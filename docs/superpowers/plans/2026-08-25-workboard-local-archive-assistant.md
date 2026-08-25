# Workboard Local Archive Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the single NAS-hosted Workboard with editable task details and a safe Windows helper that opens local folders and archives completed task files to the NAS.

**Architecture:** Flask remains the source of truth and exposes a token-protected, lease-based archive API. A standard-library Windows helper polls that API, uploads a verified manifest, writes the local archive TXT, and deletes source files only after both remote commit and local record creation succeed. The browser uses a registered `workboard://` protocol only for opening Explorer.

**Tech Stack:** Python 3, Flask, SQLite, `unittest`, vanilla JavaScript/CSS/HTML, Windows PowerShell and Registry.

**Spec:** `docs/superpowers/specs/2026-08-25-workboard-local-archive-assistant-design.md`

## Global Constraints

- NAS archive root is `/volume1/docker/workboard/data/docs/Done` through the existing `WORKBOARD_DOCS_DIR` configuration.
- Windows root is exactly `D:\01WorkBoard`; stored task paths are relative to this root.
- Never delete source material until NAS commit and atomic local TXT creation both succeed.
- Never recursively delete `D:\01WorkBoard`, its `archive` directory, a symlink/reparse point, or a path outside the configured root.
- Agent authentication uses `WORKBOARD_AGENT_TOKEN`, never the web login password.
- Do not overwrite NAS `.env`, `docker-compose.yaml`, or `data/` during manual deployment.
- All schema changes are additive migrations compatible with the existing SQLite database.

---

### Task 1: Task detail fields and archive state model

**Files:**
- Modify: `workboard/server.py`
- Modify: `workboard/tests/test_server.py`

**Interfaces:**
- Produces: serialized todo fields `resultDescription`, `localPath`, `archiveStatus`, `archiveError`, `archiveCompletedAt`.
- Produces: `normalize_local_path(value: object) -> str`, returning a safe path relative to `D:\01WorkBoard` or raising `ValueError`.
- Produces: `PATCH /api/todos/<id>` accepting the complete editable task payload.

- [ ] **Step 1: Write failing migration and serialization tests**

