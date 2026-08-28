"""Safe local path handling for the Workboard Windows archive helper."""

from dataclasses import dataclass
import hashlib
import os
import stat
from pathlib import Path, PureWindowsPath


@dataclass(frozen=True)
class FileEntry:
    relative_path: str
    size: int
    sha256: str


def resolve_task_path(root: Path, stored_path: str) -> Path:
    root = Path(root).resolve(strict=False)
    value = str(stored_path or "").strip()
    if not value:
        return root
    windows_path = PureWindowsPath(value)
    if windows_path.is_absolute() or windows_path.drive or value.startswith(("/", "\\")):
        raise ValueError("Task path must be relative to the Workboard root")
    parts = [part for part in windows_path.parts if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise ValueError("Task path must not traverse outside the Workboard root")
    candidate = root.joinpath(*parts).resolve(strict=False)
    _require_under(candidate, root)
    return candidate


def collect_task_files(root: Path, task_path: Path) -> list[FileEntry]:
    root = Path(root).resolve(strict=False)
    task_path = Path(task_path).resolve(strict=False)
    _require_under(task_path, root)
    if is_link_or_reparse(task_path):
        raise ValueError("Task path must not be a symbolic link or reparse point")
    if not task_path.is_dir():
        raise FileNotFoundError(f"Task path does not exist: {task_path}")

    archive_path = (root / "archive").resolve(strict=False)
    entries = []
    for current, directories, files in os.walk(task_path):
        current_path = Path(current)
        if _is_archive_path(current_path, archive_path):
            directories[:] = []
            continue
        for directory in list(directories):
            directory_path = current_path / directory
            if is_link_or_reparse(directory_path):
                raise ValueError("Task files must not contain symbolic links or reparse points")
            if _is_archive_path(directory_path, archive_path):
                directories.remove(directory)
        for filename in files:
            file_path = current_path / filename
            if is_link_or_reparse(file_path):
                raise ValueError("Task files must not contain symbolic links or reparse points")
            if _is_archive_path(file_path, archive_path):
                continue
            relative_path = file_path.relative_to(task_path).as_posix()
            entries.append(FileEntry(relative_path, file_path.stat().st_size, _sha256_file(file_path)))
    return sorted(entries, key=lambda entry: entry.relative_path)


def _require_under(path: Path, root: Path) -> None:
    try:
        common = os.path.commonpath([str(path), str(root)])
    except ValueError as exc:
        raise ValueError("Task path must stay under the Workboard root") from exc
    if common != str(root):
        raise ValueError("Task path must stay under the Workboard root")


def _is_archive_path(path: Path, archive_path: Path) -> bool:
    path = path.resolve(strict=False)
    return path == archive_path or path.is_relative_to(archive_path)


def is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(metadata.st_mode) or bool(getattr(metadata, "st_file_attributes", 0) & reparse_point)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
