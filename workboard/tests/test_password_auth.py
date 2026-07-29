import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash


ROOT = Path(__file__).resolve().parents[1]
TEST_DATA = Path(tempfile.mkdtemp(prefix="workboard-auth-"))
os.environ.update(
    {
        "WORKBOARD_AUTH_MODE": "password",
        "WORKBOARD_PASSWORD_HASH": generate_password_hash("test-password"),
        "WORKBOARD_SESSION_SECRET": "test-session-secret-not-for-production",
        "WORKBOARD_ALLOWED_ORIGINS": "https://work.cvhao.top",
        "WORKBOARD_DATA_DIR": str(TEST_DATA),
        "WORKBOARD_DOCS_DIR": str(TEST_DATA / "docs"),
    }
)
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


class PasswordAuthenticationTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_DATA, ignore_errors=True)

    def setUp(self):
        self.client = server.app.test_client()
        server.AUTH_MODE = "password"
        server.LOGIN_FAILURES.clear()
        server.MAX_LOGIN_FAILURES = 5

    def login(self):
        page = self.client.get("/login")
        self.assertEqual(page.status_code, 200)
        token = self.csrf_from_page(page.get_data(as_text=True))
        response = self.client.post(
            "/login",
            data={"password": "test-password", "csrf_token": token},
        )
        self.assertEqual(response.status_code, 302)
        return self.client.get("/api/session").get_json()["csrfToken"]

    @staticmethod
    def csrf_from_page(html):
        marker = 'name="csrf_token" value="'
        start = html.index(marker) + len(marker)
        return html[start : html.index('"', start)]

    def test_unauthenticated_page_redirects_and_api_is_denied(self):
        self.assertEqual(self.client.get("/").status_code, 302)
        response = self.client.get("/api/projects")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "Authentication required")

    def test_login_creates_authenticated_session(self):
        csrf_token = self.login()
        self.assertTrue(csrf_token)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_invalid_password_is_rejected(self):
        page = self.client.get("/login")
        token = self.csrf_from_page(page.get_data(as_text=True))
        response = self.client.post("/login", data={"password": "wrong", "csrf_token": token})
        self.assertEqual(response.status_code, 401)

    def test_missing_password_configuration_fails_closed(self):
        original_hash = server.PASSWORD_HASH
        server.PASSWORD_HASH = ""
        try:
            self.assertEqual(self.client.get("/login").status_code, 503)
            self.assertEqual(self.client.get("/api/projects").status_code, 503)
        finally:
            server.PASSWORD_HASH = original_hash

    def test_writes_and_logout_require_csrf(self):
        csrf_token = self.login()
        self.assertEqual(
            self.client.post("/api/todos", json={"name": "CSRF test"}).status_code,
            403,
        )
        self.assertEqual(self.client.post("/logout").status_code, 403)
        self.assertEqual(
            self.client.post("/logout", headers={"X-CSRF-Token": csrf_token}).status_code,
            204,
        )
        self.assertEqual(self.client.get("/api/projects").status_code, 401)

    def test_failed_logins_are_rate_limited(self):
        original_limit = server.MAX_LOGIN_FAILURES
        server.MAX_LOGIN_FAILURES = 2
        try:
            for _ in range(2):
                page = self.client.get("/login")
                token = self.csrf_from_page(page.get_data(as_text=True))
                self.assertEqual(
                    self.client.post("/login", data={"password": "wrong", "csrf_token": token}).status_code,
                    401,
                )
            page = self.client.get("/login")
            token = self.csrf_from_page(page.get_data(as_text=True))
            self.assertEqual(
                self.client.post("/login", data={"password": "wrong", "csrf_token": token}).status_code,
                429,
            )
        finally:
            server.MAX_LOGIN_FAILURES = original_limit

    def test_cloudflare_mode_still_accepts_access_identity(self):
        server.AUTH_MODE = "cloudflare"
        server.ALLOWED_EMAILS = {"owner@example.com"}
        self.assertEqual(self.client.get("/api/projects").status_code, 401)
        response = self.client.get(
            "/api/projects",
            headers={"Cf-Access-Authenticated-User-Email": "owner@example.com"},
        )
        self.assertEqual(response.status_code, 200)

    def test_login_assets_and_dashboard_logout_hook_exist(self):
        response = self.client.get("/login.css")
        self.assertEqual(response.status_code, 200)
        response.close()
        self.assertIn("logoutButton", (ROOT / "static" / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