Add tests that create an old `todos` table, initialize the app, and assert the seven archive columns exist. Create a task and assert the five public camelCase fields default to empty/null values.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m unittest tests.test_server.WorkboardServerTest.test_todo_archive_fields_migrate_and_serialize -v`

Expected: FAIL because `result_description` and archive columns do not exist in serialized output.

- [ ] **Step 3: Add additive columns and serialization**

Extend `CREATE TABLE`, the `ALTER TABLE` compatibility map, `todo_row_to_dict`, `row_to_mutable_todo`, `save_todo`, INSERT values, and Markdown generation with:

```python
"result_description": "TEXT NOT NULL DEFAULT ''",
"local_path": "TEXT NOT NULL DEFAULT ''",
"archive_status": "TEXT NOT NULL DEFAULT ''",
"archive_error": "TEXT NOT NULL DEFAULT ''",
"archive_lease_until": "TEXT",
"archive_agent_id": "TEXT NOT NULL DEFAULT ''",
"archive_completed_at": "TEXT",
```

- [ ] **Step 4: Write failing path-validation and edit tests**

Cover empty path, `TaskA`, `D:\01WorkBoard\TaskA`, and lexical rejection of `..\secret`, `C:\secret`, and UNC paths. Reparse-point enforcement belongs to the Windows helper in Task 3 because the NAS cannot inspect the Windows filesystem. Assert `PATCH /api/todos/<id>` updates all editable fields and project name consistently.

- [ ] **Step 5: Run focused tests and verify RED**

Run: `python -m unittest tests.test_server.WorkboardServerTest.test_update_todo_details_validates_local_path -v`

Expected: FAIL with 404/405 because the complete edit endpoint is absent.

- [ ] **Step 6: Implement normalization and complete edit endpoint**

Implement a reusable payload updater with exact limits: task name 200, project number 80, contact 120, notes 4000, result description 8000, local path 500. Preserve current screenshot when no replacement is sent and call `sync_todo_markdown` after saving.

- [ ] **Step 7: Run task model tests and the full existing suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

- [ ] **Step 8: Commit the task model**

```bash
git add workboard/server.py workboard/tests/test_server.py
git commit -m "feat: add editable task archive fields"
```

---

### Task 2: Isolated archive storage and agent API

**Files:**
- Create: `workboard/archive_service.py`
- Create: `workboard/tests/test_archive_service.py`
- Modify: `workboard/server.py`
- Modify: `workboard/.env.example`

**Interfaces:**
- Produces: `ArchiveStorage(staging_root: Path, done_root: Path)` with `store_file`, `commit`, and `discard_stale_staging` methods.
- Produces: `verify_agent_token(request_token: str, configured_token: str) -> bool` using `secrets.compare_digest`.
- Produces agent routes `/api/agent/jobs/claim`, `/files`, `/commit`, `/finish`, and `/fail`.

- [ ] **Step 1: Write failing storage security tests**

Test that `store_file(todo_id, relative_path, stream, expected_size, expected_sha256)` accepts nested relative files, rejects absolute/traversal paths, rejects mismatched size/hash, and never writes outside a temporary staging root.

- [ ] **Step 2: Run storage tests and verify RED**

Run: `python -m unittest tests.test_archive_service -v`

Expected: ERROR importing `archive_service`.

- [ ] **Step 3: Implement minimal archive storage**

Use a `.archive-staging/<todo-id>/files` directory under `WORKBOARD_DATA_DIR`. Stream to a sibling `.part` file while calculating SHA-256, call `os.replace` only after validation, write a JSON manifest atomically, and atomically rename the committed task directory into `DONE_DIR/<folderName>/files`.

- [ ] **Step 4: Write failing API authentication, lease, and state tests**

Cover missing/wrong token (401), constant token header format, one active lease per job, expired lease recovery, complete creating `archive_pending`, successful claim/upload/commit/finish, failure preserving non-done state, and repeated file upload/commit idempotency.

- [ ] **Step 5: Run API tests and verify RED**

Run: `python -m unittest tests.test_server.WorkboardServerTest.test_agent_archive_workflow -v`

Expected: FAIL because `/api/agent/jobs/claim` does not exist.

- [ ] **Step 6: Implement token-protected archive routes**

Read the token from `WORKBOARD_AGENT_TOKEN`; return 503 if not configured. Use a 10-minute UTC lease. `POST /complete` must set `status='archive_pending'`, `archiveStatus='pending'`, and retain the task under TODO storage. `finish` sets `status='done'`, progress 100, completed timestamps, moves the existing Markdown/screenshot task folder safely, and regenerates Markdown.

- [ ] **Step 7: Document the new environment variable**

Add this non-secret placeholder to `.env.example`:

```text
WORKBOARD_AGENT_TOKEN=replace-with-a-long-random-token
```

- [ ] **Step 8: Run archive and regression tests**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

- [ ] **Step 9: Commit archive API**

```bash
git add workboard/archive_service.py workboard/server.py workboard/.env.example workboard/tests/test_archive_service.py workboard/tests/test_server.py
git commit -m "feat: add safe task archive API"
```

---

### Task 3: Windows helper core

**Files:**
- Create: `workboard/local_agent/__init__.py`
- Create: `workboard/local_agent/paths.py`
- Create: `workboard/local_agent/archive_record.py`
- Create: `workboard/local_agent/client.py`
- Create: `workboard/local_agent/agent.py`
- Create: `workboard/tests/test_local_agent.py`

**Interfaces:**
- Produces: `resolve_task_path(root: Path, stored_path: str) -> Path`.
- Produces: `collect_task_files(root: Path, task_path: Path) -> list[FileEntry]`.
- Produces: `write_archive_record(root: Path, task: dict) -> Path`.
- Produces: `ArchiveClient` methods matching the five agent API routes.
- Produces: `process_job(client, root, job) -> None` with delete-after-confirm semantics.

- [ ] **Step 1: Write failing safe-path and enumeration tests**

Use `TemporaryDirectory` to verify empty path resolves to root, relative paths resolve under root, traversal/other drives are rejected, `archive` is excluded, and symlink/reparse entries are rejected instead of followed.

- [ ] **Step 2: Run helper tests and verify RED**

Run: `python -m unittest tests.test_local_agent.LocalAgentPathTest -v`

Expected: ERROR importing `local_agent.paths`.

- [ ] **Step 3: Implement safe path primitives**

Use `Path.resolve(strict=False)`, `os.path.commonpath`, `Path.is_symlink`, and Windows file attributes where available. Return immutable file entries containing relative POSIX path, byte size, and SHA-256.

- [ ] **Step 4: Write failing archive TXT tests**

Assert UTF-8 content contains every textual field, excludes screenshot fields, uses `archive/YYYY/YYYYMM`, sanitizes Windows filename characters, formats `createdAt` as `YYYYMMDD_HHmmss`, and appends task ID on collision.

- [ ] **Step 5: Implement atomic TXT creation**

Write to `<name>.tmp`, flush and `os.fsync`, then `os.replace`. Return the final path only after replacement succeeds.

- [ ] **Step 6: Write failing end-to-end helper tests**

Use a small in-process fake client (not HTTP mocks) to verify upload order, manifest commit, TXT creation, source cleanup, missing-directory behavior, and that upload/commit/TXT failures leave every source file untouched.

- [ ] **Step 7: Implement HTTP client and polling workflow**

Use `urllib.request` with `Authorization: Bearer`, JSON requests, multipart generation, 30-second timeout, and redacted error messages. `process_job` uploads and commits first, writes TXT second, deletes only task contents third, and calls `finish` last. Poll with bounded exponential backoff from 5 to 60 seconds.

- [ ] **Step 8: Run helper and full tests**

Run: `python -m unittest tests.test_local_agent -v`

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS.

- [ ] **Step 9: Commit helper core**

```bash
git add workboard/local_agent workboard/tests/test_local_agent.py
git commit -m "feat: add Windows task archive helper"
```

---

### Task 4: Windows protocol and installation scripts

**Files:**
- Create: `workboard/local_agent/protocol.py`
- Create: `workboard/local_agent/install.ps1`
- Create: `workboard/local_agent/uninstall.ps1`
- Create: `workboard/local_agent/config.example.json`
- Modify: `workboard/tests/test_local_agent.py`

**Interfaces:**
- Produces: `parse_protocol_url(url: str) -> tuple[int | None, str]`.
- Produces: user-level `HKCU\Software\Classes\workboard` protocol registration.
- Produces: user-level Startup shortcut/launcher for `pythonw -m local_agent.agent`.

- [ ] **Step 1: Write failing protocol parsing tests**

Cover an empty path, Unicode relative path, percent encoding, malformed URL, traversal, absolute path, and ignored extra query parameters.

- [ ] **Step 2: Run protocol tests and verify RED**

Run: `python -m unittest tests.test_local_agent.LocalAgentProtocolTest -v`

Expected: ERROR importing `local_agent.protocol`.

- [ ] **Step 3: Implement protocol handler**

Parse with `urllib.parse`, reuse `resolve_task_path`, and invoke Explorer with `subprocess.Popen(['explorer.exe', str(path)])` only after validation. Never use `shell=True`.

- [ ] **Step 4: Add install and uninstall scripts**

`install.ps1` accepts `-WorkboardUrl`, `-AgentToken`, and optional `-RootPath` defaulting to `D:\01WorkBoard`; writes `config.json`, registers the protocol command using the selected Python executable, creates root/archive directories, and creates a current-user Startup launcher. `uninstall.ps1` removes only those registry/startup entries and preserves task/archive data.

- [ ] **Step 5: Perform script syntax and helper tests**

Run: `powershell -NoProfile -Command "[void][scriptblock]::Create((Get-Content -Raw workboard/local_agent/install.ps1)); [void][scriptblock]::Create((Get-Content -Raw workboard/local_agent/uninstall.ps1))"`

Run: `python -m unittest tests.test_local_agent -v`

Expected: syntax checks and tests PASS.

- [ ] **Step 6: Commit Windows integration**

```bash
git add workboard/local_agent workboard/tests/test_local_agent.py
git commit -m "feat: install Workboard Windows helper"
```

---

### Task 5: Task panel layout and edit interaction

**Files:**
- Modify: `workboard/static/index.html`
- Modify: `workboard/static/script.js`
- Modify: `workboard/static/style.css`
- Create: `workboard/tests/test_static_ui.py`

**Interfaces:**
- Consumes serialized task fields and `PATCH /api/todos/<id>` from Task 1.
- Consumes archive statuses and retry endpoint from Task 2.
- Consumes `workboard://open` protocol from Task 4.

