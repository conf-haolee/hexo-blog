"""Isolated, integrity-checked storage for Workboard archive uploads."""

import contextlib
import hashlib
import json
import os
import secrets
import shutil
import stat
import time
from pathlib import Path, PurePosixPath, PureWindowsPath

try:
    import fcntl
except ImportError:
    fcntl = None
    import msvcrt


class ArchiveStorage:
    _ownership_manifest_name = ".archive-manifest.json"
    _lock_timeout_seconds = 5

    def __init__(self, staging_root: Path, done_root: Path):
        self._configured_staging_root = Path(staging_root).absolute()
        self.staging_root = Path(staging_root).resolve()
        self.done_root = Path(done_root).resolve()

    @contextlib.contextmanager
    def task_lock(self, todo_id):
        todo_id = self._todo_id(todo_id)
        lock_dir = self._lock_directory()
        lock_path = lock_dir / f"{todo_id}.lock"
        self._require_under(lock_path, lock_dir)
        deadline = time.monotonic() + self._lock_timeout_seconds
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = None
        locked = False
        try:
            descriptor = os.open(lock_path, flags, 0o600)
            if self._is_link_or_reparse(lock_path):
                raise ValueError("Archive lock file is unsafe")
            # msvcrt locks byte ranges and therefore needs at least one byte to
            # exist before attempting a lock.  Never rewrite an existing lock:
            # another process may currently own that byte range.
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"0")
            while True:
                try:
                    self._try_lock(descriptor)
                    locked = True
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Timed out waiting for archive task lock")
                    time.sleep(0.05)
            yield
        finally:
            if descriptor is not None:
                try:
                    if locked:
                        self._unlock(descriptor)
                finally:
                    os.close(descriptor)

    def _lock_directory(self):
        if self._is_link_or_reparse(self._configured_staging_root):
            raise ValueError("Archive staging root is unsafe")
        self.staging_root.mkdir(parents=True, exist_ok=True)
        if self._is_link_or_reparse(self.staging_root) or not self.staging_root.is_dir():
            raise ValueError("Archive staging root is unsafe")
        lock_dir = self.staging_root / ".locks"
        try:
            lock_dir.mkdir()
        except FileExistsError:
            pass
        if self._is_link_or_reparse(lock_dir) or not lock_dir.is_dir():
            raise ValueError("Archive lock directory is unsafe")
        self._require_under(lock_dir, self.staging_root)
        return lock_dir

    @staticmethod
    def _is_link_or_reparse(path):
        try:
            metadata = Path(path).lstat()
        except FileNotFoundError:
            return False
        reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return stat.S_ISLNK(metadata.st_mode) or bool(getattr(metadata, "st_file_attributes", 0) & reparse_point)

    @staticmethod
    def _try_lock(descriptor):
        if fcntl is not None:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise BlockingIOError() from exc
            return
        try:
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise BlockingIOError() from exc

    @staticmethod
    def _unlock(descriptor):
        if fcntl is not None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        else:
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)

    def reset(self, todo_id):
        with self.task_lock(todo_id):
            return self.reset_locked(todo_id)

    def reset_locked(self, todo_id):
        task_dir = self.staging_root / str(self._todo_id(todo_id))
        self._require_under(task_dir, self.staging_root)
        if task_dir.exists() or self._is_link_or_reparse(task_dir):
            if self._is_link_or_reparse(task_dir) or not task_dir.is_dir():
                raise ValueError("Archive staging directory is unsafe")
            shutil.rmtree(task_dir)
        task_dir.mkdir(parents=True, exist_ok=False)
        return task_dir

    def store_file(self, todo_id, relative_path, stream, expected_size, expected_sha256):
        with self.task_lock(todo_id):
            return self.store_file_locked(todo_id, relative_path, stream, expected_size, expected_sha256)

    def store_file_locked(self, todo_id, relative_path, stream, expected_size, expected_sha256):
        parts = self._relative_parts(relative_path)
        if parts[-1].endswith(".part") or parts == (self._ownership_manifest_name,):
            raise ValueError("Archive path is reserved")
        expected_size, expected_sha256 = self._integrity(expected_size, expected_sha256)
        files_dir = self._files_dir(todo_id, create=True)
        destination = self._safe_join(files_dir, parts, create_parents=True)
        temporary_path = None
        try:
            descriptor, temporary_name = self._open_unique_temp(destination.parent, destination.name)
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as output:
                actual_size, actual_sha256 = self._copy_and_hash(stream, output)
                output.flush()
                os.fsync(output.fileno())
            if (actual_size, actual_sha256) != (expected_size, expected_sha256):
                raise ValueError("Uploaded file does not match its declared size or SHA-256")
            self._replace_checked(temporary_path, destination)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        return destination

    def commit(self, todo_id, folder_name, expected_manifest=None):
        with self.task_lock(todo_id):
            return self.commit_locked(todo_id, folder_name, expected_manifest)

    def commit_locked(self, todo_id, folder_name, expected_manifest=None):
        todo_id = self._todo_id(todo_id)
        expected = self._manifest_map(expected_manifest)
        folder = self._folder_name(folder_name)
        target_parent = self._safe_join(self.done_root, (folder,), create_parents=True)
        target_parent.mkdir(exist_ok=True)
        if self._is_link_or_reparse(target_parent):
            raise ValueError("Archive path must not traverse a symbolic link")
        target = self._safe_join(target_parent, ("files",))
        if target.exists():
            files_dir, committed = self._committed_files(todo_id, folder)
            if self._manifest_map(committed["files"]) == expected == self._collect_files(files_dir, True):
                return files_dir
            raise ValueError("Committed archive does not match the submitted manifest")
        source = self._files_dir(todo_id, create=True)
        if self._collect_files(source) != expected:
            raise ValueError("Staged archive does not exactly match the submitted manifest")
        self._write_json_atomically(source / self._ownership_manifest_name, {"todoId": todo_id, "files": self._manifest_list(expected)})
        self._replace_checked(source, target)
        return target

    def verify_committed(self, todo_id, folder_name):
        with self.task_lock(todo_id):
            return self.verify_committed_locked(todo_id, folder_name)

    def verify_committed_locked(self, todo_id, folder_name):
        files_dir, manifest = self._committed_files(todo_id, folder_name)
        if self._collect_files(files_dir, True) != self._manifest_map(manifest["files"]):
            raise ValueError("Committed archive files do not match their manifest")
        return files_dir

    def verify_committed_upload(self, todo_id, folder_name, relative_path, stream, expected_size, expected_sha256):
        with self.task_lock(todo_id):
            return self.verify_committed_upload_locked(todo_id, folder_name, relative_path, stream, expected_size, expected_sha256)

    def verify_committed_upload_locked(self, todo_id, folder_name, relative_path, stream, expected_size, expected_sha256):
        parts = self._relative_parts(relative_path)
        expected_size, expected_sha256 = self._integrity(expected_size, expected_sha256)
        if self._copy_and_hash(stream) != (expected_size, expected_sha256):
            raise ValueError("Uploaded file does not match its declared size or SHA-256")
        files_dir, manifest = self._committed_files(todo_id, folder_name)
        item = self._manifest_map(manifest["files"]).get("/".join(parts))
        path = self._safe_join(files_dir, parts)
        if item != {"size": expected_size, "sha256": expected_sha256} or not path.is_file() or self._is_link_or_reparse(path) or self._hash_file(path) != (expected_size, expected_sha256):
            raise ValueError("Committed archive does not contain this declared file")
        return path

    def discard_stale_staging(self, max_age_seconds=86400, now=None):
        cutoff = (time.time() if now is None else now) - max_age_seconds
        if not self.staging_root.is_dir() or self.staging_root.is_symlink():
            return []
        removed = []
        for child in self.staging_root.iterdir():
            if child.is_dir() and not child.is_symlink() and child.name.isdigit() and child.stat().st_mtime <= cutoff:
                try:
                    with self.task_lock(child.name):
                        if child.exists() and child.is_dir() and not self._is_link_or_reparse(child) and child.stat().st_mtime <= cutoff:
                            self._require_under(child, self.staging_root)
                            shutil.rmtree(child)
                            removed.append(child)
                except TimeoutError:
                    continue
        return removed

    def _files_dir(self, todo_id, create=False):
        task = self._safe_join(self.staging_root, (str(self._todo_id(todo_id)),), create_parents=create)
        files_dir = self._safe_join(task, ("files",), create_parents=create)
        if create:
            files_dir.mkdir(exist_ok=True)
        return files_dir

    def _committed_files(self, todo_id, folder_name):
        files_dir = self._safe_join(self.done_root, (self._folder_name(folder_name), "files"))
        manifest_path = files_dir / self._ownership_manifest_name
        if not files_dir.is_dir() or files_dir.is_symlink() or manifest_path.is_symlink():
            raise ValueError("Archive destination has no valid ownership manifest")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Archive destination has no valid ownership manifest") from exc
        if not isinstance(manifest, dict) or manifest.get("todoId") != self._todo_id(todo_id):
            raise ValueError("Archive destination belongs to another task")
        self._manifest_map(manifest.get("files"))
        return files_dir, manifest

    @staticmethod
    def _todo_id(value):
        try:
            value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Todo id must be a positive integer") from exc
        if value <= 0:
            raise ValueError("Todo id must be a positive integer")
        return value

    @staticmethod
    def _integrity(size, digest):
        try:
            size = int(size)
        except (TypeError, ValueError) as exc:
            raise ValueError("Expected size must be a non-negative integer") from exc
        digest = str(digest or "").lower()
        if size < 0 or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("Expected SHA-256 or size is invalid")
        return size, digest

    @staticmethod
    def _relative_parts(path):
        raw = str(path or "")
        if not raw or "\x00" in raw or PurePosixPath(raw).is_absolute() or PureWindowsPath(raw).is_absolute() or PureWindowsPath(raw).drive:
            raise ValueError("Archive path must be a relative path")
        parts = raw.replace("\\", "/").split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("Archive path must not contain traversal segments")
        return tuple(parts)

    @staticmethod
    def _folder_name(folder_name):
        parts = ArchiveStorage._relative_parts(folder_name)
        if len(parts) != 1:
            raise ValueError("Archive folder must be a single relative name")
        return parts[0]

    def _safe_join(self, root, parts, create_parents=False):
        root = Path(root)
        if root.exists() and root.is_symlink():
            raise ValueError("Archive storage root must not be a symbolic link")
        if create_parents:
            root.mkdir(parents=True, exist_ok=True)
        current = root
        for index, part in enumerate(parts):
            current /= part
            self._require_under(current, root)
            if current.is_symlink():
                raise ValueError("Archive path must not traverse a symbolic link")
            if create_parents and index < len(parts) - 1:
                current.mkdir(exist_ok=True)
        return current

    @staticmethod
    def _require_under(path, root):
        try:
            Path(path).resolve().relative_to(Path(root).resolve())
        except ValueError as exc:
            raise ValueError("Archive path escapes its configured storage root") from exc

    def _collect_files(self, files_dir, allow_ownership_manifest=False):
        result = {}
        if not files_dir.is_dir() or files_dir.is_symlink():
            raise ValueError("Archive files directory is unavailable")
        for directory, directories, names in os.walk(files_dir, followlinks=False):
            directory = Path(directory)
            if any((directory / name).is_symlink() for name in directories):
                raise ValueError("Archive contains a symbolic link")
            for name in names:
                path = directory / name
                relative = path.relative_to(files_dir).as_posix()
                if path.is_symlink() or name.endswith(".part"):
                    raise ValueError("Archive contains an unsafe temporary or symbolic-link file")
                if relative == self._ownership_manifest_name and allow_ownership_manifest:
                    continue
                if relative == self._ownership_manifest_name or not path.is_file():
                    raise ValueError("Archive contains an unsafe file")
                size, digest = self._hash_file(path)
                result[relative] = {"size": size, "sha256": digest}
        return result

    def _manifest_map(self, manifest):
        if not isinstance(manifest, list):
            raise ValueError("Archive manifest must be a list of files")
        result = {}
        for entry in manifest:
            if not isinstance(entry, dict):
                raise ValueError("Archive manifest entry is invalid")
            parts = self._relative_parts(entry.get("relativePath"))
            if parts[-1].endswith(".part") or parts == (self._ownership_manifest_name,):
                raise ValueError("Archive manifest contains a reserved path")
            key = "/".join(parts)
            if key in result:
                raise ValueError("Archive manifest contains duplicate paths")
            size, digest = self._integrity(entry.get("size"), entry.get("sha256"))
            result[key] = {"size": size, "sha256": digest}
        return result

    @staticmethod
    def _manifest_list(manifest):
        return [{"relativePath": path, **value} for path, value in sorted(manifest.items())]

    @staticmethod
    def _copy_and_hash(stream, output=None):
        digest, size = hashlib.sha256(), 0
        while True:
            chunk = stream.read(65536)
            if not chunk:
                return size, digest.hexdigest()
            if not isinstance(chunk, bytes):
                raise ValueError("Upload stream must produce bytes")
            if output:
                output.write(chunk)
            digest.update(chunk)
            size += len(chunk)

    @staticmethod
    def _hash_file(path):
        with Path(path).open("rb") as source:
            return ArchiveStorage._copy_and_hash(source)

    @staticmethod
    def _write_json_atomically(path, value):
        descriptor, temporary = ArchiveStorage._open_unique_temp(path.parent, path.name)
        temporary = Path(temporary)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(value, output, ensure_ascii=False, sort_keys=True, indent=2)
                output.flush()
                os.fsync(output.fileno())
            ArchiveStorage._replace_checked(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _open_unique_temp(parent, name):
        parent = Path(parent)
        if ArchiveStorage._is_link_or_reparse(parent) or not parent.is_dir():
            raise ValueError("Archive temporary-file parent is unsafe")
        for _ in range(100):
            path = parent / f".{name}.{secrets.token_hex(12)}.part"
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                descriptor = os.open(path, flags, 0o600)
            except FileExistsError:
                continue
            try:
                ArchiveStorage._require_under(path, parent)
                if ArchiveStorage._is_link_or_reparse(parent) or ArchiveStorage._is_link_or_reparse(path):
                    raise ValueError("Archive temporary file is unsafe")
                return descriptor, str(path)
            except BaseException:
                os.close(descriptor)
                raise
        raise OSError("Could not allocate a unique archive temporary file")

    @staticmethod
    def _replace_checked(source, destination):
        source = Path(source); destination = Path(destination)
        ArchiveStorage._require_under(source, source.parent)
        ArchiveStorage._require_under(destination, destination.parent)
        if any(ArchiveStorage._is_link_or_reparse(path) for path in (source, source.parent, destination.parent, destination)):
            raise ValueError("Archive replace path is unsafe")
        # Repeat the lstat/boundary checks immediately before replacement so a
        # path swap between validation and os.replace cannot redirect writes.
        ArchiveStorage._require_under(source, source.parent)
        ArchiveStorage._require_under(destination, destination.parent)
        if any(ArchiveStorage._is_link_or_reparse(path) for path in (source, source.parent, destination.parent, destination)):
            raise ValueError("Archive replace path is unsafe")
        os.replace(source, destination)
