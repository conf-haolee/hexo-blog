import shutil
import sqlite3
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync_to_nas.ps1"


class SyncToNasScriptTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "data"
        self.docs_dir = self.data_dir / "docs"
        self.docs_dir.mkdir(parents=True)
        connection = sqlite3.connect(self.data_dir / "workboard.sqlite3")
        connection.execute("CREATE TABLE smoke (value TEXT)")
        connection.execute("INSERT INTO smoke VALUES ('sqlite snapshot')")
        connection.commit()
        connection.close()
        (self.docs_dir / "note.txt").write_text("progress", encoding="utf-8")
        self.local_backup_dir = self.root / "local-backups"
        self.nas_backup_dir = self.root / "nas-backups"
        self.nas_backup_dir.mkdir()
        self.nas_mirror_dir = self.root / "nas-mirror"
        self.nas_mirror_dir.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sync_script_creates_local_zip_and_copies_it_to_available_nas_path(self):
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if not powershell:
            self.skipTest("PowerShell is unavailable")

        result = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT),
                "-DataDir",
                str(self.data_dir),
                "-LocalBackupDir",
                str(self.local_backup_dir),
                "-NasBackupDir",
                str(self.nas_backup_dir),
                "-NasMirrorDir",
                str(self.nas_mirror_dir),
                "-Commit",
                "abc123",
                "-Keep",
                "3",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        local_zips = list(self.local_backup_dir.glob("workboard-backup-*.zip"))
        nas_zips = list(self.nas_backup_dir.glob("workboard-backup-*.zip"))
        self.assertEqual(len(local_zips), 1)
        self.assertEqual([path.name for path in nas_zips], [local_zips[0].name])
        with zipfile.ZipFile(local_zips[0]) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {"commit.txt", "data/docs/note.txt", "data/workboard.sqlite3"},
            )
            self.assertEqual(archive.read("commit.txt").decode("utf-8"), "abc123")
        self.assertEqual((self.nas_mirror_dir / "latest" / "commit.txt").read_text(encoding="utf-8"), "abc123")
        self.assertEqual((self.nas_mirror_dir / "latest" / "data" / "docs" / "note.txt").read_text(encoding="utf-8"), "progress")
        connection = sqlite3.connect(self.nas_mirror_dir / "latest" / "data" / "workboard.sqlite3")
        try:
            self.assertEqual(connection.execute("SELECT value FROM smoke").fetchone()[0], "sqlite snapshot")
        finally:
            connection.close()

    def test_sync_script_keeps_local_backup_when_nas_path_is_unavailable(self):
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if not powershell:
            self.skipTest("PowerShell is unavailable")
        missing_nas_dir = self.root / "missing-nas"

        result = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT),
                "-DataDir",
                str(self.data_dir),
                "-LocalBackupDir",
                str(self.local_backup_dir),
                "-NasBackupDir",
                str(missing_nas_dir),
                "-Commit",
                "abc123",
                "-Keep",
                "3",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(len(list(self.local_backup_dir.glob("workboard-backup-*.zip"))), 1)
        self.assertFalse(missing_nas_dir.exists())


if __name__ == "__main__":
    unittest.main()
