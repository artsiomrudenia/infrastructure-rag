param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8080,
    [string]$DocsDir = "",
    [string]$IncludeFolders = "",
    [string]$ExcludeFolders = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python venv not found: $pythonExe"
}

if ($DocsDir) {
    $env:RAG_DOCS_DIR = $DocsDir
}
if ($IncludeFolders) {
    $env:RAG_INCLUDE_FOLDERS = $IncludeFolders
}
if ($ExcludeFolders) {
    $env:RAG_EXCLUDE_FOLDERS = $ExcludeFolders
}

Write-Host "Starting API on http://$BindHost`:$Port" -ForegroundColor Cyan
if ($env:RAG_DOCS_DIR) {
    Write-Host "RAG_DOCS_DIR=$($env:RAG_DOCS_DIR)" -ForegroundColor DarkCyan
}
& $pythonExe -m uvicorn app.main:app --host $BindHost --port $Port
