param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8080,
    [switch]$SkipTests,
    [switch]$IncludeQuery,
    [string]$Question = "error rate after deployment and rollback",
    [int]$TopK = 3,
    [int]$StartupWaitSec = 2
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python venv not found: $pythonExe"
}

$baseUrl = "http://$BindHost`:$Port"

if (-not $SkipTests) {
    Write-Host "[1/4] Running tests" -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "run-tests.ps1") -Quiet
}

Write-Host "[2/4] Starting API" -ForegroundColor Cyan
$api = Start-Process -FilePath $pythonExe -ArgumentList "-m","uvicorn","app.main:app","--host",$BindHost,"--port",$Port -WorkingDirectory $projectRoot -PassThru

try {
    Start-Sleep -Seconds $StartupWaitSec

    Write-Host "[3/4] Running smoke checks" -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "smoke-local.ps1") -BaseUrl $baseUrl

    if ($IncludeQuery) {
        Write-Host "[4/4] Running query sample" -ForegroundColor Cyan
        & (Join-Path $PSScriptRoot "query-sample.ps1") -BaseUrl $baseUrl -Question $Question -TopK $TopK
    }
}
finally {
    if ($api -and -not $api.HasExited) {
        Stop-Process -Id $api.Id -Force
    }
}
