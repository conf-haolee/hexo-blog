"""workboard:// protocol parsing and Explorer launch helpers."""

import argparse
import json
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    from .paths import resolve_task_path
except ImportError:
    from paths import resolve_task_path


_VALIDATION_ROOT = Path(r"C:\__workboard_protocol_root__").resolve(strict=False)


def parse_protocol_url(url: str) -> tuple[int | None, str]:
    parsed = urlparse(str(url or ""))
    if parsed.scheme != "workboard" or parsed.netloc != "open":
        raise ValueError("Unsupported Workboard protocol URL")
    query = parse_qs(parsed.query, keep_blank_values=True)
    todo_id = _parse_todo_id(query.get("todoId", [""])[0])
    raw_path = query.get("path", [""])[0]
    resolved = resolve_task_path(_VALIDATION_ROOT, raw_path)
    if resolved == _VALIDATION_ROOT:
        return todo_id, ""
    return todo_id, resolved.relative_to(_VALIDATION_ROOT).as_posix()


def open_protocol_url(url: str, root: Path) -> Path:
    _todo_id, stored_path = parse_protocol_url(url)
    target = resolve_task_path(root, stored_path)
    subprocess.Popen(["explorer.exe", str(target)])
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description="Open a workboard:// URL in Explorer.")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("url")
    args = parser.parse_args(argv)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    open_protocol_url(args.url, Path(config.get("rootPath", r"D:\01WorkBoard")))


def _parse_todo_id(value: str) -> int | None:
    value = str(value or "").strip()
    if not value:
        return None
    try:
        todo_id = int(value)
    except ValueError as exc:
        raise ValueError("Invalid Workboard task id") from exc
    if todo_id <= 0:
        raise ValueError("Invalid Workboard task id")
    return todo_id


if __name__ == "__main__":
    main()
