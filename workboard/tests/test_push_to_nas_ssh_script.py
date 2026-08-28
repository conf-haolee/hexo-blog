import json
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "push_to_nas_ssh.ps1"


class PushToNasSshScriptTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "data"
        self.docs_dir = self.data_dir / "docs"
        self.docs_dir.mkdir(parents=True)
        self._write_db(self.data_dir / "workboard.sqlite3", "local")
        (self.docs_dir / "progress.txt").write_text("local progress", encoding="utf-8")
        self.local_backup_dir = self.root / "backups"
        self.plan_path = self.root / "push-plan.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_push_script_dry_run_creates_backup_and_writes_remote_overwrite_plan(self):
        powershell = self._powershell()

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
                "-Remote",
                "nas-user@nas-host",
                "-RemoteDataDir",
                "/volume1/docker/workboard/data",
                "-RemoteBackupDir",
                "/volume1/docker/workboard/backups",
                "-RemoteTempDir",
                "/tmp",
                "-Commit",
                "abc123",
                "-DryRun",
                "-PlanPath",
                str(self.plan_path),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        backups = list(self.local_backup_dir.glob("workboard-push-*.zip"))
        self.assertEqual(len(backups), 1)
        with zipfile.ZipFile(backups[0]) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {"commit.txt", "data/docs/progress.txt", "data/workboard.sqlite3"},
            )
            self.assertEqual(archive.read("commit.txt").decode("utf-8"), "abc123")
        plan = json.loads(self.plan_path.read_text(encoding="utf-8"))
        self.assertEqual(plan["remote"], "nas-user@nas-host")
        self.assertEqual(plan["remoteDataDir"], "/volume1/docker/workboard/data")
        self.assertEqual(plan["remoteBackupDir"], "/volume1/docker/workboard/backups")
        self.assertTrue(plan["localZip"].endswith(backups[0].name))
        commands = "\n".join(plan["commands"])
        self.assertIn("scp", commands)
        self.assertIn("ssh", commands)
        self.assertIn("/volume1/docker/workboard/data", commands)
        self.assertIn("/volume1/docker/workboard/backups", commands)
        self.assertIn("unzip -oq", commands)

    def test_push_script_rejects_missing_local_database(self):
        powershell = self._powershell()
        missing_data_dir = self.root / "missing-data"
        missing_data_dir.mkdir()

        result = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT),
                "-DataDir",
                str(missing_data_dir),
                "-LocalBackupDir",
                str(self.local_backup_dir),
                "-Remote",
                "nas-user@nas-host",
                "-RemoteDataDir",
                "/volume1/docker/workboard/data",
                "-DryRun",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertNotEqual(result.returncode, 0)

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


if __name__ == "__main__":
    unittest.main()
