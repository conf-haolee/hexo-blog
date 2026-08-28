# Workboard

Private Workboard service for the Hexo site. It is separate from the public
Hexo generator and from `hexo-admin`.

## Local Preview

```powershell
cd D:\hexo-blog\workboard
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
$env:WORKBOARD_AUTH_MODE = "password"
$env:WORKBOARD_PASSWORD_HASH = "<generated-password-hash>"
$env:WORKBOARD_SESSION_SECRET = "<generated-session-secret>"
$env:WORKBOARD_SESSION_COOKIE_SECURE = "false"
$env:WORKBOARD_AGENT_TOKEN = "<long-random-agent-token>"
$env:WORKBOARD_DATA_DIR = "$PWD\data"
$env:WORKBOARD_DOCS_DIR = "$PWD\data\docs"
.venv\Scripts\python server.py
```

Open `http://127.0.0.1:5000/`.

## Archive Helper

Completed tasks now enter an `archive_pending` state. A Windows helper polls
the token-protected agent API, uploads files from `D:\01WorkBoard`, writes a
local UTF-8 TXT record under `D:\01WorkBoard\archive\YYYY\YYYYMM`, deletes the
source task folder only after NAS commit and local record creation, then marks
the task done.

For the local-primary workflow, run Workboard on the Windows PC at
`http://127.0.0.1:5000`, point the helper at that local URL, and use
`scripts\push_to_nas_ssh.ps1` to publish progress snapshots to the NAS viewer
when SMB is unavailable. See `LOCAL_NAS_SYNC_MANUAL.md`.

Install the helper from Windows PowerShell:

```powershell
cd D:\hexo-blog\workboard
.\local_agent\install.ps1 -WorkboardUrl "https://work.cvhao.top" -AgentToken "<same-agent-token>"
```

The helper registers `workboard://` for opening local folders and creates a
current-user Startup shortcut. Its default log file is
`%LOCALAPPDATA%\Workboard\agent.log`. Uninstall preserves `D:\01WorkBoard`:

```powershell
.\local_agent\uninstall.ps1
```

## Production

Run the container on the NAS. Cloudflare Tunnel is the only public ingress; do
not expose the NAS management interface or arbitrary NAS folders.

Required production environment variables:

- `WORKBOARD_AUTH_MODE=password`
- `WORKBOARD_PASSWORD_HASH=<Werkzeug password hash>`
- `WORKBOARD_SESSION_SECRET=<random secret>`
- `WORKBOARD_AGENT_TOKEN=<long random archive-agent token>`
- `WORKBOARD_ALLOWED_ORIGINS=https://work.cvhao.top`
- `WORKBOARD_DATA_DIR=/app/data`
- `WORKBOARD_DOCS_DIR=/app/data/docs`

Create an untracked `.env` beside `docker-compose.yml` on the NAS. Generate
the values there, never in this repository:

```sh
docker compose run --rm workboard python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash(input('Workboard password: ')))"
docker compose run --rm workboard python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Generate the archive-agent token on Windows with PowerShell:

```powershell
[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

The `.env` file must contain only the generated values and host paths:

```dotenv
WORKBOARD_PASSWORD_HASH=paste-the-generated-hash-here
WORKBOARD_SESSION_SECRET=paste-the-generated-secret-here
WORKBOARD_AGENT_TOKEN=paste-the-generated-agent-token-here
WORKBOARD_DATA_HOST_PATH=/volume1/docker/workboard/data
WORKBOARD_PROJECTS_HOST_PATH=/volume1/docker/workboard/projects
```

For manual updates, copy only these targets to the NAS service directory:

- `server.py`
- `archive_service.py`
- `static/`

Do not overwrite NAS `.env`, `docker-compose.yaml`, or `data/`. On an existing
NAS compose file, make one minimal check before rebuilding: the `workboard`
service environment must include `WORKBOARD_AGENT_TOKEN: ${WORKBOARD_AGENT_TOKEN:-}`.
Add that single line if it is missing; do not replace the compose file.

Rebuild from the NAS service directory:

```sh
cd /volume1/docker/workboard
docker compose up -d --build workboard
docker compose ps
```

Verify `https://work.cvhao.top`: an incognito visit must show the login page,
a wrong password must fail, the correct password must show the dashboard, and
logout must return to the login page. `GET /api/health` stays public only for
Docker health checks and contains no work data.

`WORKBOARD_AUTH_MODE=cloudflare` remains available if Cloudflare Access is
enabled later. In that mode set `WORKBOARD_ALLOWED_EMAILS` and protect the
hostname with Cloudflare Access.

## Data Layout

- `data/workboard.sqlite3`: projects, tasks, and settings
- `data/docs/TODO`: active task records
- `data/docs/Done`: completed task records and committed uploaded files
- `data/projects.json`: optional first-run project import

The API never returns local or NAS absolute paths. Use authenticated NAS links
or repository links for file access.
