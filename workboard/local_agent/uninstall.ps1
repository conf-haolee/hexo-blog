Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProtocolKey = "HKCU:\Software\Classes\workboard"
if (Test-Path -LiteralPath $ProtocolKey) {
    Remove-Item -LiteralPath $ProtocolKey -Recurse -Force
}

$StartupPath = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupPath "Workboard Local Archive Agent.lnk"
if (Test-Path -LiteralPath $ShortcutPath) {
    Remove-Item -LiteralPath $ShortcutPath -Force
}

Write-Host "Workboard local archive helper removed. Task and archive data were preserved."
