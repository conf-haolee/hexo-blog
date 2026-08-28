import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bootstrap_local_from_nas.ps1"


class BootstrapLocalFromNasScriptTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.nas_data_dir = self.root / "nas-data"
        self.nas_docs_dir = self.nas_data_dir / "docs"
        self.nas_docs_dir.mkdir(parents=True)
        self._write_db(self.nas_data_dir / "workboard.sqlite3", "nas")
        (self.nas_docs_dir / "todo.txt").write_text("from nas", encoding="utf-8")
        self.local_data_dir = self.root / "local-data"
        self.backup_dir = self.root / "local-backups"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_bootstrap_copies_nas_database_and_docs_to_empty_local_data_dir(self):
        powershell = self._powershell()

        result = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT),
                "-NasDataDir",
                str(self.nas_data_dir),
                "-LocalDataDir",
                str(self.local_data_dir),
                "-BackupDir",
                str(self.backup_dir),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self._read_db(self.local_data_dir / "workboard.sqlite3"), "nas")
        self.assertEqual((self.local_data_dir / "docs" / "todo.txt").read_text(encoding="utf-8"), "from nas")
        self.assertFalse(list(self.backup_dir.glob("local-before-bootstrap-*.zip")))

    def test_bootstrap_refuses_to_overwrite_existing_local_data_without_force(self):
        powershell = self._powershell()
        self.local_data_dir.mkdir()
        self._write_db(self.local_data_dir / "workboard.sqlite3", "local")

        result = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT),
                "-NasDataDir",
                str(self.nas_data_dir),
                "-LocalDataDir",
                str(self.local_data_dir),
                "-BackupDir",
                str(self.backup_dir),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self._read_db(self.local_data_dir / "workboard.sqlite3"), "local")

    def test_bootstrap_force_backs_up_existing_local_data_before_replacing_it(self):
        powershell = self._powershell()
        local_docs_dir = self.local_data_dir / "docs"
        local_docs_dir.mkdir(parents=True)
        self._write_db(self.local_data_dir / "workboard.sqlite3", "local")
        (local_docs_dir / "old.txt").write_text("old", encoding="utf-8")

        result = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT),
                "-NasDataDir",
                str(self.nas_data_dir),
                "-LocalDataDir",
                str(self.local_data_dir),
                "-BackupDir",
                str(self.backup_dir),
                "-Force",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self._read_db(self.local_data_dir / "workboard.sqlite3"), "nas")
        self.assertFalse((self.local_data_dir / "docs" / "old.txt").exists())
        backups = list(self.backup_dir.glob("local-before-bootstrap-*.zip"))
        self.assertEqual(len(backups), 1)

    def _powershell(self):
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if not powershell:
            self.skipTest("PowerShell is unavailable")
        return powershell

    def _write_db(self, path: Path, value: str) -> None:
        connection = sqlite3.connect(path)
        try:
            connection.execute("CREATE TABLE smoke (value TEXT)")
            connection.execute("INSERT INTO smoke VALUES (?)", (value,))
            connection.commit()
        finally:
            connection.close()

    def _read_db(self, path: Path) -> str:
        connection = sqlite3.connect(path)
        try:
            return connection.execute("SELECT value FROM smoke").fetchone()[0]
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
