# Workboard

This is the private workboard service for the Hexo site. It is separate from
the public Hexo generator and from `hexo-admin`.

## Local preview

`powershell
cd D:\hexo-blog\workboard
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
$env:WORKBOARD_AUTH_MODE = "password"
$env:WORKBOARD_PASSWORD_HASH = "<generated-password-hash>"
$env:WORKBOARD_SESSION_SECRET = "<generated-session-secret>"
$env:WORKBOARD_SESSION_COOKIE_SECURE = "false"
$env:WORKBOARD_DATA_DIR = "$PWD\data"
$env:WORKBOARD_DOCS_DIR = "$PWD\data\docs"
.venv\Scripts\python server.py
`

Open `http://127.0.0.1:5000/`.

## Production

Run the container on the NAS. Cloudflare Tunnel is the only public ingress;
do not expose the NAS management interface or arbitrary NAS folders.

Required production environment variables:

- `WORKBOARD_AUTH_MODE=password`
- `WORKBOARD_PASSWORD_HASH=<Werkzeug password hash>`
- `WORKBOARD_SESSION_SECRET=<random secret>`
- `WORKBOARD_ALLOWED_ORIGINS=https://work.cvhao.top`
- `WORKBOARD_DATA_DIR=/app/data`
- `WORKBOARD_DOCS_DIR=/app/data/docs`

Create an untracked `.env` beside `docker-compose.yml` on the NAS. Generate
the values there, never in this repository:

```sh
docker compose run --rm workboard python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash(input('Workboard password: ')))"
docker compose run --rm workboard python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The `.env` file must contain only the generated values:

```dotenv
WORKBOARD_PASSWORD_HASH=paste-the-generated-hash-here
WORKBOARD_SESSION_SECRET=paste-the-generated-secret-here
WORKBOARD_DATA_HOST_PATH=/path/on/nas/workboard-data
WORKBOARD_PROJECTS_HOST_PATH=/path/on/nas/projects
```

Rebuild after updating the service files:

```sh
docker compose up -d --build workboard
docker compose ps
```

Then verify `https://work.cvhao.top`: an incognito visit must show the login
page, a wrong password must fail, the correct password must show the dashboard,
and logout must return to the login page. `GET /api/health` stays public only
for Docker health checks and contains no work data.

`WORKBOARD_AUTH_MODE=cloudflare` remains available if Cloudflare Access is
enabled later. In that mode set `WORKBOARD_ALLOWED_EMAILS` and protect the
hostname with Cloudflare Access.

## Data layout

- `data/workboard.sqlite3`: projects, tasks and settings
- `data/docs/TODO`: active task records
- `data/docs/Done`: completed task records
- `data/projects.json`: optional first-run project import

The API never returns local or NAS absolute paths. Use authenticated NAS links
or repository links for file access.

