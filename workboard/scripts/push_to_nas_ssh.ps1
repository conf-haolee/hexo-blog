param(
    [Parameter(Mandatory = $true)]
    [string]$DataDir,

    [Parameter(Mandatory = $true)]
    [string]$LocalBackupDir,

    [Parameter(Mandatory = $true)]
    [string]$Remote,

    [Parameter(Mandatory = $true)]
    [string]$RemoteDataDir,

    [string]$RemoteBackupDir = "",

    [string]$RemoteTempDir = "/tmp",

    [string]$Commit = "",

    [switch]$DryRun,

    [string]$PlanPath = "",

    [string]$SshExe = "ssh",

    [string]$ScpExe = "scp"
)

$ErrorActionPreference = "Stop"

function ConvertTo-RemoteSingleQuoted {
    param([string]$Value)
    return "'" + ($Value -replace "'", "'\\''") + "'"
}

function Invoke-CheckedCommand {
    param([string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Exe failed with exit code $LASTEXITCODE"
    }
}

$DataPath = Resolve-Path -LiteralPath $DataDir
$DbSource = Join-Path $DataPath.Path "workboard.sqlite3"
if (-not (Test-Path -LiteralPath $DbSource -PathType Leaf)) {
    throw "Missing Workboard database: $DbSource"
}

New-Item -ItemType Directory -Path $LocalBackupDir -Force | Out-Null
$LocalBackupPath = (Resolve-Path -LiteralPath $LocalBackupDir).Path

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Stage = Join-Path ([System.IO.Path]::GetTempPath()) "workboard-push-$Stamp-$PID"
$ZipName = "workboard-push-$Stamp.zip"
$ZipPath = Join-Path $LocalBackupPath $ZipName

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

    if ([string]::IsNullOrWhiteSpace($RemoteBackupDir)) {
        $RemoteBackupDir = ($RemoteDataDir.TrimEnd("/") + "-backups")
    }

    $RemoteZipPath = $RemoteTempDir.TrimEnd("/") + "/" + $ZipName
    $QuotedZip = ConvertTo-RemoteSingleQuoted $RemoteZipPath
    $QuotedData = ConvertTo-RemoteSingleQuoted $RemoteDataDir
    $QuotedBackup = ConvertTo-RemoteSingleQuoted $RemoteBackupDir
    $QuotedBackupFile = ConvertTo-RemoteSingleQuoted ($RemoteBackupDir.TrimEnd("/") + "/workboard-before-push-$Stamp.tar.gz")
    $QuotedNestedData = ConvertTo-RemoteSingleQuoted ($RemoteDataDir.TrimEnd("/") + "/data")
    $QuotedUnpack = ConvertTo-RemoteSingleQuoted ($RemoteDataDir.TrimEnd("/") + "/.workboard-unpack")
    $QuotedUnpackData = ConvertTo-RemoteSingleQuoted ($RemoteDataDir.TrimEnd("/") + "/.workboard-unpack/data")
    $QuotedUnpackDataGlob = $QuotedUnpackData + "/*"
    $RemoteCommand = "set -e; mkdir -p $QuotedBackup; if [ -d $QuotedData ]; then tar -czf $QuotedBackupFile -C $QuotedData .; fi; rm -rf $QuotedData; mkdir -p $QuotedData; unzip -oq $QuotedZip -d $QuotedData; if [ -d $QuotedNestedData ]; then rm -rf $QuotedUnpack; mkdir -p $QuotedUnpack; mv $QuotedNestedData $QuotedUnpackData; find $QuotedData -mindepth 1 -maxdepth 1 ! -name .workboard-unpack -exec rm -rf {} +; mv $QuotedUnpackDataGlob $QuotedData/; rm -rf $QuotedUnpack; fi; rm -f $QuotedZip"

    $ScpArguments = @($ZipPath, "$Remote`:$RemoteZipPath")
    $SshArguments = @($Remote, $RemoteCommand)
    $Commands = @(
        "$ScpExe `"$ZipPath`" `"$Remote`:$RemoteZipPath`"",
        "$SshExe `"$Remote`" `"$RemoteCommand`""
    )

    if ($DryRun) {
        if (-not [string]::IsNullOrWhiteSpace($PlanPath)) {
            $Plan = [ordered]@{
                remote = $Remote
                remoteDataDir = $RemoteDataDir
                remoteBackupDir = $RemoteBackupDir
                remoteTempDir = $RemoteTempDir
                localZip = $ZipPath
                remoteZip = $RemoteZipPath
                commands = $Commands
            }
            $PlanJson = $Plan | ConvertTo-Json -Depth 4
            [System.IO.File]::WriteAllText($PlanPath, $PlanJson, [System.Text.UTF8Encoding]::new($false))
        }
        Write-Host "Dry run only. Created local push package: $ZipPath"
        return
    }

    Invoke-CheckedCommand -Exe $ScpExe -Arguments $ScpArguments
    Invoke-CheckedCommand -Exe $SshExe -Arguments $SshArguments
    Write-Host "Pushed Workboard snapshot to NAS: ${Remote}:$RemoteDataDir"
}
finally {
    if (Test-Path -LiteralPath $Stage) {
        Remove-Item -LiteralPath $Stage -Recurse -Force
    }
}
