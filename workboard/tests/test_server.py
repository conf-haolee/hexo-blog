import os
import tempfile
import io
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

    def test_create_todo_accepts_detail_fields_and_screenshot(self):
        access_headers = {"Cf-Access-Authenticated-User-Email": "owner@example.com"}
        response = self.client.post(
            "/api/todos",
            data={
                "name": "调试视觉流程",
                "projectId": "",
                "projectNumber": "PX-2026-081",
                "contact": "杨珂",
                "notes": "先复现现场问题，再整理日志。",
                "taskDate": "2026-08-25",
                "dueAt": "2026-08-31T18:00",
                "screenshot": (io.BytesIO(b"fake-png-content"), "issue.png", "image/png"),
            },
            headers=access_headers,
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        item = response.get_json()["item"]
        self.assertEqual(item["projectNumber"], "PX-2026-081")
        self.assertEqual(item["contact"], "杨珂")
        self.assertEqual(item["notes"], "先复现现场问题，再整理日志。")
        self.assertEqual(item["taskDate"], "2026-08-25")
        self.assertTrue(item["screenshotUrl"].endswith("/screenshot"))

        screenshot = self.client.get(item["screenshotUrl"], headers=access_headers)
        self.assertEqual(screenshot.status_code, 200)
        self.assertEqual(screenshot.data, b"fake-png-content")
        screenshot.close()

        document = self.client.get(
            "/api/todos/%s/document" % item["id"], headers=access_headers
        )
        markdown = document.get_data(as_text=True)
        self.assertIn("- Project number: PX-2026-081", markdown)
        self.assertIn("- Contact: 杨珂", markdown)
        self.assertIn("先复现现场问题，再整理日志。", markdown)
        document.close()

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

