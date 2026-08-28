"""Copy completed Workboard task folders to a NAS archive share."""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path


def copy_task_to_nas_archive(task_path: Path, task: dict, nas_archive_path: Path, entries) -> Path:
    """Copy a task folder into ``nas_archive_path/YYYY/YYYYMM/<task-folder>``.

    The caller supplies ``entries`` from ``collect_task_files`` so link and
    traversal checks stay centralized in ``paths.py``.
    """

    target = _unique_target(Path(nas_archive_path), task)
    for entry in entries:
        source = Path(task_path) / Path(*entry.relative_path.split("/"))
        destination = target / Path(*entry.relative_path.split("/"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return target


def _unique_target(nas_archive_path: Path, task: dict) -> Path:
    timestamp = _timestamp(task)
    year = timestamp[:4]
    month = timestamp[:6]
    task_id = str(task.get("id", "task"))
    name = _safe_name(str(task.get("name") or "task"))
    base = nas_archive_path / year / month / f"{timestamp}_{name}_{task_id}"
    target = base
    suffix = 2
    while target.exists():
        target = base.with_name(f"{base.name}-{suffix}")
        suffix += 1
    target.mkdir(parents=True, exist_ok=False)
    return target


def _timestamp(task: dict) -> str:
    value = str(task.get("createdAt") or task.get("created_at") or "")
    if value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y%m%d_%H%M%S")
        except ValueError:
            pass
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_name(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" ._")
    return cleaned[:80] or "task"
