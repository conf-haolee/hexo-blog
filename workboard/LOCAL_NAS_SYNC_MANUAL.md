# Workboard Local Primary + NAS Sync Manual

## Target Architecture

- Local Windows PC is the daily Workboard writer.
- Open the local panel at `http://127.0.0.1:5000`.
- The Windows helper archives completed task folders from `D:\01WorkBoard`.
- A push script publishes a Workboard progress snapshot to NAS over SSH.
- `work.cvhao.top` remains a NAS-hosted viewer for other machines.
- Avoid editing the same Workboard task data on both local and NAS instances.
- SMB is not required for the main workflow.

## Local Service Setup

Create a local data directory:

```powershell
New-Item -ItemType Directory -Path "D:\WorkboardService\data\docs" -Force
```

Current quick-start policy: do not import NAS data. Treat the local database as
the source of truth and overwrite the NAS viewer copy from local snapshots.
`bootstrap_local_from_nas.ps1` exists only as a recovery utility for a future
NAS-to-local restore.

Create the Python environment:

```powershell
cd D:\hexo-blog\workboard
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

Generate secrets:

```powershell
.\.venv\Scripts\python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-password'))"
.\.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(48))"
[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

Copy `.env.local.example` to `.env.local` and fill:

```dotenv
WORKBOARD_PASSWORD_HASH=...
WORKBOARD_SESSION_SECRET=...
WORKBOARD_AGENT_TOKEN=...
WORKBOARD_DATA_DIR=D:\WorkboardService\data
WORKBOARD_DOCS_DIR=D:\WorkboardService\data\docs
```

Run the local service:

```powershell
cd D:\hexo-blog\workboard
Get-Content .env.local | ForEach-Object {
  if ($_ -and -not $_.StartsWith("#")) {
    $Name, $Value = $_.Split("=", 2)
    Set-Item -Path "Env:$Name" -Value $Value
  }
}
.\.venv\Scripts\python server.py
```

Open:

```text
http://127.0.0.1:5000
```

## Windows Helper Setup

Install the helper so it talks to the local Workboard service:

```powershell
cd D:\hexo-blog\workboard
.\local_agent\install.ps1 `
  -WorkboardUrl "http://127.0.0.1:5000" `
  -AgentToken "paste-the-same-agent-token-here" `
  -RootPath "D:\01WorkBoard"
```

If the local PC is not on the same LAN as the NAS, do not use `-NasArchivePath`.
The NAS viewer receives progress through the SSH push script below.

## Push Local Progress to NAS over SSH

Use `scripts\push_to_nas_ssh.ps1` to create a consistent local snapshot and
overwrite the NAS viewer data directory through `ssh` and `scp`.

First verify SSH manually:

```powershell
ssh nas-user@nas-host
```

The NAS must have `tar` and `unzip` available. Before overwriting the NAS
viewer data directory, the script creates a remote backup under
`-RemoteBackupDir`.

Example:

```powershell
cd D:\hexo-blog\workboard
.\scripts\push_to_nas_ssh.ps1 `
  -DataDir "D:\WorkboardService\data" `
  -LocalBackupDir "D:\WorkboardService\backups" `
  -Remote "nas-user@nas-host" `
  -RemoteDataDir "/volume1/docker/workboard/data" `
  -RemoteBackupDir "/volume1/docker/workboard/backups" `
  -RemoteTempDir "/tmp" `
  -Commit "local-manual"
```

Use dry-run before the first real push:

```powershell
.\scripts\push_to_nas_ssh.ps1 `
  -DataDir "D:\WorkboardService\data" `
  -LocalBackupDir "D:\WorkboardService\backups" `
  -Remote "nas-user@nas-host" `
  -RemoteDataDir "/volume1/docker/workboard/data" `
  -RemoteBackupDir "/volume1/docker/workboard/backups" `
  -DryRun `
  -PlanPath "D:\WorkboardService\backups\last-push-plan.json"
```

NAS offline behavior:

- local zip backup is still created;
- SSH/SCP fails before NAS data is changed;
- re-run after NAS SSH is reachable.

## Daily Scheduled Task

Create a Windows scheduled task, for example at 02:00 every day:

```powershell
$Action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"D:\hexo-blog\workboard\scripts\push_to_nas_ssh.ps1`" -DataDir `"D:\WorkboardService\data`" -LocalBackupDir `"D:\WorkboardService\backups`" -Remote `"nas-user@nas-host`" -RemoteDataDir `"/volume1/docker/workboard/data`" -RemoteBackupDir `"/volume1/docker/workboard/backups`" -Commit `"scheduled`""
$Trigger = New-ScheduledTaskTrigger -Daily -At 2:00
Register-ScheduledTask -TaskName "Workboard Daily NAS Sync" -Action $Action -Trigger $Trigger -Description "Publish local Workboard progress snapshot to NAS"
```

## NAS Viewer Mode

Configure `work.cvhao.top` on NAS to read the remote data directory you push:

```text
/volume1/docker/workboard/data
```

Keep NAS-side editing disabled by policy. Treat NAS Workboard as a viewer or
recovery copy, not a second writer.

## Restore

To restore local Workboard from a backup zip:

1. Stop the local Workboard service.
2. Unzip the chosen `workboard-backup-*.zip`.
3. Replace `D:\WorkboardService\data\workboard.sqlite3`.
4. Replace `D:\WorkboardService\data\docs`.
5. Start the local Workboard service.
