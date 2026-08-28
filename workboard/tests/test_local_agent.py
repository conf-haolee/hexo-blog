import hashlib
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import local_agent.agent as agent
from local_agent.archive_record import write_archive_record
from local_agent.client import ArchiveClient
from local_agent.paths import collect_task_files, resolve_task_path
from local_agent.protocol import parse_protocol_url


class LocalAgentPathTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_resolve_task_path_accepts_empty_and_relative_paths_under_root(self):
        nested = self.root / "ProjectA" / "Task01"
        nested.mkdir(parents=True)

        self.assertEqual(resolve_task_path(self.root, ""), self.root.resolve())
        self.assertEqual(resolve_task_path(self.root, "ProjectA/Task01"), nested.resolve())
        self.assertEqual(resolve_task_path(self.root, r"ProjectA\Task01"), nested.resolve())

    def test_resolve_task_path_rejects_traversal_and_absolute_paths(self):
        for stored_path in ("../secret", "ProjectA/../../secret", r"C:\secret", r"\\nas\share\task"):
            with self.subTest(stored_path=stored_path):
                with self.assertRaises(ValueError):
                    resolve_task_path(self.root, stored_path)

    def test_collect_task_files_hashes_files_and_excludes_archive(self):
        task = self.root / "TaskA"
        task.mkdir()
        (task / "result.txt").write_bytes(b"done")
        (task / "nested").mkdir()
        (task / "nested" / "notes.txt").write_text("notes", encoding="utf-8")
        (self.root / "archive" / "2026").mkdir(parents=True)
        (self.root / "archive" / "2026" / "old.txt").write_text("old", encoding="utf-8")

        entries = collect_task_files(self.root, task)

        by_path = {entry.relative_path: entry for entry in entries}
        self.assertEqual(set(by_path), {"nested/notes.txt", "result.txt"})
        self.assertEqual(by_path["result.txt"].size, 4)
        self.assertEqual(by_path["result.txt"].sha256, hashlib.sha256(b"done").hexdigest())

    def test_collect_task_files_rejects_links(self):
        task = self.root / "TaskA"
        task.mkdir()
        outside = self.root / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        try:
            os.symlink(outside, task / "link.txt")
        except OSError as exc:
            self.skipTest(f"symbolic links unavailable: {exc}")
        with self.assertRaises(ValueError):
            collect_task_files(self.root, task)


class LocalAgentArchiveRecordTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_write_archive_record_contains_text_fields_and_excludes_screenshot_fields(self):
        task = {
            "id": 42,
            "name": 'Bad<>:"/\\|?* Name',
            "projectName": "Vision Project",
            "projectNumber": "VX-001",
            "contact": "Owner",
            "notes": "Archive notes",
            "resultDescription": "Finished with local evidence.",
            "localPath": "TaskA",
            "taskDate": "2026-08-25",
            "createdAt": "2026-08-25T09:30:00",
            "completedAt": "2026-08-25T10:30:00",
            "archiveStatus": "committed",
            "archiveError": "",
            "archiveCompletedAt": "2026-08-25T10:31:00",
            "screenshotName": "secret.png",
            "screenshotMime": "image/png",
            "screenshotUrl": "/api/todos/42/screenshot",
        }

        record = write_archive_record(self.root, task)

        self.assertEqual(record.parent, self.root.resolve() / "archive" / "2026" / "202608")
        self.assertTrue(record.name.startswith("20260825_093000_"))
        self.assertNotRegex(record.name, r'[<>:"/\\|?*]')
        content = record.read_text(encoding="utf-8")
        for expected in (
            "Bad<>:\"/\\|?* Name",
            "Vision Project",
            "VX-001",
            "Owner",
            "Archive notes",
            "Finished with local evidence.",
            "TaskA",
            "2026-08-25T10:31:00",
        ):
            self.assertIn(expected, content)
        self.assertNotIn("secret.png", content)
        self.assertNotIn("screenshot", content.lower())
        self.assertFalse(list(record.parent.glob("*.tmp")))

    def test_write_archive_record_appends_task_id_on_collision(self):
        task = {
            "id": 42,
            "name": "Duplicate",
            "createdAt": "2026-08-25T09:30:00",
        }

        first = write_archive_record(self.root, task)
        second = write_archive_record(self.root, task)

        self.assertNotEqual(first, second)
        self.assertIn("_42", second.stem)
        self.assertEqual(first.read_text(encoding="utf-8"), second.read_text(encoding="utf-8"))


