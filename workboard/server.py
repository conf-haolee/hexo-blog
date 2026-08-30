"""Private workboard service.

The service is designed to run behind a reverse proxy and an identity-aware
proxy such as Cloudflare Access. It deliberately does not expose arbitrary
filesystem browsing or local desktop actions.
"""

import json
import os
import re
import secrets
import sqlite3
import subprocess
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path, PureWindowsPath
from urllib import request as urllib_request

from flask import (
    Flask,
    g,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from archive_service import ArchiveStorage

try:
    from git import Repo

    GIT_AVAILABLE = True
except ImportError:
    Repo = None
    GIT_AVAILABLE = False


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def load_local_env_file(path):
    env_path = Path(path)
    if not env_path.exists() or not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


load_local_env_file(os.environ.get("WORKBOARD_ENV_FILE", BASE_DIR / ".env.local"))

DATA_DIR = Path(os.environ.get("WORKBOARD_DATA_DIR", BASE_DIR / "data")).resolve()
DB_PATH = Path(os.environ.get("WORKBOARD_DB", DATA_DIR / "workboard.sqlite3")).resolve()
DOCS_DIR = Path(os.environ.get("WORKBOARD_DOCS_DIR", DATA_DIR / "docs")).resolve()
TODO_DIR = DOCS_DIR / "TODO"
DONE_DIR = DOCS_DIR / "Done"
PROJECTS_IMPORT_FILE = Path(
    os.environ.get("WORKBOARD_PROJECTS_FILE", DATA_DIR / "projects.json")
).resolve()
AI_SETTINGS_FILE = DATA_DIR / "ai_settings.json"

MAX_TODO_ITEMS = 12
VISIBLE_TODO_ITEMS = 6
TODO_MARKDOWN_FILE = "TODO.md"
LOCAL_WORKBOARD_ROOT = PureWindowsPath(r"D:\01WorkBoard")
DEFAULT_AI_SETTINGS = {
    "provider": "deepseek",
    "model": "deepseek-chat",
    "baseUrl": "https://api.deepseek.com/v1",
    "apiKey": "",
}

app = Flask(__name__, static_folder=str(STATIC_DIR))
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


def env_list(name, defaults=()):
    value = os.environ.get(name)
    if value is None:
        return set(defaults)
    return {item.strip() for item in value.split(",") if item.strip()}


AUTH_MODE = os.environ.get("WORKBOARD_AUTH_MODE", "password").lower()
ALLOWED_EMAILS = env_list("WORKBOARD_ALLOWED_EMAILS")
ALLOWED_ORIGINS = env_list(
    "WORKBOARD_ALLOWED_ORIGINS",
    {"http://localhost:5000", "http://127.0.0.1:5000"},
)
PASSWORD_HASH = os.environ.get("WORKBOARD_PASSWORD_HASH", "")
SESSION_SECRET = os.environ.get("WORKBOARD_SESSION_SECRET", "")
MAX_LOGIN_FAILURES = int(os.environ.get("WORKBOARD_MAX_LOGIN_FAILURES", "5"))
LOGIN_WINDOW = timedelta(minutes=int(os.environ.get("WORKBOARD_LOGIN_WINDOW_MINUTES", "15")))
LOGIN_FAILURES = defaultdict(list)
PUBLIC_PATHS = {"/api/health", "/login", "/login.css", "/style.css"}
AGENT_TOKEN = os.environ.get("WORKBOARD_AGENT_TOKEN", "")
AGENT_ID_HEADER = "X-Workboard-Agent-Id"
LEASE_TOKEN_HEADER = "X-Workboard-Lease-Token"
ARCHIVE_LEASE_DURATION = timedelta(minutes=10)

if SESSION_SECRET:
    app.secret_key = SESSION_SECRET

app.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=os.environ.get("WORKBOARD_SESSION_COOKIE_SECURE", "true").lower()
    in {"1", "true", "yes"},
    SESSION_COOKIE_SAMESITE="Lax",
)


def ensure_storage():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TODO_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)


def get_db():
    if "db" not in g:
        ensure_storage()
        connection = sqlite3.connect(str(DB_PATH))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        g.db = connection
        init_db(connection)
    return g.db


def init_db(connection):
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            description TEXT NOT NULL DEFAULT '',
            local_path TEXT NOT NULL DEFAULT '',
            nas_path TEXT NOT NULL DEFAULT '',
            git_repo TEXT NOT NULL DEFAULT '',
            categories_json TEXT NOT NULL DEFAULT '[]',
            tags_json TEXT NOT NULL DEFAULT '[]',
            created TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS todos (
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
            screenshot_mime TEXT NOT NULL DEFAULT '',
            result_description TEXT NOT NULL DEFAULT '',
            local_path TEXT NOT NULL DEFAULT '',
            archive_status TEXT NOT NULL DEFAULT '',
            archive_error TEXT NOT NULL DEFAULT '',
            archive_lease_until TEXT,
            archive_lease_token TEXT NOT NULL DEFAULT '',
            archive_agent_id TEXT NOT NULL DEFAULT '',
            archive_completed_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    todo_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(todos)").fetchall()
    }
    migrations = {
        "project_number": "TEXT NOT NULL DEFAULT ''",
        "contact": "TEXT NOT NULL DEFAULT ''",
        "notes": "TEXT NOT NULL DEFAULT ''",
        "task_date": "TEXT NOT NULL DEFAULT ''",
        "screenshot_name": "TEXT NOT NULL DEFAULT ''",
        "screenshot_mime": "TEXT NOT NULL DEFAULT ''",
        "result_description": "TEXT NOT NULL DEFAULT ''",
        "local_path": "TEXT NOT NULL DEFAULT ''",
        "archive_status": "TEXT NOT NULL DEFAULT ''",
        "archive_error": "TEXT NOT NULL DEFAULT ''",
        "archive_lease_until": "TEXT",
        "archive_lease_token": "TEXT NOT NULL DEFAULT ''",
        "archive_agent_id": "TEXT NOT NULL DEFAULT ''",
        "archive_completed_at": "TEXT",
    }
    for column, definition in migrations.items():
        if column not in todo_columns:
            connection.execute(f"ALTER TABLE todos ADD COLUMN {column} {definition}")
    connection.execute(
        "UPDATE todos SET task_date = substr(created_at, 1, 10) WHERE task_date = ''"
    )
    connection.commit()
    import_projects_if_needed(connection)


