param(
    [Parameter(Mandatory = $true)]
    [string]$DataDir,

    [Parameter(Mandatory = $true)]
    [string]$LocalBackupDir,

    [string]$NasBackupDir = "",

    [string]$NasMirrorDir = "",

    [string]$Commit = "",

    [int]$Keep = 30
)

$ErrorActionPreference = "Stop"

$DataPath = Resolve-Path -LiteralPath $DataDir
$DbSource = Join-Path $DataPath.Path "workboard.sqlite3"
if (-not (Test-Path -LiteralPath $DbSource -PathType Leaf)) {
    throw "Missing Workboard database: $DbSource"
}

New-Item -ItemType Directory -Path $LocalBackupDir -Force | Out-Null
$LocalBackupPath = (Resolve-Path -LiteralPath $LocalBackupDir).Path

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Stage = Join-Path ([System.IO.Path]::GetTempPath()) "workboard-backup-$Stamp-$PID"
$ZipPath = Join-Path $LocalBackupPath "workboard-backup-$Stamp.zip"

try {
    New-Item -ItemType Directory -Path (Join-Path $Stage "data") -Force | Out-Null
    $DbTarget = Join-Path $Stage "data\workboard.sqlite3"
    $Python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -eq $Python) {
        $Python = Get-Command python -ErrorAction Stop
    }
    $BackupCode = "import sqlite3, sys; src, dst = sys.argv[1], sys.argv[2]; source = sqlite3.connect(src); target = sqlite3.connect(dst); source.backup(target); target.close(); source.close()"
    & $Python.Source -c $BackupCode $DbSource $DbTarget
    if ($LASTEXITCODE -ne 0) {
        throw "SQLite backup failed"
    }

    $DocsSource = Join-Path $DataPath.Path "docs"
    if (Test-Path -LiteralPath $DocsSource -PathType Container) {
        Copy-Item -LiteralPath $DocsSource -Destination (Join-Path $Stage "data\docs") -Recurse -Force
    }

    if ([string]::IsNullOrWhiteSpace($Commit)) {
        $Commit = "unknown"
    }
    [System.IO.File]::WriteAllText((Join-Path $Stage "commit.txt"), $Commit, [System.Text.UTF8Encoding]::new($false))

    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }
    Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $ZipPath -CompressionLevel Optimal

    if (-not [string]::IsNullOrWhiteSpace($NasBackupDir)) {
        if (Test-Path -LiteralPath $NasBackupDir -PathType Container) {
            Copy-Item -LiteralPath $ZipPath -Destination $NasBackupDir -Force
            Write-Host "Copied backup to NAS: $NasBackupDir"
        } else {
            Write-Warning "NAS backup path is unavailable; kept local backup only: $NasBackupDir"
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($NasMirrorDir)) {
        if (Test-Path -LiteralPath $NasMirrorDir -PathType Container) {
            $LatestDir = Join-Path $NasMirrorDir "latest"
            $LatestDataDir = Join-Path $LatestDir "data"
            New-Item -ItemType Directory -Path $LatestDataDir -Force | Out-Null

            $MirrorDbTmp = Join-Path $LatestDataDir "workboard.sqlite3.tmp"
            $MirrorDb = Join-Path $LatestDataDir "workboard.sqlite3"
            Copy-Item -LiteralPath $DbTarget -Destination $MirrorDbTmp -Force
            Move-Item -LiteralPath $MirrorDbTmp -Destination $MirrorDb -Force

            $MirrorDocs = Join-Path $LatestDataDir "docs"
            if (Test-Path -LiteralPath $MirrorDocs) {
                Remove-Item -LiteralPath $MirrorDocs -Recurse -Force
            }
            $StageDocs = Join-Path $Stage "data\docs"
            if (Test-Path -LiteralPath $StageDocs -PathType Container) {
                Copy-Item -LiteralPath $StageDocs -Destination $MirrorDocs -Recurse -Force
            }
            Copy-Item -LiteralPath (Join-Path $Stage "commit.txt") -Destination (Join-Path $LatestDir "commit.txt") -Force
            Write-Host "Updated NAS mirror: $LatestDir"
        } else {
            Write-Warning "NAS mirror path is unavailable; skipped mirror update: $NasMirrorDir"
        }
    }

    foreach ($BackupDir in @($LocalBackupPath, $NasBackupDir)) {
        if ([string]::IsNullOrWhiteSpace($BackupDir) -or -not (Test-Path -LiteralPath $BackupDir -PathType Container)) {
            continue
        }
        Get-ChildItem -LiteralPath $BackupDir -Filter "workboard-backup-*.zip" |
            Sort-Object LastWriteTime -Descending |
            Select-Object -Skip $Keep |
            Remove-Item -Force
    }

    Write-Host "Created local backup: $ZipPath"
}
finally {
    if (Test-Path -LiteralPath $Stage) {
        Remove-Item -LiteralPath $Stage -Recurse -Force
    }
}
