# Workboard Archive Deployment Manual

## Scope

This manual covers the NAS Workboard service and the Windows local archive
helper. It does not deploy the public Hexo site.

## NAS Update

Copy only these files or folders from the prepared worktree to
`/volume1/docker/workboard` on the NAS:

- `server.py`
- `archive_service.py`
- `static/`

Do not overwrite these NAS-owned items during a manual update:

- `.env`
- `docker-compose.yaml` or `docker-compose.yml`
- `data/`

Before rebuilding, confirm the existing compose file passes the agent token
into the container:

```yaml
environment:
  WORKBOARD_AGENT_TOKEN: ${WORKBOARD_AGENT_TOKEN:-}
```

If that line is missing, add only that line under the existing `workboard`
service environment. Do not replace the compose file.

Generate the archive-agent token on Windows:

```powershell
[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

Add it to the NAS `.env`:

```dotenv
WORKBOARD_AGENT_TOKEN=paste-the-generated-agent-token-here
```

Rebuild from the NAS host:

```sh
cd /volume1/docker/workboard
docker compose up -d --build workboard
docker compose ps
```

Verify the service:

```sh
docker compose logs --tail=100 workboard
```

Then open `https://work.cvhao.top`, log in, create or edit a small task, set a
local path relative to `D:\01WorkBoard`, and complete it. The task should move
to the archive queue instead of Done until the Windows helper finishes it.

## Windows Helper Install

Run PowerShell as the target Windows user:

```powershell
cd D:\hexo-blog\workboard
.\local_agent\install.ps1 -WorkboardUrl "https://work.cvhao.top" -AgentToken "paste-the-generated-agent-token-here"
```

Optional root override:

```powershell
.\local_agent\install.ps1 -WorkboardUrl "https://work.cvhao.top" -AgentToken "paste-the-generated-agent-token-here" -RootPath "D:\01WorkBoard"
```

The installer:

- creates `D:\01WorkBoard` and `D:\01WorkBoard\archive`
- writes `local_agent\config.json`
- registers the current-user `workboard://` protocol
- creates a current-user Startup shortcut for the helper
- writes logs to `%LOCALAPPDATA%\Workboard\agent.log`

Test the protocol handler from Run or a browser address bar:

```text
workboard://open?path=
```

For a task folder:

```text
workboard://open?todoId=42&path=ProjectA%2FTask01
```

## Operation

When a task is completed in the browser, Workboard sets it to
`archive_pending`. The Windows helper claims one job at a time, uploads all
files from the configured local task folder, commits the manifest to the NAS
Done directory, writes the local TXT archive record, deletes the source task
folder, and then marks the task done.

Archive status labels in the browser:

- `等待归档`: queued for the helper
- `正在归档`: claimed or committed by the helper
- `归档失败`: helper reported an error
- `已完成`: NAS commit and local cleanup finished

If a task shows `归档失败`, open the task editor, check the error, fix the local
folder or configuration, and click `重试归档`.

## Rollback

NAS rollback:

1. Restore the previous `server.py`, `archive_service.py`, and `static/` from
   your NAS backup.
2. Keep `.env`, `docker-compose.yaml`, and `data/` unchanged.
3. Run from `/volume1/docker/workboard`:

```sh
docker compose up -d --build workboard
```

Windows helper rollback:

```powershell
cd D:\hexo-blog\workboard
.\local_agent\uninstall.ps1
```

Uninstall removes only the `workboard://` registration and Startup shortcut.
It preserves `D:\01WorkBoard`, existing task folders, and local archive records.