- [ ] **Step 1: Write failing static UI structure tests**

Parse `index.html` and assert `todoSection` precedes `projectSection`, which precedes `heatmapSection`; assert the edit dialog contains inputs for result description and local path; assert `script.js` contains handlers for card click, double-click, edit submit, and archive retry.

- [ ] **Step 2: Run UI tests and verify RED**

Run: `python -m unittest tests.test_static_ui -v`

Expected: FAIL because the section order/dialog/handlers are absent.

- [ ] **Step 3: Reorder sections and add task dialog**

Move whole existing sections without duplicating IDs. Add a native `<dialog id="todoEditDialog">` containing all editable fields, save/cancel controls, and an archive error/retry area. Increment CSS/JS cache-busting query values.

- [ ] **Step 4: Implement event-safe card interaction**

Render each card with `data-todo-id`. A single click on card whitespace opens the edit dialog after a short delay; a double-click cancels that delay and navigates to the encoded `workboard://open` URL. Buttons call `stopPropagation`. Save sends JSON to PATCH and reloads. Archive states map to Chinese labels: 等待归档、正在归档、归档失败、已完成.

- [ ] **Step 5: Style responsive task cards and dialog**

Keep the established dark visual language, use a two-column detail form above 760px and one column below it, visibly distinguish archive errors, and keep task screenshots bounded without changing project cards.

