param(
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python venv not found: $pythonExe"
}

$args = @("-m", "pytest")
if ($Quiet) {
    $args += "-q"
}

Write-Host "Running tests..." -ForegroundColor Cyan
& $pythonExe @args
