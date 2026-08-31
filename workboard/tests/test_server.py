import os
import tempfile
import io
import hashlib
import contextlib
import sqlite3
import sys
import threading
import time
import unittest
from datetime import datetime
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server


class WorkboardServerTest(unittest.TestCase):
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
        self.access_headers = {"Cf-Access-Authenticated-User-Email": "owner@example.com"}

    def tearDown(self):
        self.temp_dir.cleanup()

    def enable_agent(self):
        previous_agent_token = server.AGENT_TOKEN
        self.addCleanup(setattr, server, "AGENT_TOKEN", previous_agent_token)
        server.AGENT_TOKEN = "test-agent-token"

    def agent_headers(self, agent_id, lease_token=None, authorization=None):
        headers = {
            "Authorization": authorization or "Bearer test-agent-token",
            "X-Workboard-Agent-Id": agent_id,
        }
        if lease_token:
            headers["X-Workboard-Lease-Token"] = lease_token
        return headers

    def create_archive_pending(self, name="Archive workflow task", screenshot=False):
        payload = {"name": name}
        if screenshot:
            response = self.client.post(
                "/api/todos",
                data={
                    **payload,
                    "contact": "Archive owner",
                    "screenshot": (io.BytesIO(b"source-screenshot"), "source.png", "image/png"),
                },
                headers=self.access_headers,
                content_type="multipart/form-data",
            )
        else:
            response = self.client.post("/api/todos", json=payload, headers=self.access_headers)
        self.assertEqual(response.status_code, 200)
        item = response.get_json()["item"]
        response.close()
        response = self.client.post("/api/todos/%s/complete" % item["id"], headers=self.access_headers)
        self.assertEqual(response.status_code, 200)
        response.close()
        return item

    def claim(self, agent_id="agent-a", lease_token=None):
        response = self.client.post(
            "/api/agent/jobs/claim",
            json={"agentId": agent_id, "leaseToken": lease_token} if lease_token else {"agentId": agent_id},
            headers=self.agent_headers(agent_id, lease_token),
        )
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        response.close()
        return result

    def upload(self, todo_id, agent_id, lease_token, relative_path, content):
        return self.client.put(
            "/api/agent/jobs/%s/files" % todo_id,
            data={
                "relativePath": relative_path,
                "expectedSize": str(len(content)),
                "expectedSha256": hashlib.sha256(content).hexdigest(),
                "file": (io.BytesIO(content), Path(relative_path).name),
            },
            headers=self.agent_headers(agent_id, lease_token),
            content_type="multipart/form-data",
        )

    def commit(self, todo_id, agent_id, lease_token, manifest):
        return self.client.post(
            "/api/agent/jobs/%s/commit" % todo_id,
            json={"manifest": manifest},
            headers=self.agent_headers(agent_id, lease_token),
        )

    def test_todo_archive_fields_migrate_and_serialize(self):
        server.DATA_DIR.mkdir(parents=True)
        connection = sqlite3.connect(server.DB_PATH)
        connection.execute(
            """
            CREATE TABLE todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_no INTEGER NOT NULL,
                name TEXT NOT NULL,
                project_id INTEGER,
                project_name TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                completed_at TEXT,
                due_at TEXT,
                progress INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'todo',
                folder_name TEXT NOT NULL,
                project_number TEXT NOT NULL DEFAULT '',
                contact TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                task_date TEXT NOT NULL DEFAULT '',
                screenshot_name TEXT NOT NULL DEFAULT '',
                screenshot_mime TEXT NOT NULL DEFAULT ''
            )
            """
        )
        connection.commit()
        connection.close()

        response = self.client.post(
            "/api/todos", json={"name": "Archive-ready task"}, headers=self.access_headers
        )

        self.assertEqual(response.status_code, 200)
        item = response.get_json()["item"]
        response.close()
        migrated = sqlite3.connect(server.DB_PATH)
        columns = {row[1] for row in migrated.execute("PRAGMA table_info(todos)")}
        migrated.close()
        self.assertTrue(
            {
                "result_description",
                "local_path",
                "archive_status",
                "archive_error",
                "archive_lease_until",
                "archive_agent_id",
                "archive_completed_at",
            }.issubset(columns)
        )
        self.assertEqual(item["resultDescription"], "")
        self.assertEqual(item["localPath"], "")
        self.assertEqual(item["archiveStatus"], "")
        self.assertEqual(item["archiveError"], "")
        self.assertIsNone(item["archiveCompletedAt"])

    def test_update_todo_details_validates_local_path(self):
        self.assertEqual(server.normalize_local_path(""), "")
        self.assertEqual(server.normalize_local_path("TaskA"), "TaskA")
        self.assertEqual(
            server.normalize_local_path(r"D:\01WorkBoard\TaskA"), "TaskA"
        )
        for unsafe_path in (r"..\secret", r"C:\secret", r"\\server\share"):
            with self.assertRaises(ValueError):
                server.normalize_local_path(unsafe_path)

        project_response = self.client.post(
            "/api/projects",
            json={
                "name": "Archive Project",
                "nasPath": r"\\nas\projects\archive-project",
                "created": "2026-08-25",
            },
            headers=self.access_headers,
        )
        self.assertEqual(project_response.status_code, 200)
        project_id = project_response.get_json()["item"]["id"]
        project_response.close()

        todo_response = self.client.post(
            "/api/todos",
            data={
                "name": "Original task",
                "contact": "Original owner",
                "taskDate": "2026-08-25",
                "screenshot": (io.BytesIO(b"original-image"), "original.png", "image/png"),
            },
            headers=self.access_headers,
            content_type="multipart/form-data",
        )
        self.assertEqual(todo_response.status_code, 200)
        original = todo_response.get_json()["item"]
        todo_response.close()

        response = self.client.patch(
            "/api/todos/%s" % original["id"],
            json={
                "name": "Edited task",
                "projectId": project_id,
                "projectNumber": "WB-2026-001",
                "contact": "Archive owner",
                "notes": "Archive the completed work package.",
                "resultDescription": "Local archive verified.",
                "localPath": r"D:\01WorkBoard\TaskA",
                "taskDate": "2026-08-26",
                "dueAt": "2026-08-31T18:00",
                "progress": 80,
            },
            headers=self.access_headers,
        )

        self.assertEqual(response.status_code, 200)
        item = response.get_json()["item"]
        response.close()
        self.assertEqual(item["name"], "Edited task")
        self.assertEqual(item["projectName"], "Archive Project")
        self.assertEqual(item["projectNumber"], "WB-2026-001")
        self.assertEqual(item["contact"], "Archive owner")
        self.assertEqual(item["notes"], "Archive the completed work package.")
        self.assertEqual(item["resultDescription"], "Local archive verified.")
        self.assertEqual(item["localPath"], "TaskA")
        self.assertEqual(item["taskDate"], "2026-08-26")
        self.assertEqual(item["dueAt"], "2026-08-31T18:00")
        self.assertEqual(item["progress"], 80)
        self.assertEqual(item["screenshotName"], original["screenshotName"])

        screenshot_response = self.client.patch(
            "/api/todos/%s" % original["id"],
            data={
                "name": "Edited task",
                "screenshot": (io.BytesIO(b"replacement-image"), "replacement.jpg", "image/jpeg"),
            },
            headers=self.access_headers,
            content_type="multipart/form-data",
        )
        self.assertEqual(screenshot_response.status_code, 200)
        replacement = screenshot_response.get_json()["item"]
        screenshot_response.close()
        self.assertEqual(replacement["screenshotName"], "screenshot.jpg")
        screenshot = self.client.get(replacement["screenshotUrl"], headers=self.access_headers)
        self.assertEqual(screenshot.data, b"replacement-image")
        screenshot.close()

    def test_update_todo_details_applies_editable_field_limits(self):
        todo_response = self.client.post(
            "/api/todos",
            json={"name": "Original task", "taskDate": "2026-08-25"},
            headers=self.access_headers,
        )
        self.assertEqual(todo_response.status_code, 200)
        todo_id = todo_response.get_json()["item"]["id"]
        todo_response.close()

        name = "n" * 201
        project_number = "p" * 81
        contact = "c" * 121
        notes = "o" * 4001
        result_description = "r" * 8001
        local_path = "l" * 501
        response = self.client.patch(
            "/api/todos/%s" % todo_id,
            json={
                "name": name,
                "projectNumber": project_number,
                "contact": contact,
                "notes": notes,
                "resultDescription": result_description,
                "localPath": local_path,
                "taskDate": "2026-08-26",
                "dueAt": "2026-08-31T18:00",
                "progress": 100,
            },
            headers=self.access_headers,
        )

        self.assertEqual(response.status_code, 200)
        item = response.get_json()["item"]
        response.close()
        self.assertEqual(item["name"], name[:200])
        self.assertEqual(item["projectNumber"], project_number[:80])
        self.assertEqual(item["contact"], contact[:120])
        self.assertEqual(item["notes"], notes[:4000])
        self.assertEqual(item["resultDescription"], result_description[:8000])
        self.assertEqual(item["localPath"], local_path[:500])
        self.assertEqual(item["dueAt"], "2026-08-31T18:00")
        self.assertEqual(item["progress"], 100)

    def test_agent_requires_bearer_authentication_and_put_upload(self):
        self.enable_agent()
        item = self.create_archive_pending()
        response = self.client.post("/api/agent/jobs/claim", json={"agentId": "agent-a"})
        self.assertEqual(response.status_code, 401)
        response.close()
        response = self.client.post(
            "/api/agent/jobs/claim",
            json={"agentId": "agent-a"},
            headers={"Authorization": "Basic test-agent-token"},
        )
        self.assertEqual(response.status_code, 401)
        response.close()
        claim = self.claim()
        lease_token = claim["leaseToken"]
        response = self.client.post(
            "/api/agent/jobs/%s/files" % item["id"],
            headers=self.agent_headers("agent-a", lease_token),
        )
        self.assertEqual(response.status_code, 405)
        response.close()
        response = self.upload(item["id"], "agent-a", lease_token, "evidence.txt", b"evidence")
        self.assertEqual(response.status_code, 200)
        response.close()
        previous_limit = server.app.config["MAX_CONTENT_LENGTH"]
        self.addCleanup(server.app.config.__setitem__, "MAX_CONTENT_LENGTH", previous_limit)
        server.app.config["MAX_CONTENT_LENGTH"] = 8
        response = self.upload(item["id"], "agent-a", lease_token, "too-large.txt", b"too-large")
        self.assertEqual(response.status_code, 413)
        response.close()
        server.AGENT_TOKEN = ""
        response = self.client.post("/api/agent/jobs/claim", json={"agentId": "agent-a"})
        self.assertEqual(response.status_code, 503)
        response.close()

    def test_commit_requires_exact_manifest_and_allows_empty_archive(self):
        self.enable_agent()
        item = self.create_archive_pending("Manifest extra")
        claim = self.claim()
        lease_token = claim["leaseToken"]
        content = b"evidence"
        response = self.upload(item["id"], "agent-a", lease_token, "evidence.txt", content)
        self.assertEqual(response.status_code, 200)
        response.close()
        response = self.commit(item["id"], "agent-a", lease_token, [])
        self.assertEqual(response.status_code, 400)
        response.close()
        manifest = [{"relativePath": "evidence.txt", "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}]
        wrong_manifest = [{**manifest[0], "sha256": "0" * 64}]
        response = self.commit(item["id"], "agent-a", lease_token, wrong_manifest)
        self.assertEqual(response.status_code, 400)
        response.close()
        response = self.commit(item["id"], "agent-a", lease_token, manifest)
        self.assertEqual(response.status_code, 200)
        response.close()
        response = self.upload(item["id"], "agent-a", lease_token, "evidence.txt", content)
        self.assertEqual(response.status_code, 200)
        response.close()
        response = self.upload(item["id"], "agent-a", lease_token, "evidence.txt", b"changed")
        self.assertEqual(response.status_code, 409)
        response.close()

        empty_item = self.create_archive_pending("Empty archive")
        empty_claim = self.claim()
        response = self.commit(empty_item["id"], "agent-a", empty_claim["leaseToken"], [])
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_agent_lease_token_fences_stale_requests_and_renews_for_same_agent(self):
        self.enable_agent()
        item = self.create_archive_pending()
        claim = self.claim()
        lease_token = claim["leaseToken"]
        renewed = self.claim("agent-a", lease_token)
        self.assertEqual(renewed["leaseToken"], lease_token)
        response = self.upload(item["id"], "agent-a", "stale-token", "evidence.txt", b"evidence")
        self.assertEqual(response.status_code, 409)
        response.close()
        response = self.upload(item["id"], "agent-a", lease_token, "evidence.txt", b"evidence")
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_committed_job_is_reclaimable_after_lease_expiry_and_can_finish(self):
        self.enable_agent()
        item = self.create_archive_pending()
        claim = self.claim()
        response = self.commit(item["id"], "agent-a", claim["leaseToken"], [])
        self.assertEqual(response.status_code, 200)
        response.close()
        with server.app.app_context():
            expired = server.find_todo(item["id"])
            expired["archiveLeaseUntil"] = "2000-01-01T00:00:00"
            server.save_todo(expired)
        recovered = self.claim("agent-b")
        response = self.client.post(
            "/api/agent/jobs/%s/finish" % item["id"],
            headers=self.agent_headers("agent-b", recovered["leaseToken"]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["item"]["status"], "done")
        response.close()

    def test_failed_archive_requires_web_retry_before_another_claim(self):
        self.enable_agent()
        item = self.create_archive_pending()
        claim = self.claim()
        response = self.client.post(
            "/api/agent/jobs/%s/fail" % item["id"],
            json={"error": "NAS unavailable"},
            headers=self.agent_headers("agent-a", claim["leaseToken"]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["item"]["archiveStatus"], "failed")
        response.close()
        response = self.client.post(
            "/api/agent/jobs/claim",
            json={"agentId": "agent-b"},
            headers=self.agent_headers("agent-b"),
        )
        self.assertEqual(response.status_code, 204)
        response.close()
        response = self.client.post(
            "/api/todos/%s/archive/retry" % item["id"], headers=self.access_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["item"]["archiveStatus"], "pending")
        response.close()
        recovered = self.claim("agent-b")
        self.assertEqual(recovered["job"]["id"], item["id"])

    def test_retry_resets_staging_before_accepting_a_new_manifest(self):
        self.enable_agent()
        item = self.create_archive_pending("Retry cleans staging")
        claim = self.claim()
        self.client.post(
            "/api/agent/jobs/%s/fail" % item["id"],
            json={"error": "copy interrupted"},
            headers=self.agent_headers("agent-a", claim["leaseToken"]),
        ).close()
        stale = server.DATA_DIR / ".archive-staging" / str(item["id"]) / "files"
        stale.mkdir(parents=True)
        stale.joinpath("old-extra.txt").write_bytes(b"old")
        response = self.client.post("/api/todos/%s/archive/retry" % item["id"], headers=self.access_headers)
        self.assertEqual(response.status_code, 200)
        response.close()
        self.assertFalse(stale.joinpath("old-extra.txt").exists())
        new_claim = self.claim("agent-b")
        content = b"new"
        response = self.upload(item["id"], "agent-b", new_claim["leaseToken"], "new.txt", content)
        self.assertEqual(response.status_code, 200)
        response.close()
        response = self.commit(item["id"], "agent-b", new_claim["leaseToken"], [{"relativePath": "new.txt", "size": 3, "sha256": hashlib.sha256(content).hexdigest()}])
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_retry_keeps_failed_state_when_staging_reset_fails(self):
        self.enable_agent()
        item = self.create_archive_pending("Retry remains failed")
        claim = self.claim()
        self.client.post(
            "/api/agent/jobs/%s/fail" % item["id"],
            json={"error": "copy interrupted"},
            headers=self.agent_headers("agent-a", claim["leaseToken"]),
        ).close()
        with patch.object(server.ArchiveStorage, "reset_locked", side_effect=OSError("reset denied"), create=True):
            response = self.client.post("/api/todos/%s/archive/retry" % item["id"], headers=self.access_headers)
        self.assertEqual(response.status_code, 400)
        response.close()
        with server.app.app_context():
            self.assertEqual(server.find_todo(item["id"])["archiveStatus"], "failed")

    def test_upload_rechecks_lease_after_waiting_for_task_lock(self):
        self.enable_agent(); item = self.create_archive_pending("Lease changes while waiting"); claim = self.claim()
        storage = server.archive_storage(); result = {}
        with storage.task_lock(item["id"]):
            def upload_in_thread():
                client = server.app.test_client()
                result["response"] = client.put(
                    "/api/agent/jobs/%s/files" % item["id"],
                    data={"relativePath": "late.txt", "expectedSize": "4", "expectedSha256": hashlib.sha256(b"late").hexdigest(), "file": (io.BytesIO(b"late"), "late.txt")},
                    headers=self.agent_headers("agent-a", claim["leaseToken"]), content_type="multipart/form-data")
            worker = threading.Thread(target=upload_in_thread); worker.start(); time.sleep(0.15)
            with server.app.app_context():
                stale = server.find_todo(item["id"]); stale["archiveLeaseUntil"] = "2000-01-01T00:00:00"; server.save_todo(stale)
        worker.join(5)
        self.assertEqual(result["response"].status_code, 409)

    def test_finish_rechecks_lease_after_waiting_for_task_lock(self):
        self.enable_agent()
        item = self.create_archive_pending("Finish lease changes while waiting")
        claim = self.claim()
        response = self.commit(item["id"], "agent-a", claim["leaseToken"], [])
        self.assertEqual(response.status_code, 200)
        response.close()

        storage = server.archive_storage()
        acquire_attempted = threading.Event()
        original_task_lock = storage.task_lock
        result = {}

        @contextlib.contextmanager
        def observed_task_lock(todo_id):
            acquire_attempted.set()
            with original_task_lock(todo_id):
                yield

        def finish_in_thread():
            client = server.app.test_client()
            response = client.post(
                "/api/agent/jobs/%s/finish" % item["id"],
                headers=self.agent_headers("agent-a", claim["leaseToken"]),
            )
            result["status_code"] = response.status_code
            response.close()

        with patch.object(server, "archive_storage", return_value=storage), patch.object(
            storage, "task_lock", new=observed_task_lock
        ):
            with original_task_lock(item["id"]):
                worker = threading.Thread(target=finish_in_thread)
                worker.start()
                self.assertTrue(acquire_attempted.wait(2), "finish never attempted the task lock")
                with server.app.app_context():
                    replaced = server.find_todo(item["id"])
                    replaced["archiveAgentId"] = "agent-b"
                    replaced["archiveLeaseToken"] = "replacement-token"
                    replaced["archiveLeaseUntil"] = server.utc_timestamp(
                        server.utc_now() + server.ARCHIVE_LEASE_DURATION
                    )
                    server.save_todo(replaced)
            worker.join(5)

        self.assertFalse(worker.is_alive())
        self.assertEqual(result["status_code"], 409)
        with server.app.app_context():
            unchanged = server.find_todo(item["id"])
        self.assertEqual(unchanged["status"], "archive_pending")
        self.assertEqual(unchanged["archiveStatus"], "committed")
        self.assertTrue((server.TODO_DIR / item["folderName"] / "TODO.md").is_file())
        self.assertFalse((server.DONE_DIR / item["folderName"] / "TODO.md").exists())

    def test_agent_routes_handle_task_lock_entry_failure_without_state_change(self):
        self.enable_agent()
        item = self.create_archive_pending("Unsafe task lock")
        claim = self.claim()
        response = self.commit(item["id"], "agent-a", claim["leaseToken"], [])
        self.assertEqual(response.status_code, 200)
        response.close()

        previous_propagation = server.app.config.get("PROPAGATE_EXCEPTIONS")
        self.addCleanup(
            server.app.config.__setitem__, "PROPAGATE_EXCEPTIONS", previous_propagation
        )
        server.app.config["PROPAGATE_EXCEPTIONS"] = False
        with patch.object(
            server.ArchiveStorage,
            "task_lock",
            side_effect=ValueError("Archive lock directory is unsafe"),
        ):
            responses = [
                self.upload(
                    item["id"],
                    "agent-a",
                    claim["leaseToken"],
                    "late.txt",
                    b"late",
                ),
                self.commit(item["id"], "agent-a", claim["leaseToken"], []),
                self.client.post(
                    "/api/agent/jobs/%s/finish" % item["id"],
                    headers=self.agent_headers("agent-a", claim["leaseToken"]),
                ),
            ]

        try:
            self.assertEqual([response.status_code for response in responses], [400, 400, 400])
        finally:
            for response in responses:
                response.close()
        with server.app.app_context():
            unchanged = server.find_todo(item["id"])
        self.assertEqual(unchanged["status"], "archive_pending")
        self.assertEqual(unchanged["archiveStatus"], "committed")
        self.assertTrue((server.TODO_DIR / item["folderName"] / "TODO.md").is_file())
        self.assertFalse((server.DONE_DIR / item["folderName"] / "TODO.md").exists())

    def test_finish_task_lock_timeout_returns_503_without_state_change(self):
        self.enable_agent()
        item = self.create_archive_pending("Finish task lock timeout")
        claim = self.claim()
        response = self.commit(item["id"], "agent-a", claim["leaseToken"], [])
        self.assertEqual(response.status_code, 200)
        response.close()

        source_markdown = server.TODO_DIR / item["folderName"] / "TODO.md"
        target_markdown = server.DONE_DIR / item["folderName"] / "TODO.md"
        self.assertTrue(source_markdown.is_file())
        self.assertFalse(target_markdown.exists())

        with patch.object(
            server.ArchiveStorage,
            "task_lock",
            side_effect=TimeoutError("Timed out waiting for archive task lock"),
        ):
            response = self.client.post(
                "/api/agent/jobs/%s/finish" % item["id"],
                headers=self.agent_headers("agent-a", claim["leaseToken"]),
            )

        self.assertEqual(response.status_code, 503)
        response.close()
        with server.app.app_context():
            unchanged = server.find_todo(item["id"])
        self.assertEqual(unchanged["status"], "archive_pending")
        self.assertEqual(unchanged["archiveStatus"], "committed")
        self.assertTrue(source_markdown.is_file())
        self.assertFalse(target_markdown.exists())

    def test_finish_preflights_conflicts_and_repairs_final_markdown_idempotently(self):
        self.enable_agent()
        item = self.create_archive_pending("Move safely", screenshot=True)
        claim = self.claim()
        response = self.commit(item["id"], "agent-a", claim["leaseToken"], [])
        self.assertEqual(response.status_code, 200)
        response.close()
        source = server.TODO_DIR / item["folderName"]
        target = server.DONE_DIR / item["folderName"]
        (target / "screenshot.png").write_bytes(b"conflicting screenshot")
        response = self.client.post(
            "/api/agent/jobs/%s/finish" % item["id"],
            headers=self.agent_headers("agent-a", claim["leaseToken"]),
        )
        self.assertEqual(response.status_code, 400)
        response.close()
        self.assertTrue((source / "TODO.md").is_file())
        self.assertTrue((source / "screenshot.png").is_file())
        (target / "screenshot.png").unlink()
        with server.app.app_context():
            recovered_markdown = dict(server.find_todo(item["id"]))
        recovered_markdown.update(status="done", progress=100)
        (target / "TODO.md").write_text(server.todo_markdown(recovered_markdown), encoding="utf-8")
        response = self.client.post(
            "/api/agent/jobs/%s/finish" % item["id"],
            headers=self.agent_headers("agent-a", claim["leaseToken"]),
        )
        self.assertEqual(response.status_code, 200)
        finished = response.get_json()["item"]
        response.close()
        final_markdown = target / "TODO.md"
        self.assertTrue(final_markdown.is_file())
        self.assertIn("- Status: done", final_markdown.read_text(encoding="utf-8"))
        final_markdown.unlink()
        response = self.client.post(
            "/api/agent/jobs/%s/finish" % item["id"],
            headers=self.agent_headers("agent-a", claim["leaseToken"]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["item"]["id"], finished["id"])
        response.close()
        self.assertTrue(final_markdown.is_file())


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

    def test_project_and_todo_flow_exposes_local_path_but_hides_nas_path(self):
        access_headers = {"Cf-Access-Authenticated-User-Email": "owner@example.com"}
        project_dir = Path(self.temp_dir.name) / "project"
        local_dir = Path(self.temp_dir.name) / "local-project"
        project_dir.mkdir()
        local_dir.mkdir()
        response = self.client.post(
            "/api/projects",
            json={
                "name": "Private project",
                "localPath": str(local_dir),
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
        self.assertEqual(response.json["item"]["localPath"], str(local_dir))

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

    def test_project_open_launches_existing_local_path(self):
        access_headers = {"Cf-Access-Authenticated-User-Email": "owner@example.com"}
        local_dir = Path(self.temp_dir.name) / "local-project"
        local_dir.mkdir()
        response = self.client.post(
            "/api/projects",
            json={
                "name": "Openable project",
                "localPath": str(local_dir),
                "gitRepo": "",
                "created": "2026-07-13",
            },
            headers=access_headers,
        )
        self.assertEqual(response.status_code, 200)

        with patch("server.open_path_in_explorer") as opener:
            response = self.client.post("/api/project/1/open", headers=access_headers)

        self.assertEqual(response.status_code, 200)
        expected_path = local_dir.resolve(strict=False)
        self.assertEqual(response.json["path"], str(expected_path))
        opener.assert_called_once_with(expected_path)

    def test_project_details_can_be_loaded_and_updated_without_exposing_paths_in_list(self):
        access_headers = {"Cf-Access-Authenticated-User-Email": "owner@example.com"}
        first_local = Path(self.temp_dir.name) / "first-local"
        second_local = Path(self.temp_dir.name) / "second-local"
        first_local.mkdir()
        second_local.mkdir()
        create_response = self.client.post(
            "/api/projects",
            json={
                "name": "Editable project",
                "localPath": str(first_local),
                "nasPath": r"\\nas\projects\editable",
                "gitRepo": str(first_local / "repo"),
                "created": "2026-08-20",
                "tags": "old, vision",
                "categories": "source",
                "description": "Original description",
            },
            headers=access_headers,
        )
        self.assertEqual(create_response.status_code, 200)
        project_id = create_response.get_json()["item"]["id"]
        create_response.close()

        details_response = self.client.get(
            "/api/projects/%s" % project_id, headers=access_headers
        )
        self.assertEqual(details_response.status_code, 200)
        details = details_response.get_json()
        details_response.close()
        self.assertEqual(details["nasPath"], r"\\nas\projects\editable")
        self.assertEqual(details["gitRepo"], str(first_local / "repo"))

        update_response = self.client.patch(
            "/api/projects/%s" % project_id,
            json={
                "name": "Edited project",
                "localPath": str(second_local),
                "nasPath": r"\\nas\projects\edited",
                "gitRepo": str(second_local / "repo"),
                "created": "2026-08-29",
                "tags": "edited, Git",
                "categories": "archive, local",
                "description": "Updated description",
            },
            headers=access_headers,
        )
        self.assertEqual(update_response.status_code, 200)
        updated = update_response.get_json()["item"]
        update_response.close()
        self.assertEqual(updated["name"], "Edited project")
        self.assertEqual(updated["localPath"], str(second_local))
        self.assertEqual(updated["nasPath"], r"\\nas\projects\edited")
        self.assertEqual(updated["gitRepo"], str(second_local / "repo"))
        self.assertEqual(updated["tags"], ["edited", "Git"])
        self.assertEqual(updated["categories"], ["archive", "local"])
        self.assertEqual(updated["description"], "Updated description")

        list_response = self.client.get("/api/projects", headers=access_headers)
        self.assertEqual(list_response.status_code, 200)
        listed = list_response.get_json()[0]
        list_response.close()
        self.assertNotIn("nasPath", listed)
        self.assertNotIn("gitRepo", listed)

    def test_project_update_rejects_duplicate_project_name(self):
        access_headers = {"Cf-Access-Authenticated-User-Email": "owner@example.com"}
        first = self.client.post(
            "/api/projects",
            json={"name": "First project", "localPath": "D:\\first", "created": "2026-08-20"},
            headers=access_headers,
        )
        second = self.client.post(
            "/api/projects",
            json={"name": "Second project", "localPath": "D:\\second", "created": "2026-08-21"},
            headers=access_headers,
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        first_id = first.get_json()["item"]["id"]
        first.close()
        second.close()

        duplicate = self.client.patch(
            "/api/projects/%s" % first_id,
            json={"name": "Second project", "localPath": "D:\\first", "created": "2026-08-20"},
            headers=access_headers,
        )

        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.get_json()["error"], "Project name already exists")
        duplicate.close()

    def test_knowledge_items_create_list_and_open_local_path(self):
        access_headers = {"Cf-Access-Authenticated-User-Email": "owner@example.com"}
        local_dir = Path(self.temp_dir.name) / "knowledge-doc"
        local_dir.mkdir()

        created = self.client.post(
            "/api/knowledge",
            json={
                "name": "VisionX 通讯调试说明",
                "type": "internal_docs",
                "localPath": str(local_dir),
            },
            headers=access_headers,
        )
        self.assertEqual(created.status_code, 200)
        item = created.get_json()["item"]
        created.close()
        self.assertEqual(item["name"], "VisionX 通讯调试说明")
        self.assertEqual(item["type"], "internal_docs")
        self.assertEqual(item["typeLabel"], "内部技术文档")
        self.assertEqual(item["localPath"], str(local_dir))

        listed = self.client.get("/api/knowledge", headers=access_headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()[0]["name"], "VisionX 通讯调试说明")
        listed.close()

        with patch("server.open_path_in_explorer") as opener:
            opened = self.client.post("/api/knowledge/%s/open" % item["id"], headers=access_headers)
        self.assertEqual(opened.status_code, 200)
        opener.assert_called_once_with(local_dir.resolve(strict=False))
        opened.close()

    def test_knowledge_items_reject_unknown_type_and_require_path(self):
        access_headers = {"Cf-Access-Authenticated-User-Email": "owner@example.com"}
        invalid_type = self.client.post(
            "/api/knowledge",
            json={"name": "Unknown", "type": "other", "localPath": "D:\\docs"},
            headers=access_headers,
        )
        self.assertEqual(invalid_type.status_code, 400)
        self.assertEqual(invalid_type.get_json()["error"], "Knowledge type is invalid")
        invalid_type.close()

        missing_path = self.client.post(
            "/api/knowledge",
            json={"name": "No path", "type": "skill_packages", "localPath": ""},
            headers=access_headers,
        )
        self.assertEqual(missing_path.status_code, 400)
        self.assertEqual(missing_path.get_json()["error"], "Knowledge local path is required")
        missing_path.close()

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

    def test_import_local_task_folders_reads_only_date_folders_and_is_idempotent(self):
        access_headers = {"Cf-Access-Authenticated-User-Email": "owner@example.com"}
        root = Path(self.temp_dir.name) / "worklogs"
        task_dir = root / "20260824" / "1.去石岩欣旺达处理SVB工程CT问题，排查通讯延时问题"
        ignored_dir = root / "测试透明管" / "不应导入"
        task_dir.mkdir(parents=True)
        ignored_dir.mkdir(parents=True)
        (task_dir / "WorkLog.txt").write_text(
            "现场复现通讯延时，确认等待机制需要调整。\n补充抓取日志和复盘结论。",
            encoding="utf-8",
        )
        (ignored_dir / "WorkLog.txt").write_text("非日期目录不导入", encoding="utf-8")

        response = self.client.post(
            "/api/import/local-tasks",
            json={"rootPath": str(root)},
            headers=access_headers,
        )

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["ignoredDateFolders"], ["测试透明管"])
        imported = result["items"][0]
        self.assertEqual(imported["name"], "1.去石岩欣旺达处理SVB工程CT问题，排查通讯延时问题")
        self.assertEqual(imported["taskDate"], "2026-08-24")
        self.assertEqual(imported["status"], "done")
        self.assertEqual(imported["completedAt"], "2026-08-24T23:59:00")
        self.assertEqual(imported["localPath"], str(task_dir.resolve(strict=False)))
        self.assertIn("现场复现通讯延时", imported["notes"])
        self.assertIn("现场复现通讯延时", imported["resultDescription"])

        duplicate = self.client.post(
            "/api/import/local-tasks",
            json={"rootPath": str(root)},
            headers=access_headers,
        )
        self.assertEqual(duplicate.status_code, 200)
        duplicate_result = duplicate.get_json()
        self.assertEqual(duplicate_result["imported"], 0)
        self.assertEqual(duplicate_result["skipped"], 1)

        todos = self.client.get("/api/todos", headers=access_headers).get_json()
        self.assertEqual(len(todos["todo"]), 0)
        self.assertEqual(len(todos["done"]), 1)

    def test_ai_settings_are_saved_without_exposing_full_key(self):
        access_headers = {"Cf-Access-Authenticated-User-Email": "owner@example.com"}
        response = self.client.post(
            "/api/settings/ai",
            json={
                "apiKey": "sk-test-123456789",
                "baseUrl": "https://api.deepseek.com/v1",
                "model": "deepseek-chat",
            },
            headers=access_headers,
        )

        self.assertEqual(response.status_code, 200)
        settings = response.get_json()["settings"]
        self.assertTrue(settings["hasApiKey"])
        self.assertEqual(settings["keyPreview"], "sk-...789")
        self.assertNotIn("apiKey", settings)

        loaded = self.client.get("/api/settings/ai", headers=access_headers).get_json()
        self.assertEqual(loaded["keyPreview"], "sk-...789")
        self.assertNotIn("apiKey", loaded)

    def test_summary_context_includes_pending_and_completed_task_details(self):
        access_headers = {"Cf-Access-Authenticated-User-Email": "owner@example.com"}
        self.client.post(
            "/api/todos",
            json={
                "name": "待处理视觉问题",
                "notes": "需要复测曝光参数。",
                "taskDate": datetime.now().strftime("%Y-%m-%d"),
            },
            headers=access_headers,
        )
        root = Path(self.temp_dir.name) / "worklogs"
        imported_task = root / datetime.now().strftime("%Y%m%d") / "已处理通讯延时"
        imported_task.mkdir(parents=True)
        (imported_task / "WorkLog.txt").write_text(
            "调整等待机制，延时问题关闭。", encoding="utf-8"
        )
        self.client.post(
            "/api/import/local-tasks",
            json={"rootPath": str(root)},
            headers=access_headers,
        )

        context = self.client.get(
            "/api/summary/context?period=today", headers=access_headers
        ).get_json()

        self.assertEqual(context["tasks"]["pending"][0]["name"], "待处理视觉问题")
        self.assertIn("复测曝光参数", context["tasks"]["pending"][0]["notes"])
        self.assertEqual(context["tasks"]["completed"][0]["name"], "已处理通讯延时")
        self.assertIn("延时问题关闭", context["tasks"]["completed"][0]["resultDescription"])

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