- [ ] **Step 6: Run UI, JavaScript, and full tests**

Run: `python -m unittest tests.test_static_ui -v`

Run: `node --check workboard/static/script.js`

Run: `python -m unittest discover -s workboard/tests -v`

Expected: all checks PASS.

- [ ] **Step 7: Commit the UI**

```bash
git add workboard/static workboard/tests/test_static_ui.py
git commit -m "feat: add editable task archive interface"
```

---

### Task 6: Documentation, packaging, and end-to-end verification

**Files:**
- Modify: `workboard/README.md`
- Create: `workboard/DEPLOY_MANUAL.md`

**Interfaces:**
- Documents exact NAS copy set, environment variable, rebuild command, Windows installation, verification, retry, and rollback.

- [ ] **Step 1: Update operator documentation**

Document these exact NAS copy targets: `server.py`, `archive_service.py`, and `static/`; state that `.env`, `docker-compose.yaml`, and `data/` must remain untouched. Explain generation of a token with PowerShell `[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))`, adding it to NAS `.env`, and running the compose rebuild from `/volume1/docker/workboard` on the NAS host.

- [ ] **Step 2: Document Windows installation and rollback**

Include the `install.ps1` invocation, expected `workboard://` test, agent log location, `uninstall.ps1`, archive failure retry, and the rule that uninstall preserves `D:\01WorkBoard`.

- [ ] **Step 3: Run complete verification**

Run:

```text
python -m unittest discover -s workboard/tests -v
python -m py_compile workboard/server.py workboard/archive_service.py workboard/local_agent/__init__.py workboard/local_agent/paths.py workboard/local_agent/archive_record.py workboard/local_agent/client.py workboard/local_agent/agent.py workboard/local_agent/protocol.py
node --check workboard/static/script.js
git diff --check -- workboard
```

Expected: all tests and syntax checks exit 0; `git diff --check` reports no whitespace errors.

- [ ] **Step 4: Build and smoke-test the container**

Run: `docker compose -f workboard/docker-compose.yml build workboard`

Run the built service with temporary data/token settings, then verify authenticated health, task edit, archive claim, a small file upload, commit, and finish through the integration test client. Stop only the temporary test container afterward.

- [ ] **Step 5: Review changed-file boundary**

Run: `git status --short` and verify the feature commits include only `workboard/` plus these spec/plan documents; preserve unrelated existing worktree changes.

- [ ] **Step 6: Commit documentation**

```bash
git add workboard/README.md workboard/DEPLOY_MANUAL.md
git commit -m "docs: add Workboard archive deployment guide"
```
