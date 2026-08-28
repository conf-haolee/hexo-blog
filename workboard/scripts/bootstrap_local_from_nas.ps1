param(
    [Parameter(Mandatory = $true)]
    [string]$NasDataDir,

    [Parameter(Mandatory = $true)]
    [string]$LocalDataDir,

    [Parameter(Mandatory = $true)]
    [string]$BackupDir,

    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Test-DirectoryHasAnyItem {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return $false
    }
    return $null -ne (Get-ChildItem -LiteralPath $Path -Force -ErrorAction Stop | Select-Object -First 1)
}

function Copy-DataSnapshot {
    param(
        [string]$SourceDataDir,
        [string]$TargetDataDir
    )

    New-Item -ItemType Directory -Path $TargetDataDir -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $SourceDataDir "workboard.sqlite3") -Destination (Join-Path $TargetDataDir "workboard.sqlite3") -Force

    $SourceDocs = Join-Path $SourceDataDir "docs"
    $TargetDocs = Join-Path $TargetDataDir "docs"
    if (Test-Path -LiteralPath $TargetDocs) {
        Remove-Item -LiteralPath $TargetDocs -Recurse -Force
    }
    if (Test-Path -LiteralPath $SourceDocs -PathType Container) {
        Copy-Item -LiteralPath $SourceDocs -Destination $TargetDocs -Recurse -Force
    }
}

$NasPath = Resolve-Path -LiteralPath $NasDataDir
$NasDb = Join-Path $NasPath.Path "workboard.sqlite3"
if (-not (Test-Path -LiteralPath $NasDb -PathType Leaf)) {
    throw "NAS Workboard database not found: $NasDb"
}

New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
$BackupPath = (Resolve-Path -LiteralPath $BackupDir).Path

if ((Test-DirectoryHasAnyItem -Path $LocalDataDir) -and -not $Force) {
    throw "Local data directory is not empty. Re-run with -Force to back it up and replace it: $LocalDataDir"
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Stage = Join-Path ([System.IO.Path]::GetTempPath()) "workboard-bootstrap-$Stamp-$PID"
try {
    if (Test-DirectoryHasAnyItem -Path $LocalDataDir) {
        $ExistingBackup = Join-Path $BackupPath "local-before-bootstrap-$Stamp.zip"
        Compress-Archive -Path (Join-Path $LocalDataDir "*") -DestinationPath $ExistingBackup -CompressionLevel Optimal
        Write-Host "Backed up existing local data: $ExistingBackup"
    }

    New-Item -ItemType Directory -Path $Stage -Force | Out-Null
    Copy-DataSnapshot -SourceDataDir $NasPath.Path -TargetDataDir $Stage

    if (Test-Path -LiteralPath $LocalDataDir) {
        Remove-Item -LiteralPath $LocalDataDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $LocalDataDir -Force | Out-Null
    Copy-DataSnapshot -SourceDataDir $Stage -TargetDataDir $LocalDataDir
    Write-Host "Bootstrapped local Workboard data from NAS."
    Write-Host "Source: $($NasPath.Path)"
    Write-Host "Target: $LocalDataDir"
}
finally {
    if (Test-Path -LiteralPath $Stage) {
        Remove-Item -LiteralPath $Stage -Recurse -Force
    }
}
