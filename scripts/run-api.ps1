param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8080
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python venv not found: $pythonExe"
}

Write-Host "Starting API on http://$BindHost`:$Port" -ForegroundColor Cyan
& $pythonExe -m uvicorn app.main:app --host $BindHost --port $Port
