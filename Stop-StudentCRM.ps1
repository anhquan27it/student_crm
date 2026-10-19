$ErrorActionPreference = 'Stop'
$portalRoot = Join-Path $PSScriptRoot 'frontend'
$pidFile = Join-Path $portalRoot '.runtime\frontend.pid'
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Host 'No managed Student CRM process found.'; exit 0 }
$portalProcessId = [int](Get-Content -LiteralPath $pidFile)
$processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $portalProcessId"
$serverPath = Join-Path $portalRoot 'server.mjs'
if ($processInfo) {
    if (-not $processInfo.CommandLine.Contains($serverPath)) { throw 'PID belongs to another process; refusing to stop it.' }
    Stop-Process -Id $portalProcessId
}
Remove-Item -LiteralPath $pidFile
Write-Host 'Student CRM frontend stopped. Frappe was not stopped.'
