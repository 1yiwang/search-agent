# Start Cloudflare tunnel only — backend must already run on :8000
# Usage: .\scripts\start-tunnel.ps1

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_cloudflared.ps1")

$Cloudflared = Get-CloudflaredExe
if (-not $Cloudflared) {
    Write-Host "cloudflared not found. winget install Cloudflare.cloudflared" -ForegroundColor Red
    exit 1
}

try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 3
    if ($r.status -ne "ok") { throw "bad status" }
} catch {
    Write-Host "Backend not running on http://127.0.0.1:8000" -ForegroundColor Red
    Write-Host "Start it first: cd backend; .\.venv\Scripts\python.exe main.py" -ForegroundColor Yellow
    exit 1
}

Write-Host "Backend OK on :8000" -ForegroundColor Green

$tokenPath = Join-Path $env:USERPROFILE ".cloudflared\token.txt"
$namedConfig = Join-Path $env:USERPROFILE ".cloudflared\config.yml"

if (Test-Path $tokenPath) {
    $token = (Get-Content $tokenPath -Raw).Trim()
    Write-Host "Starting tunnel (token) -> api-search.yiwang.dev ..." -ForegroundColor Cyan
    Write-Host "Ctrl+C stops tunnel only." -ForegroundColor Yellow
    & $Cloudflared tunnel run --token $token
} elseif (Test-Path $namedConfig) {
    Write-Host "Starting tunnel (config) -> api-search.yiwang.dev ..." -ForegroundColor Cyan
    & $Cloudflared tunnel run search-agent
} else {
    Write-Host "Missing token.txt or config.yml in $env:USERPROFILE\.cloudflared" -ForegroundColor Red
    exit 1
}
