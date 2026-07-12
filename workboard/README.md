# Workboard

This is the private workboard service for the Hexo site. It is separate from
the public Hexo generator and from `hexo-admin`.

## Local preview

`powershell
cd D:\hexo-blog\workboard
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
$env:WORKBOARD_AUTH_MODE = "local"
$env:WORKBOARD_DATA_DIR = "$PWD\data"
$env:WORKBOARD_DOCS_DIR = "$PWD\data\docs"
.venv\Scripts\python server.py
`

Open `http://127.0.0.1:5000/`.

## Production

Run the container on the NAS and bind the service to a private interface or
firewall it so only the VPS/Tailscale network can reach port 5000.

Required production environment variables:

- `WORKBOARD_AUTH_MODE=cloudflare`
- `WORKBOARD_ALLOWED_EMAILS=your-account-email`
- `WORKBOARD_ALLOWED_ORIGINS=https://www.cvhao.top`
- `WORKBOARD_DATA_DIR=/app/data`
- `WORKBOARD_DOCS_DIR=/app/data/docs`

Cloudflare Access must protect `www.cvhao.top/workboard/*`. The application
also checks the `Cf-Access-Authenticated-User-Email` header, so a direct request
without the Access identity is rejected.

## Data layout

- `data/workboard.sqlite3`: projects, tasks and settings
- `data/docs/TODO`: active task records
- `data/docs/Done`: completed task records
- `data/projects.json`: optional first-run project import

The API never returns local or NAS absolute paths. Use authenticated NAS links
or repository links for file access.

