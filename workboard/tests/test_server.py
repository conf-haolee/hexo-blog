import os
import tempfile
import unittest
from pathlib import Path

import server


class WorkboardApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        server.DATA_DIR = root / "data"
        server.DB_PATH = server.DATA_DIR / "workboard.sqlite3"
        server.DOCS_DIR = server.DATA_DIR / "docs"
        server.TODO_DIR = server.DOCS_DIR / "TODO"
        server.DONE_DIR = server.DOCS_DIR / "Done"
        server.PROJECTS_IMPORT_FILE = root / "missing-projects.json"
        server.AUTH_MODE = "cloudflare"
        server.ALLOWED_EMAILS = {"owner@example.com"}
        server.ALLOWED_ORIGINS = {"http://localhost:5000"}
        server.app.config.update(TESTING=True)
        self.client = server.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_health_does_not_expose_filesystem_path(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["storage"], "sqlite")
        self.assertNotIn("todo_workspace", response.json)

    def test_project_and_todo_flow_hides_paths(self):
        access_headers = {"Cf-Access-Authenticated-User-Email": "owner@example.com"}
        project_dir = Path(self.temp_dir.name) / "project"
        project_dir.mkdir()
        response = self.client.post(
            "/api/projects",
            json={
                "name": "Private project",
                "nasPath": str(project_dir),
                "gitRepo": "",
                "created": "2026-07-13",
                "tags": "vision, C#",
                "categories": "source",
            },
            headers=access_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("nasPath", response.json["item"])
        self.assertNotIn("localPath", response.json["item"])

        response = self.client.post(
            "/api/todos",
            json={"name": "Write project review", "projectId": 1},
            headers=access_headers,
        )
        self.assertEqual(response.status_code, 200)
        todo_id = response.json["item"]["id"]

        response = self.client.get("/api/todos/%s/document" % todo_id, headers=access_headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Write project review", response.get_data(as_text=True))
        response.close()

        response = self.client.get("/api/todos/%s/open" % todo_id, headers=access_headers)
        self.assertEqual(response.status_code, 410)

    def test_cloudflare_mode_requires_identity_header(self):
        server.AUTH_MODE = "cloudflare"
        server.ALLOWED_EMAILS = {"owner@example.com"}

        response = self.client.get("/")
        self.assertEqual(response.status_code, 401)
        response.close()
        response = self.client.get(
            "/",
            headers={"Cf-Access-Authenticated-User-Email": "owner@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        response.close()


if __name__ == "__main__":
    unittest.main()