def import_projects_if_needed(connection):
    count = connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    if count or not PROJECTS_IMPORT_FILE.exists():
        return
    try:
        records = json.loads(PROJECTS_IMPORT_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(records, list):
        return
    for record in records:
        try:
            payload = normalize_project_payload(record, [], allow_duplicate=False)
            connection.execute(
                """
                INSERT INTO projects
                (name, description, local_path, nas_path, git_repo,
                 categories_json, tags_json, created)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                project_values(payload),
            )
        except (ValueError, sqlite3.IntegrityError):
            continue
    connection.commit()


@app.teardown_appcontext
def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


@app.before_request
def enforce_access_boundary():
    if request.path == "/api/health":
        return None

    if request.path.startswith("/api/agent/"):
        return enforce_agent_access()

    if AUTH_MODE not in {"password", "cloudflare"}:
        return configuration_error("Authentication mode is not configured")

    if AUTH_MODE == "password" and not password_auth_is_configured():
        return configuration_error("Password login is not configured")

    if request.path in PUBLIC_PATHS:
        return None

    if AUTH_MODE == "password":
        if not session.get("authenticated"):
            return authentication_error("Authentication required", 401)
        if request.method in {"POST", "PATCH", "PUT", "DELETE"} and not valid_csrf_token():
            return jsonify({"error": "Invalid CSRF token"}), 403

    if AUTH_MODE == "cloudflare":
        email = request.headers.get("Cf-Access-Authenticated-User-Email", "").strip().lower()
        allowed = {item.lower() for item in ALLOWED_EMAILS}
        if not email:
            return jsonify({"error": "Authentication required"}), 401
        if allowed and email not in allowed:
            return jsonify({"error": "Access denied"}), 403

    if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
        origin = request.headers.get("Origin")
        if origin and origin not in ALLOWED_ORIGINS:
            return jsonify({"error": "Origin not allowed"}), 403


def password_auth_is_configured():
    return bool(PASSWORD_HASH and SESSION_SECRET)


def verify_agent_token(request_token: str, configured_token: str) -> bool:
    return bool(
        request_token
        and configured_token
        and secrets.compare_digest(str(request_token), str(configured_token))
    )


def enforce_agent_access():
    if not AGENT_TOKEN:
        return jsonify({"error": "Archive agent token is not configured"}), 503
    authorization = request.headers.get("Authorization", "")
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0] != "Bearer" or not parts[1] or not verify_agent_token(parts[1], AGENT_TOKEN):
        return jsonify({"error": "Archive agent authentication required"}), 401
    return None


def is_api_request():
    return request.path.startswith("/api/")


def authentication_error(message, status):
    if is_api_request():
        return jsonify({"error": message}), status
    return redirect(url_for("login"))


def configuration_error(message):
    if is_api_request():
        return jsonify({"error": message}), 503
    return message, 503


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def valid_csrf_token():
    supplied = request.headers.get("X-CSRF-Token", "") or request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    return bool(supplied and expected and secrets.compare_digest(supplied, expected))


def login_attempt_key():
    return request.remote_addr or "unknown"


def too_many_login_failures(key):
    cutoff = datetime.now() - LOGIN_WINDOW
    attempts = [item for item in LOGIN_FAILURES[key] if item > cutoff]
    LOGIN_FAILURES[key] = attempts
    return len(attempts) >= MAX_LOGIN_FAILURES


def record_login_failure(key):
    LOGIN_FAILURES[key].append(datetime.now())


def render_login(error=False, status=200):
    template = (STATIC_DIR / "login.html").read_text(encoding="utf-8")
    return (
        render_template_string(template, csrf_token=csrf_token(), error=error),
        status,
    )


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; connect-src 'self'; img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
        "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
        "script-src 'self'",
    )
    return response


def json_list(value):
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        parsed = []
    return parsed if isinstance(parsed, list) else []


def normalize_text_list(value):
    raw_values = value if isinstance(value, list) else str(value or "").split(",")
    result = []
    seen = set()
    for raw_value in raw_values:
        item = str(raw_value).strip()
        if item and item.lower() not in seen:
            result.append(item)
            seen.add(item.lower())
    return result


def validate_date(value):
    try:
        return datetime.strptime(str(value or ""), "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Created date must be in YYYY-MM-DD format") from exc


def date_folder_to_iso(value):
    try:
        return datetime.strptime(str(value or ""), "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Date folder must use YYYYMMDD format") from exc


def project_values(project):
    return (
        project["name"],
        project["description"],
        project["localPath"],
        project["nasPath"],
        project["gitRepo"],
        json.dumps(project["categories"], ensure_ascii=False),
        json.dumps(project["tags"], ensure_ascii=False),
        project["created"],
    )


def normalize_project_payload(payload, existing_projects, allow_duplicate=True):
    name = str(payload.get("name") or "").strip()
    local_path = str(payload.get("localPath") or "").strip()
    nas_path = str(payload.get("nasPath") or "").strip()
    git_repo = str(payload.get("gitRepo") or "").strip()
    description = str(payload.get("description") or "").strip()
    if not name:
        raise ValueError("Project name is required")
    if not local_path and not nas_path:
        raise ValueError("A local path or NAS path is required")
    duplicate = (
        allow_duplicate
        and name.lower()
        in {str(project.get("name", "")).strip().lower() for project in existing_projects}
    )
    if duplicate:
        raise ValueError("Project name already exists")
    return {
        "name": name,
        "description": description,
        "localPath": local_path,
        "nasPath": nas_path,
        "gitRepo": git_repo,
        "categories": normalize_text_list(payload.get("categories")),
        "created": validate_date(
            payload.get("created") or datetime.now().strftime("%Y-%m-%d")
        ),
        "tags": normalize_text_list(payload.get("tags")),
    }


def row_to_project(row):
    local_path = row["local_path"]
    nas_path = row["nas_path"]
    local_exists = bool(local_path and Path(local_path).exists())
    nas_exists = bool(nas_path and Path(nas_path).exists())
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "categories": json_list(row["categories_json"]),
        "tags": json_list(row["tags_json"]),
        "created": row["created"],
        "localPath": local_path,
        "gitInfo": get_git_info(row["git_repo"]),
        "pathStatus": {
            "localExists": local_exists,
            "nasExists": nas_exists,
            "recommendedPath": "nas" if nas_exists else ("local" if local_exists else None),
        },
        "pathLabel": "NAS path configured" if nas_path else "Local path configured",
    }


def load_project_rows():
    return get_db().execute("SELECT * FROM projects ORDER BY id").fetchall()


def load_projects():
    return [row_to_internal_project(row) for row in load_project_rows()]


def row_to_internal_project(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "localPath": row["local_path"],
        "nasPath": row["nas_path"],
        "gitRepo": row["git_repo"],
        "categories": json_list(row["categories_json"]),
        "tags": json_list(row["tags_json"]),
        "created": row["created"],
    }


def enrich_projects():
    projects = [row_to_project(row) for row in load_project_rows()]
    projects.sort(
        key=lambda item: (item["gitInfo"] or {}).get("last_commit", {}).get("date", ""),
        reverse=True,
    )
    return projects


def get_git_info(repo_path):
    if not GIT_AVAILABLE or not repo_path or not Path(repo_path).exists():
        return None
    try:
        repo = Repo(repo_path)
        commits = []
        for commit in repo.iter_commits(max_count=10):
            committed_at = commit.committed_datetime.replace(tzinfo=None)
            commits.append(
                {
                    "hash": commit.hexsha[:7],
                    "message": commit.message.strip().splitlines()[0] if commit.message else "",
                    "author": str(commit.author),
                    "date": committed_at.isoformat(timespec="seconds"),
                    "relative_date": relative_time(committed_at),
                }
            )
        if not commits:
            return None
        return {
            "branch": repo.active_branch.name if not repo.head.is_detached else "detached",
            "has_changes": repo.is_dirty(untracked_files=True),
            "last_commit": commits[0],
            "commits": commits,
        }
    except Exception as exc:
        print(f"Git metadata unavailable for {repo_path}: {exc}")
        return None


def relative_time(value):
    diff = datetime.now() - value
    seconds = max(diff.total_seconds(), 0)
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(seconds // 86400)
    return f"{days} day{'s' if days != 1 else ''} ago"


def validate_due_at(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).isoformat(timespec="minutes")
    except ValueError as exc:
        raise ValueError("Due time must be in YYYY-MM-DDTHH:MM format") from exc


def validate_progress(value, default=0):
    try:
        progress = default if value in (None, "") else int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Progress must be one of 0, 20, 40, 60, 80, 100") from exc
    if progress not in {0, 20, 40, 60, 80, 100}:
        raise ValueError("Progress must be one of 0, 20, 40, 60, 80, 100")
    return progress


def normalize_local_path(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    path = PureWindowsPath(raw)
    if path.drive or path.root:
        try:
            parts = list(path.relative_to(LOCAL_WORKBOARD_ROOT).parts)
        except ValueError as exc:
            raise ValueError("Local path must be under D:\\01WorkBoard") from exc
    else:
        parts = list(path.parts)

    normalized = []
    for part in parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not normalized:
                raise ValueError("Local path must stay under D:\\01WorkBoard")
            normalized.pop()
        else:
            normalized.append(part)
    return "\\".join(normalized)


def payload_text(payload, key, current, limit):
    value = payload[key] if key in payload else current
    return str(value or "").strip()[:limit]


def apply_todo_payload(item, payload):
    name = payload_text(payload, "name", item["name"], 200)
    if not name:
        raise ValueError("Task name is required")
    item["name"] = name
    item["projectNumber"] = payload_text(
        payload, "projectNumber", item["projectNumber"], 80
    )
    item["contact"] = payload_text(payload, "contact", item["contact"], 120)
    item["notes"] = payload_text(payload, "notes", item["notes"], 4000)
    item["resultDescription"] = payload_text(
        payload, "resultDescription", item["resultDescription"], 8000
    )
    item["localPath"] = normalize_local_path(
        payload_text(payload, "localPath", item["localPath"], 500)
    )
    item["taskDate"] = validate_date(
        payload["taskDate"] if "taskDate" in payload else item["taskDate"]
    )
    item["dueAt"] = validate_due_at(
        payload["dueAt"] if "dueAt" in payload else item["dueAt"]
    )
    item["progress"] = validate_progress(
        payload["progress"] if "progress" in payload else item["progress"],
        default=item["progress"],
    )
    if "projectId" in payload:
        project_id = payload["projectId"]
        if project_id in (None, ""):
            item["projectId"] = None
            item["projectName"] = (
                payload_text(payload, "projectName", "Temporary work", 200)
                or "Temporary work"
            )
        else:
            try:
                project_id = int(project_id)
            except (TypeError, ValueError) as exc:
                raise ValueError("A valid project must be selected") from exc
            project = next(
                (project for project in load_projects() if project["id"] == project_id), None
            )
            if project is None:
                raise LookupError("Project not found")
            item["projectId"] = project_id
            item["projectName"] = project["name"]
    elif "projectName" in payload:
        item["projectId"] = None
        item["projectName"] = (
            payload_text(payload, "projectName", "Temporary work", 200)
            or "Temporary work"
        )
    return item


def sanitize_task_name(name):
    value = re.sub(r'[<>:"/\\|?*]+', " ", str(name or "").strip())
    value = re.sub(r"\s+", " ", value).strip().rstrip(".")
    return (value or "Untitled Task")[:80]


def read_text_with_fallback(path):
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "cp936"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def find_worklog_file(task_dir):
    try:
        children = list(task_dir.iterdir())
    except OSError:
        return None
    return next(
        (
            child
            for child in children
            if child.is_file() and child.name.lower() == "worklog.txt"
        ),
        None,
    )


def first_summary_line(text, fallback):
    for line in str(text or "").splitlines():
        value = line.strip()
        if value:
            return value[:8000]
    return str(fallback or "本地历史任务已导入。")[:8000]


def local_import_duplicate_exists(task_date, name, local_path):
    return (
        get_db()
        .execute(
            """
            SELECT 1 FROM todos
            WHERE task_date = ? AND name = ? AND local_path = ? AND status = 'done'
            LIMIT 1
            """,
            (task_date, name, local_path),
        )
        .fetchone()
        is not None
    )


def safe_folder_name(base_dir, preferred_name, current_name=None):
    candidate = preferred_name
    index = 2
    while True:
        if candidate == current_name or not (base_dir / candidate).exists():
            return candidate
        candidate = f"{preferred_name} ({index})"
        index += 1


def todo_folder(item):
    base = DONE_DIR if item["status"] == "done" else TODO_DIR
    return base / item["folderName"]


def todo_row_to_dict(row):
    item = {
        "id": row["id"],
        "orderNo": row["order_no"],
        "name": row["name"],
        "projectId": row["project_id"],
        "projectName": row["project_name"] or "Temporary work",
        "createdAt": row["created_at"],
        "completedAt": row["completed_at"],
        "dueAt": row["due_at"],
        "progress": row["progress"],
        "status": row["status"],
        "folderName": row["folder_name"],
        "projectNumber": row["project_number"],
        "contact": row["contact"],
        "notes": row["notes"],
        "taskDate": row["task_date"],
        "screenshotName": row["screenshot_name"],
        "screenshotMime": row["screenshot_mime"],
        "resultDescription": row["result_description"],
        "localPath": row["local_path"],
        "archiveStatus": row["archive_status"],
        "archiveError": row["archive_error"],
        "archiveCompletedAt": row["archive_completed_at"],
    }
    item["screenshotUrl"] = (
        f"/api/todos/{item['id']}/screenshot" if item["screenshotName"] else None
    )
    item["todoMarkdownExists"] = (todo_folder(item) / TODO_MARKDOWN_FILE).exists()
    return item


def load_todos():
    rows = get_db().execute("SELECT * FROM todos ORDER BY order_no").fetchall()
    items = [todo_row_to_dict(row) for row in rows]
    return {
        "todo": [item for item in items if item["status"] != "done"],
        "done": [item for item in items if item["status"] == "done"],
        "limits": {"visibleTodoItems": VISIBLE_TODO_ITEMS, "maxTodoItems": MAX_TODO_ITEMS},
    }


def find_todo(todo_id):
    row = get_db().execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    return row_to_mutable_todo(row) if row else None


def row_to_mutable_todo(row):
    return {
        "id": row["id"],
        "orderNo": row["order_no"],
        "name": row["name"],
        "projectId": row["project_id"],
        "projectName": row["project_name"],
        "createdAt": row["created_at"],
        "completedAt": row["completed_at"],
        "dueAt": row["due_at"],
        "progress": row["progress"],
        "status": row["status"],
        "folderName": row["folder_name"],
        "projectNumber": row["project_number"],
        "contact": row["contact"],
        "notes": row["notes"],
        "taskDate": row["task_date"],
        "screenshotName": row["screenshot_name"],
        "screenshotMime": row["screenshot_mime"],
        "resultDescription": row["result_description"],
        "localPath": row["local_path"],
        "archiveStatus": row["archive_status"],
        "archiveError": row["archive_error"],
        "archiveLeaseUntil": row["archive_lease_until"],
        "archiveLeaseToken": row["archive_lease_token"],
        "archiveAgentId": row["archive_agent_id"],
        "archiveCompletedAt": row["archive_completed_at"],
    }


def save_todo(item):
    get_db().execute(
        """
        UPDATE todos SET order_no=?, name=?, project_id=?, project_name=?, created_at=?,
        completed_at=?, due_at=?, progress=?, status=?, folder_name=?, project_number=?,
        contact=?, notes=?, task_date=?, screenshot_name=?, screenshot_mime=?,
        result_description=?, local_path=?, archive_status=?, archive_error=?,
        archive_lease_until=?, archive_lease_token=?, archive_agent_id=?, archive_completed_at=? WHERE id=?
        """,
        (
            item["orderNo"],
            item["name"],
            item["projectId"],
            item["projectName"],
            item["createdAt"],
            item["completedAt"],
            item["dueAt"],
            item["progress"],
            item["status"],
            item["folderName"],
            item["projectNumber"],
            item["contact"],
            item["notes"],
            item["taskDate"],
            item["screenshotName"],
            item["screenshotMime"],
            item["resultDescription"],
            item["localPath"],
            item["archiveStatus"],
            item["archiveError"],
            item["archiveLeaseUntil"],
            item["archiveLeaseToken"],
            item["archiveAgentId"],
            item["archiveCompletedAt"],
            item["id"],
        ),
    )
    get_db().commit()


def todo_markdown(item):
    status = "done" if item["status"] == "done" else "todo"
    return "\n".join(
        [
            f"# {item['name']}",
            "",
            f"- Status: {status}",
            f"- Progress: {item['progress']}%",
            f"- Project: {item['projectName'] or 'Temporary work'}",
            f"- Project number: {item['projectNumber'] or 'Not set'}",
            f"- Contact: {item['contact'] or 'Not set'}",
            f"- Task date: {item['taskDate']}",
            f"- Local path: {item['localPath'] or 'Not set'}",
            f"- Created: {item['createdAt']}",
            f"- Due: {item['dueAt'] or 'Not set'}",
            f"- Completed: {item['completedAt'] or 'Not completed'}",
            f"- Archive status: {item['archiveStatus'] or 'Not started'}",
            f"- Archive completed: {item['archiveCompletedAt'] or 'Not completed'}",
            "",
            "## Notes",
            "",
            item["notes"] or "Add progress notes, evidence, screenshots and delivery details here.",
            "",
            "## Result Description",
            "",
            item["resultDescription"] or "No result description recorded.",
            "",
            "## Archive Error",
            "",
            item["archiveError"] or "None",
            "",
            "## Screenshot",
            "",
            item["screenshotName"] or "Not attached",
            "",
        ]
    )


def sync_todo_markdown(item):
    folder = todo_folder(item)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / TODO_MARKDOWN_FILE).write_text(todo_markdown(item), encoding="utf-8")


def serialize_todo(item):
    result = dict(item)
    result["todoMarkdownExists"] = (todo_folder(item) / TODO_MARKDOWN_FILE).exists()
    result["screenshotUrl"] = (
        f"/api/todos/{item['id']}/screenshot" if item["screenshotName"] else None
    )
    return result


def archive_storage():
    return ArchiveStorage(DATA_DIR / ".archive-staging", DONE_DIR)


def utc_now():
    return datetime.now(timezone.utc)


def utc_timestamp(value=None):
    return (value or utc_now()).isoformat(timespec="seconds")


def lease_is_active(item, now=None):
    raw_lease = item.get("archiveLeaseUntil")
    if not raw_lease:
        return False
    try:
        lease_until = datetime.fromisoformat(raw_lease)
        if lease_until.tzinfo is None:
            lease_until = lease_until.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return lease_until > (now or utc_now())


def agent_id_from_request(payload=None):
    header_value = request.headers.get(AGENT_ID_HEADER, "").strip()
    payload_value = str((payload or {}).get("agentId") or "").strip()
    if header_value and payload_value and header_value != payload_value:
        raise ValueError("Archive agent id does not match the request header")
    agent_id = header_value or payload_value
    if not agent_id:
        raise ValueError("Archive agent id is required")
    return agent_id[:120]


def require_active_agent_lease(todo_id, allow_done=False):
    item = find_todo(todo_id)
    if item is None:
        return None, (jsonify({"error": "Archive job not found"}), 404)
    try:
        agent_id = agent_id_from_request()
    except ValueError as exc:
        return None, (jsonify({"error": str(exc)}), 400)
    lease_token = request.headers.get(LEASE_TOKEN_HEADER, "")
    if ((item["status"] != "archive_pending" and not (allow_done and item["status"] == "done")) or item["archiveAgentId"] != agent_id
            or not lease_token or not item["archiveLeaseToken"]
            or not secrets.compare_digest(lease_token, item["archiveLeaseToken"])
            or not lease_is_active(item)):
        return None, (jsonify({"error": "Archive job is not leased to this agent"}), 409)
    return item, None


def archive_todo_folder_path(base_dir, folder_name):
    folder = ArchiveStorage._folder_name(folder_name)
    path = Path(base_dir) / folder
    ArchiveStorage._require_under(path, base_dir)
    return path


def move_todo_folder_to_done(item):
    source = archive_todo_folder_path(TODO_DIR, item["folderName"])
    target = archive_todo_folder_path(DONE_DIR, item["folderName"])
    target.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        write_text_atomically(target / TODO_MARKDOWN_FILE, todo_markdown(item))
        return
    write_text_atomically(source / TODO_MARKDOWN_FILE, todo_markdown(item))
    children = list(source.iterdir())
    for child in children:
        destination = target / child.name
        ArchiveStorage._require_under(destination, target)
        if destination.exists():
            if not child.is_file() or not destination.is_file() or child.read_bytes() != destination.read_bytes():
                raise RuntimeError("Archive destination already contains a task file")
    for child in source.iterdir():
        destination = target / child.name
        os.replace(child, destination)
    source.rmdir()


def write_text_atomically(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".part", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(value)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def setting_get(key, default=None):
    row = get_db().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return default if row is None else row["value"]


def setting_set(key, value):
    get_db().execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    get_db().commit()


def load_ai_settings():
    raw = setting_get("ai", "")
    if raw:
        try:
            value = json.loads(raw)
            if isinstance(value, dict):
                return {**DEFAULT_AI_SETTINGS, **value}
        except json.JSONDecodeError:
            pass
    if AI_SETTINGS_FILE.exists():
        try:
            value = json.loads(AI_SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                return {**DEFAULT_AI_SETTINGS, **value}
        except (OSError, json.JSONDecodeError):
            pass
    return dict(DEFAULT_AI_SETTINGS)


def save_ai_settings(settings):
    safe = {key: settings.get(key, DEFAULT_AI_SETTINGS[key]) for key in DEFAULT_AI_SETTINGS}
    setting_set("ai", json.dumps(safe, ensure_ascii=False))


def serialize_ai_settings(settings):
    key = settings.get("apiKey", "")
    return {
        "provider": settings.get("provider", "deepseek"),
        "model": settings.get("model", "deepseek-chat"),
        "baseUrl": settings.get("baseUrl", DEFAULT_AI_SETTINGS["baseUrl"]),
        "hasApiKey": bool(key),
        "keyPreview": f"{key[:3]}...{key[-3:]}" if len(key) >= 8 else "",
    }


def normalize_ai_payload(payload, existing):
    api_key = str(payload.get("apiKey") or "").strip() or existing.get("apiKey", "")
    base_url = str(payload.get("baseUrl") or DEFAULT_AI_SETTINGS["baseUrl"]).strip()
    if not base_url.startswith("https://"):
        raise ValueError("AI base URL must use HTTPS")
    return {
        "provider": "deepseek",
        "model": str(payload.get("model") or DEFAULT_AI_SETTINGS["model"]).strip(),
        "baseUrl": base_url.rstrip("/"),
        "apiKey": api_key,
    }


def resolve_period(period):
    now = datetime.now()
    if period == "week":
        start = now - timedelta(days=now.weekday())
        title = "This week"
    elif period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        title = "Today"
    else:
        raise ValueError("Period must be today or week")
    return start, now, title


def summary_task_item(item):
    return {
        "name": item.get("name", ""),
        "projectName": item.get("projectName", ""),
        "projectNumber": item.get("projectNumber", ""),
        "taskDate": item.get("taskDate", ""),
        "progress": item.get("progress", 0),
        "notes": item.get("notes", ""),
        "resultDescription": item.get("resultDescription", ""),
        "completedAt": item.get("completedAt"),
    }


def build_summary_context(period):
    start, end, title = resolve_period(period)
    todos = load_todos()
    pending = todos["todo"]
    done = [
        item for item in todos["done"]
        if item.get("completedAt") and item["completedAt"] >= start.isoformat()
    ]
    projects = enrich_projects()
    return {
        "period": period,
        "title": title,
        "range": {
            "start": start.isoformat(timespec="minutes"),
            "end": end.isoformat(timespec="minutes"),
        },
        "stats": {
            "pendingTodos": len(pending),
            "completedTodos": len(done),
            "projects": len(projects),
        },
        "basis": [
            f"Pending tasks: {len(pending)}",
            f"Completed tasks in period: {len(done)}",
            f"Tracked projects: {len(projects)}",
        ],
        "tasks": {
            "pending": [summary_task_item(item) for item in pending],
            "completed": [summary_task_item(item) for item in done],
        },
    }


def request_summary(settings, context):
    if not settings.get("apiKey"):
        raise ValueError("Configure the AI API key on the server before generating a summary")
    payload = {
        "model": settings.get("model", "deepseek-chat"),
        "messages": [
            {"role": "system", "content": "Summarize work progress clearly and concisely."},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
        "temperature": 0.2,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        settings["baseUrl"] + "/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings['apiKey']}",
        },
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"AI request failed: {exc}") from exc
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("AI provider returned an invalid response") from exc


@app.route("/login", methods=["GET", "POST"])
def login():
    if AUTH_MODE != "password":
        return authentication_error("Password login is not enabled", 404)
    if request.method == "GET":
        if session.get("authenticated"):
            return redirect(url_for("serve_index"))
        return render_login()

    if not valid_csrf_token():
        return render_login(error=True, status=400)

    key = login_attempt_key()
    if too_many_login_failures(key):
        return render_login(error=True, status=429)

    password = request.form.get("password", "")
    if not check_password_hash(PASSWORD_HASH, password):
        record_login_failure(key)
        return render_login(error=True, status=401)

    LOGIN_FAILURES.pop(key, None)
    session.clear()
    session.permanent = True
    session["authenticated"] = True
    csrf_token()
    return redirect(url_for("serve_index"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return ("", 204)


@app.route("/login.css")
def login_stylesheet():
    return send_from_directory(str(STATIC_DIR), "login.css")


@app.route("/")
def serve_index():
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory(str(STATIC_DIR), path)


@app.route("/api/session")
def get_session():
    return jsonify(
        {
            "authenticated": True,
            "authMode": AUTH_MODE,
            "csrfToken": csrf_token() if AUTH_MODE == "password" else None,
        }
    )


@app.route("/api/projects", methods=["GET"])
def get_projects():
    return jsonify(enrich_projects())


@app.route("/api/projects", methods=["POST"])
def create_project():
    payload = request.get_json(silent=True) or {}
    existing = load_projects()
    try:
        project = normalize_project_payload(payload, existing)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    try:
        cursor = get_db().execute(
            """
            INSERT INTO projects
            (name, description, local_path, nas_path, git_repo, categories_json, tags_json, created)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            project_values(project),
        )
        get_db().commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Project name already exists"}), 400
    row = get_db().execute("SELECT * FROM projects WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify({"success": True, "item": row_to_project(row)})


@app.route("/api/settings/ai", methods=["GET"])
def get_ai_settings():
    return jsonify(serialize_ai_settings(load_ai_settings()))


@app.route("/api/settings/ai", methods=["POST"])
def update_ai_settings():
    try:
        settings = normalize_ai_payload(request.get_json(silent=True) or {}, load_ai_settings())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    save_ai_settings(settings)
    return jsonify({"success": True, "settings": serialize_ai_settings(settings)})


def open_path_in_explorer(path):
    subprocess.Popen(["explorer.exe", str(path)])


@app.route("/api/project/<int:project_id>/open", methods=["GET", "POST"])
def open_project_folder(project_id):
    if request.method != "POST":
        return jsonify({"error": "Local folder opening requires a POST request"}), 410
    row = get_db().execute("SELECT local_path FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Project not found"}), 404
    local_path = str(row["local_path"] or "").strip()
    if not local_path:
        return jsonify({"error": "Project local path is not configured"}), 409
    path = Path(local_path).expanduser().resolve(strict=False)
    if not path.exists():
        return jsonify({"error": "Project local path does not exist"}), 404
    open_path_in_explorer(path)
    return jsonify({"success": True, "path": str(path)})


@app.route("/api/folder/select", methods=["POST"])
def folder_select_removed():
    return jsonify({"error": "Remote folder selection is disabled"}), 410


@app.route("/api/todos", methods=["GET"])
def get_todos():
    return jsonify(load_todos())


@app.route("/api/todos", methods=["POST"])
def create_todo():
    is_form_submission = request.mimetype == "multipart/form-data"
    payload = request.form.to_dict() if is_form_submission else (request.get_json(silent=True) or {})
    name = str(payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Task name is required"}), 400
    contact = str(payload.get("contact") or "").strip()
    if is_form_submission and not contact:
        return jsonify({"error": "Contact is required"}), 400
    try:
        due_at = validate_due_at(payload.get("dueAt"))
        progress = validate_progress(payload.get("progress"), default=0)
        task_date = validate_date(
            payload.get("taskDate") or datetime.now().strftime("%Y-%m-%d")
        )
        result_description = str(payload.get("resultDescription") or "").strip()[:8000]
        local_path = normalize_local_path(
            str(payload.get("localPath") or "").strip()[:500]
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    screenshot = request.files.get("screenshot")
    screenshot_name = ""
    screenshot_mime = ""
    if screenshot and screenshot.filename:
        screenshot_mime = str(screenshot.mimetype or "").lower()
        extensions = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        if screenshot_mime not in extensions:
            return jsonify({"error": "Screenshot must be PNG, JPEG, WebP or GIF"}), 400
        screenshot_name = "screenshot" + extensions[screenshot_mime]

    project_id = payload.get("projectId")
    project = None
    if project_id not in (None, ""):
        try:
            project_id = int(project_id)
        except (TypeError, ValueError):
            return jsonify({"error": "A valid project must be selected"}), 400
        project = next((item for item in load_projects() if item["id"] == project_id), None)
        if project is None:
            return jsonify({"error": "Project not found"}), 404
    else:
        project_id = None

    db = get_db()
    pending = db.execute("SELECT COUNT(*) FROM todos WHERE status != 'done'").fetchone()[0]
    if pending >= MAX_TODO_ITEMS:
        return jsonify({"error": f"Todo list is full. Maximum {MAX_TODO_ITEMS} pending tasks."}), 400
    folder_name = safe_folder_name(TODO_DIR, sanitize_task_name(name))
    now = datetime.now().isoformat(timespec="seconds")
    cursor = db.execute(
        """
        INSERT INTO todos
        (order_no, name, project_id, project_name, created_at, due_at, progress, status,
         folder_name, project_number, contact, notes, task_date, screenshot_name, screenshot_mime,
          result_description, local_path, archive_status, archive_error, archive_lease_until, archive_lease_token,
         archive_agent_id, archive_completed_at)
        VALUES ((SELECT COALESCE(MAX(order_no), 0) + 1 FROM todos), ?, ?, ?, ?, ?, ?, 'todo',
                ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', NULL, '', '', NULL)
        """,
        (
            name,
            project_id,
            project["name"] if project else "Temporary work",
            now,
            due_at,
            progress,
            folder_name,
            str(payload.get("projectNumber") or "").strip()[:80],
            contact[:120],
            str(payload.get("notes") or "").strip()[:4000],
            task_date,
            screenshot_name,
            screenshot_mime,
            result_description,
            local_path,
        ),
    )
    db.commit()
    item = find_todo(cursor.lastrowid)
    sync_todo_markdown(item)
    if screenshot_name:
        screenshot.save(todo_folder(item) / screenshot_name)
    return jsonify({"success": True, "item": serialize_todo(item)})


@app.route("/api/import/local-tasks", methods=["POST"])
def import_local_tasks():
    payload = request.get_json(silent=True) or {}
    root_path = Path(str(payload.get("rootPath") or "").strip()).expanduser()
    if not str(root_path).strip():
        return jsonify({"error": "Root path is required"}), 400
    root_path = root_path.resolve(strict=False)
    if not root_path.is_dir():
        return jsonify({"error": "Root path does not exist"}), 400

    imported = []
    skipped = 0
    ignored_date_folders = []
    db = get_db()
    for date_dir in sorted((child for child in root_path.iterdir() if child.is_dir()), key=lambda item: item.name):
        if not re.fullmatch(r"\d{8}", date_dir.name):
            ignored_date_folders.append(date_dir.name)
            continue
        try:
            task_date = date_folder_to_iso(date_dir.name)
        except ValueError:
            ignored_date_folders.append(date_dir.name)
            continue
        completed_at = f"{task_date}T23:59:00"
        for task_dir in sorted((child for child in date_dir.iterdir() if child.is_dir()), key=lambda item: item.name):
            name = task_dir.name.strip()
            if not name:
                continue
            local_path = str(task_dir.resolve(strict=False))
            if local_import_duplicate_exists(task_date, name, local_path):
                skipped += 1
                continue
            worklog = find_worklog_file(task_dir)
            notes = read_text_with_fallback(worklog).strip()[:4000] if worklog else ""
            result_description = first_summary_line(notes, name)
            folder_name = safe_folder_name(DONE_DIR, sanitize_task_name(name))
            cursor = db.execute(
                """
                INSERT INTO todos
                (order_no, name, project_id, project_name, created_at, completed_at, due_at,
                 progress, status, folder_name, project_number, contact, notes, task_date,
                 screenshot_name, screenshot_mime, result_description, local_path, archive_status,
                 archive_error, archive_lease_until, archive_lease_token, archive_agent_id,
                 archive_completed_at)
                VALUES ((SELECT COALESCE(MAX(order_no), 0) + 1 FROM todos), ?, NULL,
                        'Local imported worklog', ?, ?, NULL, 100, 'done', ?, '', '本地导入',
                        ?, ?, '', '', ?, ?, 'complete', '', NULL, '', '', ?)
                """,
                (
                    name[:200],
                    f"{task_date}T09:00:00",
                    completed_at,
                    folder_name,
                    notes,
                    task_date,
                    result_description,
                    local_path[:500],
                    completed_at,
                ),
            )
            db.commit()
            item = find_todo(cursor.lastrowid)
            sync_todo_markdown(item)
            imported.append(serialize_todo(item))

    return jsonify(
        {
            "success": True,
            "imported": len(imported),
            "skipped": skipped,
            "ignoredDateFolders": ignored_date_folders,
            "items": imported,
        }
    )


@app.route("/api/todos/<int:todo_id>", methods=["PATCH"])
def update_todo(todo_id):
    is_form_submission = request.mimetype == "multipart/form-data"
    payload = request.form.to_dict() if is_form_submission else (request.get_json(silent=True) or {})
    item = find_todo(todo_id)
    if item is None:
        return jsonify({"error": "Todo item not found"}), 404
    try:
        apply_todo_payload(item, payload)
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    screenshot = request.files.get("screenshot")
    if screenshot and screenshot.filename:
        screenshot_mime = str(screenshot.mimetype or "").lower()
        extensions = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        if screenshot_mime not in extensions:
            return jsonify({"error": "Screenshot must be PNG, JPEG, WebP or GIF"}), 400
        item["screenshotName"] = "screenshot" + extensions[screenshot_mime]
        item["screenshotMime"] = screenshot_mime
    old_folder = todo_folder(item)
    item["folderName"] = safe_folder_name(
        DONE_DIR if item["status"] == "done" else TODO_DIR,
        sanitize_task_name(item["name"]),
        current_name=item["folderName"],
    )
    new_folder = todo_folder(item)
    if old_folder != new_folder and old_folder.exists():
        old_folder.rename(new_folder)
    save_todo(item)
    sync_todo_markdown(item)
    if screenshot and screenshot.filename:
        screenshot.save(todo_folder(item) / item["screenshotName"])
    return jsonify({"success": True, "item": serialize_todo(item)})


@app.route("/api/todos/<int:todo_id>/progress", methods=["PATCH"])
def update_todo_progress(todo_id):
    item = find_todo(todo_id)
    if item is None:
        return jsonify({"error": "Todo item not found"}), 404
    try:
        payload = request.get_json(silent=True) or {}
        item["progress"] = validate_progress(payload.get("progress"), default=item["progress"])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    save_todo(item)
    sync_todo_markdown(item)
    return jsonify({"success": True, "item": serialize_todo(item)})


@app.route("/api/agent/jobs/claim", methods=["POST"])
def claim_archive_job():
    payload = request.get_json(silent=True) or {}
    try:
        agent_id = agent_id_from_request(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    now = utc_now()
    supplied_lease_token = str(payload.get("leaseToken") or "")
    db = get_db(); db.execute("BEGIN IMMEDIATE")
    active = db.execute("SELECT * FROM todos WHERE status='archive_pending' AND archive_agent_id=? ORDER BY id", (agent_id,)).fetchall()
    for row in active:
        item = row_to_mutable_todo(row)
        if lease_is_active(item) and supplied_lease_token and item["archiveLeaseToken"] and secrets.compare_digest(supplied_lease_token, item["archiveLeaseToken"]):
            item["archiveLeaseUntil"] = utc_timestamp(now + ARCHIVE_LEASE_DURATION)
            save_todo(item)
            return jsonify({"success": True, "job": serialize_todo(item), "leaseToken": item["archiveLeaseToken"]})
    row = db.execute(
        """
        SELECT * FROM todos
        WHERE status = 'archive_pending'
          AND archive_status IN ('pending', 'claimed', 'committed')
          AND (archive_lease_until IS NULL OR archive_lease_until <= ?)
        ORDER BY order_no, id
        LIMIT 1
        """,
        (utc_timestamp(now),),
    ).fetchone()
    if row is None:
        db.commit()
        return "", 204
    item = row_to_mutable_todo(row)
    if item["archiveStatus"] != "committed":
        item["archiveStatus"] = "claimed"
    item["archiveError"] = ""
    item["archiveLeaseUntil"] = utc_timestamp(now + ARCHIVE_LEASE_DURATION)
    item["archiveLeaseToken"] = secrets.token_urlsafe(32)
    item["archiveAgentId"] = agent_id
    save_todo(item)
    return jsonify({"success": True, "job": serialize_todo(item), "leaseToken": item["archiveLeaseToken"]})


@app.route("/api/agent/jobs/<int:todo_id>/files", methods=["PUT"])
def upload_archive_file(todo_id):
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify({"error": "Archive file is required"}), 400
    item = None
    try:
        storage = archive_storage()
        with storage.task_lock(todo_id):
            item, error_response = require_active_agent_lease(todo_id)
            if error_response:
                return error_response
            if item["archiveStatus"] == "committed":
                storage.verify_committed_upload_locked(todo_id, item["folderName"], request.form.get("relativePath"), upload.stream, request.form.get("expectedSize"), request.form.get("expectedSha256"))
            else:
                storage.store_file_locked(todo_id, request.form.get("relativePath"), upload.stream, request.form.get("expectedSize"), request.form.get("expectedSha256"))
    except TimeoutError as exc:
        return jsonify({"error": str(exc)}), 503
    except (OSError, ValueError) as exc:
        status_code = 409 if item is not None and item["archiveStatus"] == "committed" else 400
        return jsonify({"error": str(exc)}), status_code
    return jsonify({"success": True, "path": str(request.form.get("relativePath") or "").replace("\\", "/")})


@app.route("/api/agent/jobs/<int:todo_id>/commit", methods=["POST"])
def commit_archive_job(todo_id):
    item = None
    try:
        storage = archive_storage()
        with storage.task_lock(todo_id):
            item, error_response = require_active_agent_lease(todo_id)
            if error_response:
                return error_response
            storage.commit_locked(todo_id, item["folderName"], (request.get_json(silent=True) or {}).get("manifest"))
    except TimeoutError as exc:
        return jsonify({"error": str(exc)}), 503
    except (OSError, ValueError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 400
    item["archiveStatus"] = "committed"
    item["archiveError"] = ""
    save_todo(item)
    sync_todo_markdown(item)
    return jsonify({"success": True, "item": serialize_todo(item)})


@app.route("/api/agent/jobs/<int:todo_id>/finish", methods=["POST"])
def finish_archive_job(todo_id):
    item = None
    try:
        storage = archive_storage()
        with storage.task_lock(todo_id):
            item, error_response = require_active_agent_lease(todo_id, allow_done=True)
            if error_response:
                return error_response
            if item["archiveStatus"] not in {"committed", "complete"}:
                return jsonify({"error": "Archive files must be committed before finishing"}), 409
            storage.verify_committed_locked(todo_id, item["folderName"])
            final_item = dict(item); final_item.update(status="done", progress=100)
            move_todo_folder_to_done(final_item)
            if item["status"] == "done" and item["archiveStatus"] == "complete":
                return jsonify({"success": True, "item": serialize_todo(item)})
            completed_at = utc_timestamp()
            item["status"] = "done"
            item["progress"] = 100
            item["completedAt"] = completed_at
            item["archiveStatus"] = "complete"
            item["archiveError"] = ""
            item["archiveCompletedAt"] = completed_at
            save_todo(item)
            sync_todo_markdown(item)
            return jsonify({"success": True, "item": serialize_todo(item)})
    except TimeoutError as exc:
        return jsonify({"error": str(exc)}), 503
    except (OSError, RuntimeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/agent/jobs/<int:todo_id>/fail", methods=["POST"])
def fail_archive_job(todo_id):
    item = find_todo(todo_id)
    if item is None:
        return jsonify({"error": "Archive job not found"}), 404
    try:
        agent_id = agent_id_from_request()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    item, error_response = require_active_agent_lease(todo_id)
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    item["archiveStatus"] = "failed"
    item["archiveError"] = str(payload.get("error") or "Archive agent reported failure").strip()[:1000]
    item["archiveLeaseUntil"] = None
    item["archiveLeaseToken"] = ""
    save_todo(item)
    sync_todo_markdown(item)
    return jsonify({"success": True, "item": serialize_todo(item)})


@app.route("/api/todos/<int:todo_id>/archive/retry", methods=["POST"])
def retry_todo_archive(todo_id):
    try:
        storage = archive_storage()
        with storage.task_lock(todo_id):
            item = find_todo(todo_id)
            if item is None:
                return jsonify({"error": "Todo item not found"}), 404
            if item["status"] != "archive_pending" or item["archiveStatus"] != "failed":
                return jsonify({"error": "Archive is not retryable"}), 409
            storage.reset_locked(todo_id)
    except (OSError, ValueError, TimeoutError) as exc:
        return jsonify({"error": str(exc)}), 400
    item["archiveStatus"] = "pending"; item["archiveError"] = ""; item["archiveLeaseUntil"] = None; item["archiveLeaseToken"] = ""; item["archiveAgentId"] = ""
    save_todo(item); sync_todo_markdown(item)
    return jsonify({"success": True, "item": serialize_todo(item)})


@app.route("/api/todos/<int:todo_id>/complete", methods=["POST"])
def complete_todo(todo_id):
    item = find_todo(todo_id)
    if item is None:
        return jsonify({"error": "Todo item not found"}), 404
    if item["status"] == "todo":
        item["status"] = "archive_pending"
        item["archiveStatus"] = "pending"
        item["archiveError"] = ""
        item["archiveLeaseUntil"] = None
        item["archiveLeaseToken"] = ""
        item["archiveAgentId"] = ""
        item["archiveCompletedAt"] = None
        save_todo(item)
        sync_todo_markdown(item)
    return jsonify({"success": True, "item": serialize_todo(item)})


@app.route("/api/todos/<int:todo_id>/open")
def open_todo_removed(todo_id):
    return jsonify({"error": "Desktop folder opening is disabled in remote mode"}), 410


@app.route("/api/todos/<int:todo_id>/document")
def todo_document(todo_id):
    item = find_todo(todo_id)
    if item is None:
        return jsonify({"error": "Todo item not found"}), 404
    sync_todo_markdown(item)
    return send_file(todo_folder(item) / TODO_MARKDOWN_FILE, mimetype="text/plain; charset=utf-8")


@app.route("/api/todos/<int:todo_id>/screenshot")
def todo_screenshot(todo_id):
    item = find_todo(todo_id)
    if item is None or not item["screenshotName"]:
        return jsonify({"error": "Screenshot not found"}), 404
    screenshot_path = todo_folder(item) / item["screenshotName"]
    if not screenshot_path.is_file():
        return jsonify({"error": "Screenshot not found"}), 404
    return send_file(screenshot_path, mimetype=item["screenshotMime"])


@app.route("/api/contributions")
def get_contributions():
    if not GIT_AVAILABLE:
        return jsonify({})
    cutoff = datetime.now() - timedelta(days=365)
    daily_counts = defaultdict(int)
    for project in load_projects():
        repo_path = project.get("gitRepo")
        if not repo_path or not Path(repo_path).exists():
            continue
        try:
            repo = Repo(repo_path)
            for commit in repo.iter_commits(max_count=5000):
                committed_at = commit.committed_datetime.replace(tzinfo=None)
                if committed_at < cutoff:
                    break
                daily_counts[committed_at.strftime("%Y-%m-%d")] += 1
        except Exception as exc:
            print(f"Heatmap: error reading {repo_path}: {exc}")
    return jsonify(dict(daily_counts))


@app.route("/api/summary/context")
def get_summary_context():
    try:
        return jsonify(build_summary_context(request.args.get("period", "today")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/summary/generate", methods=["POST"])
def generate_summary():
    period = (request.get_json(silent=True) or {}).get("period", "today")
    try:
        context = build_summary_context(period)
        summary = request_summary(load_ai_settings(), context)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify(
        {
            **context,
            "success": True,
            "summary": summary,
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
        }
    )


@app.route("/api/health")
def health_check():
    get_db()
    return jsonify({"status": "ok", "git_available": GIT_AVAILABLE, "storage": "sqlite"})


if __name__ == "__main__":
    ensure_storage()
    host = os.environ.get("WORKBOARD_HOST", "127.0.0.1")
    port = int(os.environ.get("WORKBOARD_PORT", "5000"))
    app.run(host=host, port=port, debug=False)