class FakeArchiveClient:
    def __init__(self, fail_at=None):
        self.fail_at = fail_at
        self.events = []

    def upload_file(self, todo_id, lease_token, relative_path, stream, size, sha256):
        content = stream.read()
        self.events.append(("upload", todo_id, lease_token, relative_path, size, hashlib.sha256(content).hexdigest()))
        if self.fail_at == "upload":
            raise RuntimeError("upload failed")
        self.assert_integrity(content, size, sha256)

    def commit(self, todo_id, lease_token, manifest):
        self.events.append(("commit", todo_id, lease_token, manifest))
        if self.fail_at == "commit":
            raise RuntimeError("commit failed")

    def finish(self, todo_id, lease_token):
        self.events.append(("finish", todo_id, lease_token))

    def fail(self, todo_id, lease_token, error):
        self.events.append(("fail", todo_id, lease_token, error))

    @staticmethod
    def assert_integrity(content, size, sha256):
        if len(content) != size or hashlib.sha256(content).hexdigest() != sha256:
            raise AssertionError("fake client received mismatched integrity fields")


class LocalAgentWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.task_dir = self.root / "TaskA"
        self.task_dir.mkdir()
        (self.task_dir / "a.txt").write_bytes(b"a")
        (self.task_dir / "nested").mkdir()
        (self.task_dir / "nested" / "b.txt").write_bytes(b"bb")
        self.job = {
            "id": 42,
            "leaseToken": "lease-42",
            "name": "TaskA",
            "projectName": "Vision",
            "createdAt": "2026-08-25T09:30:00",
            "localPath": "TaskA",
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_process_job_uploads_commits_records_cleans_sources_and_finishes(self):
        client = FakeArchiveClient()

        agent.process_job(client, self.root, self.job)

        self.assertEqual([event[0] for event in client.events], ["upload", "upload", "commit", "finish"])
        self.assertEqual(client.events[0][3], "a.txt")
        self.assertEqual(client.events[1][3], "nested/b.txt")
        manifest = client.events[2][3]
        self.assertEqual([item["relativePath"] for item in manifest], ["a.txt", "nested/b.txt"])
        self.assertFalse(self.task_dir.exists())
        records = list((self.root / "archive" / "2026" / "202608").glob("*.txt"))
        self.assertEqual(len(records), 1)
        self.assertIn("TaskA", records[0].read_text(encoding="utf-8"))

    def test_process_job_copies_task_to_nas_archive_before_cleaning_sources(self):
        client = FakeArchiveClient()
        nas_root = self.root / "nas-archive"

        agent.process_job(client, self.root, self.job, nas_archive_path=nas_root)

        archived_files = sorted(path.relative_to(nas_root).as_posix() for path in nas_root.rglob("*") if path.is_file())
        self.assertEqual(
            archived_files,
            [
                "2026/202608/20260825_093000_TaskA_42/a.txt",
                "2026/202608/20260825_093000_TaskA_42/nested/b.txt",
            ],
        )
        self.assertFalse(self.task_dir.exists())
        self.assertEqual(client.events[-1][0], "finish")

    def test_process_job_keeps_sources_and_reports_failure_when_nas_archive_copy_fails(self):
        client = FakeArchiveClient()
        blocked_nas_root = self.root / "blocked-nas"
        blocked_nas_root.write_text("not a directory", encoding="utf-8")

        agent.process_job(client, self.root, self.job, nas_archive_path=blocked_nas_root)

        self.assertTrue((self.task_dir / "a.txt").is_file())
        self.assertEqual(client.events[-1][0], "fail")
        self.assertFalse(any(event[0] == "commit" for event in client.events))
        self.assertFalse(any(event[0] == "finish" for event in client.events))

    def test_process_job_reports_missing_directory_without_uploading(self):
        client = FakeArchiveClient()
        self.job["localPath"] = "Missing"

        agent.process_job(client, self.root, self.job)

        self.assertEqual(client.events[0][0], "fail")
        self.assertEqual(len(client.events), 1)
        self.assertTrue(self.task_dir.exists())

    def test_process_job_leaves_sources_when_upload_commit_or_record_fails(self):
        for fail_at in ("upload", "commit", "record"):
            with self.subTest(fail_at=fail_at):
                with tempfile.TemporaryDirectory() as case_dir:
                    root = Path(case_dir)
                    task_dir = root / "TaskA"
                    task_dir.mkdir()
                    (task_dir / "a.txt").write_bytes(b"a")
                    job = dict(self.job)
                    client = FakeArchiveClient(fail_at=fail_at)
                    if fail_at == "record":
                        (root / "archive").write_text("not a directory", encoding="utf-8")

                    agent.process_job(client, root, job)

                    self.assertTrue((task_dir / "a.txt").is_file())
                    self.assertEqual(client.events[-1][0], "fail")
                    self.assertFalse(any(event[0] == "finish" for event in client.events))


class RecordingHandler(BaseHTTPRequestHandler):
    records = []

    def do_POST(self):
        self._handle()

    def do_PUT(self):
        self._handle()

    def log_message(self, _format, *args):
        pass

    def _handle(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.records.append((self.command, self.path, dict(self.headers), body))
        if self.path == "/api/agent/jobs/500/fail":
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"error":"secret-token leaked"}')
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"success":true,"leaseToken":"lease-1","job":null}')


