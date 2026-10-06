param(
    [string]$BaseUrl = "http://127.0.0.1:8080",
    [string]$Question = "error rate after deployment and rollback",
    [int]$TopK = 3,
    [int]$TimeoutSec = 15
)

$ErrorActionPreference = "Stop"

$env:NO_PROXY = "localhost,127.0.0.1"
$env:no_proxy = "localhost,127.0.0.1"

$payload = @{
    question = $Question
    top_k = $TopK
} | ConvertTo-Json -Compress

Invoke-RestMethod -NoProxy -Method Post -Uri "$BaseUrl/query" -ContentType "application/json" -Body $payload -TimeoutSec $TimeoutSec | ConvertTo-Json -Depth 6
