param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$portalRoot = Join-Path $PSScriptRoot 'frontend'
$runtimeDir = Join-Path $portalRoot '.runtime'
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
$nodePath = (Get-Command node -ErrorAction Stop).Source
try {
    $existingPortal = Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -TimeoutSec 3
    if ($existingPortal.Content -notmatch 'Student CRM') { throw 'Port 5173 is used by another application.' }
    Write-Host 'Student CRM is already running: http://127.0.0.1:5173'
} catch {
    $portBusy = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
    if ($portBusy) { throw 'Port 5173 is in use. Stop the conflicting service or set a different PORT in frontend/.env.' }
    $serverPath = Join-Path $portalRoot 'server.mjs'
    $processInfo = Start-Process -FilePath $nodePath -ArgumentList @('--env-file-if-exists=.env', ('"' + $serverPath + '"')) -WorkingDirectory $portalRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir 'frontend.log') -RedirectStandardError (Join-Path $runtimeDir 'frontend-error.log') -PassThru
    $processInfo.Id | Set-Content -LiteralPath (Join-Path $runtimeDir 'frontend.pid')
    Write-Host 'Student CRM started: http://127.0.0.1:5173'
}
Write-Host 'Frappe must be running in Ubuntu WSL (bench start, port 8000).'
if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:5173' }