class LocalAgentClientTest(unittest.TestCase):
    def setUp(self):
        RecordingHandler.records = []
        self.server = HTTPServer(("127.0.0.1", 0), RecordingHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = ArchiveClient(
            f"http://127.0.0.1:{self.server.server_address[1]}",
            "secret-token",
            "agent-a",
        )

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(5)
        self.server.server_close()

    def test_archive_client_sends_agent_routes_and_headers(self):
        self.client.claim()
        self.client.upload_file(42, "lease-1", "a.txt", io.BytesIO(b"a"), 1, hashlib.sha256(b"a").hexdigest())
        self.client.commit(42, "lease-1", [{"relativePath": "a.txt", "size": 1, "sha256": hashlib.sha256(b"a").hexdigest()}])
        self.client.finish(42, "lease-1")

        self.assertEqual(
            [(record[0], record[1]) for record in RecordingHandler.records],
            [
                ("POST", "/api/agent/jobs/claim"),
                ("PUT", "/api/agent/jobs/42/files"),
                ("POST", "/api/agent/jobs/42/commit"),
                ("POST", "/api/agent/jobs/42/finish"),
            ],
        )
        upload_headers = RecordingHandler.records[1][2]
        self.assertEqual(upload_headers["Authorization"], "Bearer secret-token")
        self.assertEqual(upload_headers["X-Workboard-Agent-Id"], "agent-a")
        self.assertEqual(upload_headers["X-Workboard-Lease-Token"], "lease-1")
        upload_body = RecordingHandler.records[1][3]
        self.assertIn(b'name="relativePath"', upload_body)
        self.assertIn(b"a.txt", upload_body)

    def test_archive_client_redacts_token_from_http_error_body(self):
        with self.assertRaises(RuntimeError) as context:
            self.client.fail(500, "lease-1", "boom")

        self.assertNotIn("secret-token", str(context.exception))


class LocalAgentProtocolTest(unittest.TestCase):
    def test_parse_protocol_url_accepts_empty_unicode_and_percent_encoded_paths(self):
        self.assertEqual(parse_protocol_url("workboard://open"), (None, ""))
        self.assertEqual(
            parse_protocol_url("workboard://open?todoId=42&path=Task%20A%2FResult"),
            (42, "Task A/Result"),
        )
        self.assertEqual(
            parse_protocol_url("workboard://open?path=%E9%A1%B9%E7%9B%AE%2F%E4%BB%BB%E5%8A%A1&unused=1"),
            (None, "项目/任务"),
        )

    def test_parse_protocol_url_rejects_malformed_traversal_and_absolute_paths(self):
        for url in (
            "https://example.com/open?path=TaskA",
            "workboard://finish?path=TaskA",
            "workboard://open?path=..%2Fsecret",
            "workboard://open?path=C%3A%5Csecret",
            "workboard://open?path=%5C%5Cnas%5Cshare%5Ctask",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    parse_protocol_url(url)


if __name__ == "__main__":
    unittest.main()
