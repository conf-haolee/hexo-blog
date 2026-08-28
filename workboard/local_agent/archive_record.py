"""Local TXT archive record writer for completed Workboard tasks."""

from datetime import datetime
import os
import re
from pathlib import Path


_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')
_TEXT_FIELDS = (
    ("Task ID", "id"),
    ("Name", "name"),
    ("Project", "projectName"),
    ("Project number", "projectNumber"),
    ("Contact", "contact"),
    ("Task date", "taskDate"),
    ("Created at", "createdAt"),
    ("Completed at", "completedAt"),
    ("Archive completed at", "archiveCompletedAt"),
    ("Archive status", "archiveStatus"),
    ("Archive error", "archiveError"),
    ("Local path", "localPath"),
    ("Notes", "notes"),
    ("Result description", "resultDescription"),
)


def write_archive_record(root: Path, task: dict) -> Path:
    root = Path(root).resolve(strict=False)
    created = _parse_timestamp(task.get("createdAt"))
    directory = root / "archive" / created.strftime("%Y") / created.strftime("%Y%m")
    directory.mkdir(parents=True, exist_ok=True)
    target = _record_path(directory, created, task)
    temporary = target.with_name(f"{target.name}.tmp")
    content = _render_record(task)

    with temporary.open("w", encoding="utf-8", newline="\n") as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, target)
    return target


def _record_path(directory: Path, created: datetime, task: dict) -> Path:
    safe_name = _sanitize_filename(str(task.get("name") or "task"))
    prefix = f"{created.strftime('%Y%m%d_%H%M%S')}_{safe_name}"
    candidate = directory / f"{prefix}.txt"
    if not candidate.exists():
        return candidate
    task_id = _sanitize_filename(str(task.get("id") or "task"))
    candidate = directory / f"{prefix}_{task_id}.txt"
    index = 2
    while candidate.exists():
        candidate = directory / f"{prefix}_{task_id}_{index}.txt"
        index += 1
    return candidate


def _render_record(task: dict) -> str:
    lines = ["Workboard archive record", ""]
    for label, key in _TEXT_FIELDS:
        value = task.get(key)
        if value is None:
            value = ""
        lines.append(f"{label}: {value}")
    lines.append("")
    return "\n".join(lines)


def _parse_timestamp(value) -> datetime:
    if value:
        text = str(value).replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            pass
    return datetime.now()


def _sanitize_filename(value: str) -> str:
    value = _INVALID_FILENAME_CHARS.sub("_", value).strip()
    value = re.sub(r"\s+", " ", value)
    value = value.rstrip(". ")
    return value or "task"
