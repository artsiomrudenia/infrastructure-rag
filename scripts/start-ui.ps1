param(
    [ValidateSet("overlap", "bm25", "semantic", "hybrid")]
    [string]$Retriever = "hybrid",
    [ValidateRange(1, 65535)]
    [int]$Port = 8080,
    [string]$DocsDir = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python venv not found: $pythonExe"
}

if (-not $DocsDir) {
    $DocsDir = Join-Path $projectRoot "evaluation\corpus"
}
if (-not (Test-Path $DocsDir -PathType Container)) {
    throw "Documents directory not found: $DocsDir"
}

$modelDir = Join-Path $env:LOCALAPPDATA "infrastructure-rag\models\multilingual-e5-small-614241f"
if ($Retriever -in @("semantic", "hybrid") -and -not (Test-Path $modelDir -PathType Container)) {
    throw "Local E5 model not found: $modelDir. Restore the model or start with -Retriever overlap/bm25."
}

$settings = @{
    RAG_RETRIEVER = $Retriever
    RAG_DOCS_DIR = $DocsDir
    RAG_INCLUDE_FOLDERS = ""
    RAG_EXCLUDE_FOLDERS = ""
    RAG_BM25_K1 = "1.5"
    RAG_BM25_B = "0.75"
    RAG_CANDIDATE_MULTIPLIER = "5"
    HF_HUB_OFFLINE = "1"
    TRANSFORMERS_OFFLINE = "1"
}
if ($Retriever -in @("semantic", "hybrid")) {
    $settings.RAG_SEMANTIC_MODEL_DIR = $modelDir
}

$baseUrl = "http://127.0.0.1:$Port/"
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    try {
        $existingRuntime = Invoke-RestMethod -NoProxy -Uri "http://127.0.0.1:$Port/ui/config" -TimeoutSec 3
        $existingInfo = Invoke-RestMethod -NoProxy -Uri "http://127.0.0.1:$Port/info" -TimeoutSec 3
    } catch {
        throw "Port $Port is already in use by another service. Stop it or choose another port with -Port."
    }

    $expectedDocsDir = (Resolve-Path $DocsDir).Path
    $sameDocsDir = [string]::Equals($existingInfo.docs_dir, $expectedDocsDir, [StringComparison]::OrdinalIgnoreCase)
    $sameRuntime = $existingRuntime.retriever -eq $Retriever -and
        $existingRuntime.bm25_k1 -eq 1.5 -and
        $existingRuntime.bm25_b -eq 0.75 -and
        $existingRuntime.candidate_multiplier -eq 5
    if ($sameDocsDir -and $sameRuntime) {
        Write-Host "Matching infrastructure-rag UI is already running on $baseUrl" -ForegroundColor Green
        Write-Host "Retriever: $($existingRuntime.retriever) | Documents: $($existingInfo.indexed_documents)" -ForegroundColor DarkCyan
        Start-Process $baseUrl
        return
    }

    throw "Port $Port already serves infrastructure-rag with a different corpus or runtime. Stop it or choose another port with -Port."
}

$previous = @{}
foreach ($name in $settings.Keys) {
    $previous[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
    [Environment]::SetEnvironmentVariable($name, $settings[$name], "Process")
}

Write-Host "Starting infrastructure-rag UI: $baseUrl" -ForegroundColor Cyan
Write-Host "Retriever: $Retriever | Documents: $DocsDir" -ForegroundColor DarkCyan
Write-Host "Open $baseUrl after the API reports startup complete." -ForegroundColor DarkCyan
Write-Host "Keep this terminal open. Stop the server with Ctrl+C." -ForegroundColor Yellow

try {
    & (Join-Path $PSScriptRoot "run-api.ps1") -BindHost "127.0.0.1" -Port $Port -DocsDir $DocsDir
} finally {
    foreach ($name in $settings.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previous[$name], "Process")
    }
}
