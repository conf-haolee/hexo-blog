import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LocalEnvFileTests(unittest.TestCase):
    def test_server_loads_config_from_workboard_env_file(self):
        with tempfile.TemporaryDirectory(prefix="workboard-env-") as tmp:
            env_file = Path(tmp) / ".env.local"
            env_file.write_text(
                textwrap.dedent(
                    """
                    WORKBOARD_AUTH_MODE=password
                    WORKBOARD_PASSWORD_HASH=scrypt:32768:8:1$example$hash
                    WORKBOARD_SESSION_SECRET=test-session-secret
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            for key in (
                "WORKBOARD_AUTH_MODE",
                "WORKBOARD_PASSWORD_HASH",
                "WORKBOARD_SESSION_SECRET",
            ):
                env.pop(key, None)
            env["WORKBOARD_ENV_FILE"] = str(env_file)
            env["PYTHONPATH"] = str(ROOT)

            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import server; print(server.AUTH_MODE); print(server.password_auth_is_configured())",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), ["password", "True"])


if __name__ == "__main__":
    unittest.main()
