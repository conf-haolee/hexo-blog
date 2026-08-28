"""Polling workflow for the Workboard Windows archive helper."""

import argparse
import json
import logging
import time
from pathlib import Path

from .archive_record import write_archive_record
from .client import ArchiveClient
from .nas_archive import copy_task_to_nas_archive
from .paths import collect_task_files, is_link_or_reparse, resolve_task_path


def process_job(client, root: Path, job: dict, nas_archive_path: Path | None = None) -> None:
    todo_id = job["id"]
    lease_token = job.get("leaseToken") or job.get("archiveLeaseToken") or ""
    try:
        task_path = resolve_task_path(root, job.get("localPath", ""))
        entries = collect_task_files(root, task_path)
        manifest = []
        for entry in entries:
            source = task_path / Path(*entry.relative_path.split("/"))
            with source.open("rb") as stream:
                client.upload_file(todo_id, lease_token, entry.relative_path, stream, entry.size, entry.sha256)
            manifest.append({"relativePath": entry.relative_path, "size": entry.size, "sha256": entry.sha256})
        if nas_archive_path:
            copy_task_to_nas_archive(task_path, job, nas_archive_path, entries)
        client.commit(todo_id, lease_token, manifest)
        write_archive_record(root, job)
        _delete_task_contents(root, task_path)
        client.finish(todo_id, lease_token)
        logging.info("Archived Workboard task %s from %s", todo_id, task_path)
    except Exception as exc:
        logging.exception("Failed to archive Workboard task %s", todo_id)
        _report_failure(client, todo_id, lease_token, exc)


def poll(client, root: Path, once: bool = False, nas_archive_path: Path | None = None) -> None:
    delay = 5
    lease_token = None
    while True:
        try:
            result = client.claim(lease_token)
            lease_token = result.get("leaseToken") or lease_token
            job = result.get("job")
            if job:
                job["leaseToken"] = lease_token
                process_job(client, root, job, nas_archive_path=nas_archive_path)
                delay = 5
        except Exception:
            logging.exception("Workboard archive polling failed")
            delay = min(max(delay, 5) * 2, 60)
        if once:
            return
        time.sleep(delay)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the Workboard local archive helper.")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    configure_logging(config.get("logPath"))
    client = ArchiveClient(config["workboardUrl"], config["agentToken"], config.get("agentId", "workboard-local-agent"))
    nas_archive_path = config.get("nasArchivePath")
    poll(
        client,
        Path(config.get("rootPath", r"D:\01WorkBoard")),
        once=args.once,
        nas_archive_path=Path(nas_archive_path) if nas_archive_path else None,
    )


def configure_logging(log_path=None):
    if not log_path:
        logging.basicConfig(level=logging.INFO)
        return
    path = Path(log_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=path, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _report_failure(client, todo_id, lease_token, exc):
    try:
        client.fail(todo_id, lease_token, _redact(str(exc)))
    except Exception:
        pass


def _redact(message: str) -> str:
    return message.replace("\r", " ").replace("\n", " ")[:1000]


def _delete_task_contents(root: Path, task_path: Path) -> None:
    root = Path(root).resolve(strict=False)
    task_path = Path(task_path).resolve(strict=False)
    archive_path = (root / "archive").resolve(strict=False)
    if task_path == archive_path or task_path.is_relative_to(archive_path):
        raise ValueError("Archive directory must not be deleted")
    if task_path == root:
        for child in list(task_path.iterdir()):
            if child.resolve(strict=False) == archive_path:
                continue
            _delete_child(child)
        return
    _delete_child(task_path)


def _delete_child(path: Path) -> None:
    if is_link_or_reparse(path):
        raise ValueError("Symbolic links must not be deleted by the archive helper")
    if path.is_dir():
        for child in list(path.iterdir()):
            _delete_child(child)
        path.rmdir()
    elif path.exists():
        path.unlink()


if __name__ == "__main__":
    main()
