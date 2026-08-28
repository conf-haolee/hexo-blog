param(
    [Parameter(Mandatory = $true)]
    [string]$WorkboardUrl,

    [Parameter(Mandatory = $true)]
    [string]$AgentToken,

    [string]$RootPath = "D:\01WorkBoard",

    [string]$NasArchivePath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$AgentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkboardDir = Split-Path -Parent $AgentDir
$ConfigPath = Join-Path $AgentDir "config.json"
$LogDir = Join-Path $env:LOCALAPPDATA "Workboard"
$LogPath = Join-Path $LogDir "agent.log"
$PythonCommand = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if ($null -eq $PythonCommand) {
    $PythonCommand = Get-Command python.exe -ErrorAction Stop
}
$PythonExe = $PythonCommand.Source

New-Item -ItemType Directory -Path $RootPath -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $RootPath "archive") -Force | Out-Null
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

$Config = [ordered]@{
    workboardUrl = $WorkboardUrl
    agentToken = $AgentToken
    agentId = "workboard-local-agent"
    rootPath = $RootPath
    logPath = $LogPath
}
if (-not [string]::IsNullOrWhiteSpace($NasArchivePath)) {
    $Config.nasArchivePath = $NasArchivePath
}
$Config | ConvertTo-Json | Set-Content -LiteralPath $ConfigPath -Encoding UTF8

$ProtocolKey = "HKCU:\Software\Classes\workboard"
$CommandKey = Join-Path $ProtocolKey "shell\open\command"
New-Item -Path $CommandKey -Force | Out-Null
Set-Item -LiteralPath $ProtocolKey -Value "URL:Workboard Protocol"
New-ItemProperty -Path $ProtocolKey -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
$ProtocolCommand = '"' + $PythonExe + '" "' + (Join-Path $AgentDir "protocol.py") + '" --config "' + $ConfigPath + '" "%1"'
Set-Item -LiteralPath $CommandKey -Value $ProtocolCommand

$StartupPath = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupPath "Workboard Local Archive Agent.lnk"
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonExe
$Shortcut.Arguments = '-m local_agent.agent --config "' + $ConfigPath + '"'
$Shortcut.WorkingDirectory = $WorkboardDir
$Shortcut.WindowStyle = 7
$Shortcut.Save()

Write-Host "Workboard local archive helper installed."
Write-Host "Config: $ConfigPath"
Write-Host "Root: $RootPath"
Write-Host "Log: $LogPath"
if (-not [string]::IsNullOrWhiteSpace($NasArchivePath)) {
    Write-Host "NAS archive: $NasArchivePath"
}
