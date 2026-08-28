import hashlib
import io
import json
import multiprocessing
import os
import sys
import tempfile
import threading
import time
from unittest.mock import patch
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from archive_service import ArchiveStorage


def hold_archive_lock(staging_root, done_root, ready, release):
    storage = ArchiveStorage(Path(staging_root), Path(done_root))
    with storage.task_lock(42):
        ready.set()
        release.wait(5)


class ArchiveStorageTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.staging_root = root / ".archive-staging"
        self.done_root = root / "docs" / "Done"
        self.storage = ArchiveStorage(self.staging_root, self.done_root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_store_file_accepts_nested_relative_file_inside_staging(self):
        content = b"archive evidence"
        result = self.storage.store_file(
            42,
            "evidence/logs/result.txt",
            io.BytesIO(content),
            len(content),
            hashlib.sha256(content).hexdigest(),
        )

        expected = self.staging_root / "42" / "files" / "evidence" / "logs" / "result.txt"
        self.assertEqual(result, expected.resolve())
        self.assertEqual(expected.read_bytes(), content)
        self.assertTrue(expected.resolve().is_relative_to(self.staging_root.resolve()))

    def test_store_file_rejects_absolute_and_traversal_paths(self):
        content = b"archive evidence"
        digest = hashlib.sha256(content).hexdigest()

        for relative_path in ("/etc/passwd", r"C:\\windows\\system32", "../secret.txt", "nested/../../secret.txt"):
            with self.subTest(relative_path=relative_path):
                with self.assertRaises(ValueError):
                    self.storage.store_file(42, relative_path, io.BytesIO(content), len(content), digest)

        self.assertFalse((Path(self.temp_dir.name) / "secret.txt").exists())

    def test_store_file_rejects_mismatched_size_or_hash_without_final_file(self):
        content = b"archive evidence"
        digest = hashlib.sha256(content).hexdigest()

        with self.assertRaises(ValueError):
            self.storage.store_file(42, "evidence.txt", io.BytesIO(content), len(content) + 1, digest)
        with self.assertRaises(ValueError):
            self.storage.store_file(42, "evidence.txt", io.BytesIO(content), len(content), "0" * 64)

        destination = self.staging_root / "42" / "files" / "evidence.txt"
        self.assertFalse(destination.exists())
        self.assertFalse(destination.with_suffix(".txt.part").exists())

    def test_commit_is_idempotent_only_for_its_own_manifest(self):
        content = b"archive evidence"
        digest = hashlib.sha256(content).hexdigest()
        self.storage.store_file(42, "evidence.txt", io.BytesIO(content), len(content), digest)

        manifest = [{"relativePath": "evidence.txt", "size": len(content), "sha256": digest}]
        target = self.storage.commit(42, "Task 42", manifest)

        self.assertEqual(target, (self.done_root / "Task 42" / "files").resolve())
        manifest_path = target / ".archive-manifest.json"
        self.assertTrue(manifest_path.is_file())
        ownership_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(ownership_manifest["todoId"], 42)
        self.assertEqual(self.storage.commit(42, "Task 42", manifest), target)

        self.storage.store_file(43, "evidence.txt", io.BytesIO(content), len(content), digest)
        (self.done_root / "Existing task" / "files").mkdir(parents=True)
        with self.assertRaises(ValueError):
            self.storage.commit(43, "Existing task", manifest)

    def test_store_file_rejects_part_names_and_commit_requires_exact_manifest(self):
        content = b"archive evidence"
        digest = hashlib.sha256(content).hexdigest()
        with self.assertRaises(ValueError):
            self.storage.store_file(42, "evidence.part", io.BytesIO(content), len(content), digest)

        self.storage.store_file(42, "evidence.txt", io.BytesIO(content), len(content), digest)
        manifest = [{"relativePath": "evidence.txt", "size": len(content), "sha256": digest}]
        with self.assertRaises(ValueError):
            self.storage.commit(42, "Task 42", [])
        self.assertEqual(
            self.storage.commit(42, "Task 42", manifest),
            (self.done_root / "Task 42" / "files").resolve(),
        )

    def test_task_lock_blocks_a_second_storage_instance_in_another_process(self):
        context = multiprocessing.get_context("spawn")
        ready = context.Event()
        release = context.Event()
        holder = context.Process(
            target=hold_archive_lock,
            args=(str(self.staging_root), str(self.done_root), ready, release),
        )
        holder.start()
        self.assertTrue(ready.wait(5))
        acquired = threading.Event()

        def contend():
            with ArchiveStorage(self.staging_root, self.done_root).task_lock(42):
                acquired.set()

        contender = threading.Thread(target=contend)
        contender.start()
        self.assertFalse(acquired.wait(0.3))
        release.set()
        contender.join(5)
        holder.join(5)
        self.assertTrue(acquired.is_set())
        self.assertEqual(holder.exitcode, 0)

    def test_old_lock_file_timestamp_does_not_steal_a_live_advisory_lock(self):
        context = multiprocessing.get_context("spawn")
        ready, release = context.Event(), context.Event()
        holder = context.Process(target=hold_archive_lock, args=(str(self.staging_root), str(self.done_root), ready, release))
        holder.start(); self.assertTrue(ready.wait(5))
        lock_path = self.staging_root / ".locks" / "42.lock"
        os.utime(lock_path, (time.time() - 120, time.time() - 120))
        acquired = threading.Event()
        def contend():
            with ArchiveStorage(self.staging_root, self.done_root).task_lock(42):
                acquired.set()
        contender = threading.Thread(target=contend)
        contender.start()
        self.assertFalse(acquired.wait(0.3))
        release.set(); contender.join(5); holder.join(5)
        self.assertTrue(acquired.is_set())

    def test_symbolic_link_locks_directory_is_rejected(self):
        self.staging_root.mkdir()
        outside = Path(self.temp_dir.name) / "outside"; outside.mkdir()
        try:
            os.symlink(outside, self.staging_root / ".locks", target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symbolic links unavailable: {exc}")
        with self.assertRaises(ValueError):
            with self.storage.task_lock(42):
                pass

    def test_lock_write_failure_closes_descriptor(self):
        with patch("archive_service.os.write", side_effect=OSError("write denied")), patch("archive_service.os.close", wraps=os.close) as close:
            with self.assertRaises(OSError):
                with self.storage.task_lock(42):
                    pass
        self.assertEqual(close.call_count, 1)

    def test_lock_acquisition_failure_closes_descriptor_without_unlocking(self):
        self.storage._lock_timeout_seconds = 0
        with patch.object(self.storage, "_try_lock", side_effect=BlockingIOError), patch("archive_service.os.close", wraps=os.close) as close, patch.object(self.storage, "_unlock") as unlock:
            with self.assertRaises(TimeoutError):
                with self.storage.task_lock(42):
                    pass
        self.assertEqual(close.call_count, 1)
        unlock.assert_not_called()

    def test_stale_staging_maintenance_skips_a_task_held_by_another_process(self):
        task_dir = self.staging_root / "42" / "files"
        task_dir.mkdir(parents=True)
        task_dir.joinpath("active.txt").write_bytes(b"still uploading")
        old = time.time() - 120
        os.utime(task_dir.parent, (old, old))
        self.storage._lock_timeout_seconds = 0.1
        context = multiprocessing.get_context("spawn")
        ready, release = context.Event(), context.Event()
        holder = context.Process(target=hold_archive_lock, args=(str(self.staging_root), str(self.done_root), ready, release))
        holder.start(); self.assertTrue(ready.wait(5))
        self.assertEqual(self.storage.discard_stale_staging(max_age_seconds=60, now=time.time()), [])
        self.assertTrue(task_dir.exists())
        release.set(); holder.join(5)


if __name__ == "__main__":
    unittest.main()
