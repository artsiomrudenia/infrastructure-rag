param(
    [string]$BaseUrl = "http://127.0.0.1:8080",
    [int]$TimeoutSec = 10
)

$ErrorActionPreference = "Stop"

$env:NO_PROXY = "localhost,127.0.0.1"
$env:no_proxy = "localhost,127.0.0.1"

Write-Host "Smoke check against $BaseUrl" -ForegroundColor Cyan

$health = Invoke-RestMethod -NoProxy -Method Get -Uri "$BaseUrl/healthz" -TimeoutSec $TimeoutSec
$reindex = Invoke-RestMethod -NoProxy -Method Post -Uri "$BaseUrl/reindex" -TimeoutSec $TimeoutSec

[PSCustomObject]@{
    health_status = $health.status
    indexed_documents = $reindex.indexed_documents
    indexed_chunks = $reindex.indexed_chunks
} | ConvertTo-Json -Depth 5
