# Write config.yml only — no Cloudflare login, no DNS changes.
# Use when: DNS already set + you have tunnel credentials from Cloudflare Dashboard.
#
# Usage:
#   1. Cloudflare Zero Trust → Networks → Tunnels → Create → search-agent
#   2. Copy the <uuid>.json credential into %USERPROFILE%\.cloudflared\
#   3. .\scripts\write-tunnel-config.ps1

$ErrorActionPreference = "Stop"

$TunnelName = "search-agent"
$Hostname = "api-search.yiwang.dev"
$CloudflaredDir = Join-Path $env:USERPROFILE ".cloudflared"
$ConfigPath = Join-Path $CloudflaredDir "config.yml"

if (-not (Test-Path $CloudflaredDir)) {
    New-Item -ItemType Directory -Path $CloudflaredDir | Out-Null
}

$credFile = Get-ChildItem -Path $CloudflaredDir -Filter "*.json" -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne "config.json" } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $credFile) {
    Write-Host "No tunnel credential JSON in $CloudflaredDir" -ForegroundColor Red
    Write-Host ""
    Write-Host "Get it from Cloudflare Dashboard (no CLI zone login needed):" -ForegroundColor Yellow
    Write-Host "  Zero Trust → Networks → Tunnels → search-agent → Configure"
    Write-Host "  Install connector → copy the .json file to:" -ForegroundColor Yellow
    Write-Host "  $CloudflaredDir"
    Write-Host ""
    Write-Host "Or save a run token to:" -ForegroundColor Yellow
    Write-Host "  $CloudflaredDir\token.txt"
    Write-Host "  (one line, from Dashboard → Run connector)" -ForegroundColor Yellow
    exit 1
}

$yaml = @"
tunnel: $TunnelName
credentials-file: $($credFile.FullName -replace '\\', '/')

ingress:
  - hostname: $Hostname
    service: http://localhost:8000
  - service: http_status:404
"@
Set-Content -Path $ConfigPath -Value $yaml -Encoding UTF8

Write-Host "Wrote $ConfigPath" -ForegroundColor Green
Write-Host "  credentials: $($credFile.Name)"
Write-Host ""
Write-Host "DNS: not touched (you already configured api-search)." -ForegroundColor Cyan
Write-Host "Test: .\scripts\start-personal.ps1" -ForegroundColor Cyan
