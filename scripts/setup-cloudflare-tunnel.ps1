# One-time Cloudflare Tunnel setup for api.search.yiwang.dev
# Usage: .\scripts\setup-cloudflare-tunnel.ps1
# Requires: cloudflared (winget install Cloudflare.cloudflared)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_cloudflared.ps1")

$TunnelName = "search-agent"
$Hostname = "api.search.yiwang.dev"
$CloudflaredDir = Join-Path $env:USERPROFILE ".cloudflared"
$ConfigPath = Join-Path $CloudflaredDir "config.yml"

$Cloudflared = Get-CloudflaredExe
if (-not $Cloudflared) {
    Write-Host "cloudflared not found." -ForegroundColor Red
    Write-Host "Install: winget install Cloudflare.cloudflared" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Search Agent — Cloudflare Tunnel setup" -ForegroundColor Cyan
Write-Host "  cloudflared: $Cloudflared"
Write-Host "  Hostname: $Hostname -> localhost:8000"
Write-Host ""

if (-not (Test-Path $CloudflaredDir)) {
    New-Item -ItemType Directory -Path $CloudflaredDir | Out-Null
}

$certPath = Join-Path $CloudflaredDir "cert.pem"
if (-not (Test-Path $certPath)) {
    Write-Host "Step 1/4: Login to Cloudflare (browser will open)..." -ForegroundColor Cyan
    Write-Host "  Select zone: yiwang.dev"
    & $Cloudflared tunnel login
} else {
    Write-Host "Step 1/4: Already logged in (cert.pem exists)." -ForegroundColor Green
}

Write-Host ""
Write-Host "Step 2/4: Create tunnel '$TunnelName' (skip if already exists)..." -ForegroundColor Cyan
$tunnelList = & $Cloudflared tunnel list 2>&1 | Out-String
if ($tunnelList -match $TunnelName) {
    Write-Host "  Tunnel '$TunnelName' already exists." -ForegroundColor Green
} else {
    & $Cloudflared tunnel create $TunnelName
}

$credFile = Get-ChildItem -Path $CloudflaredDir -Filter "*.json" -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne "config.json" } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $credFile) {
    Write-Host "No tunnel credentials JSON found in $CloudflaredDir" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Step 3/4: Route DNS $Hostname ..." -ForegroundColor Cyan
& $Cloudflared tunnel route dns $TunnelName $Hostname

Write-Host ""
Write-Host "Step 4/4: Write $ConfigPath ..." -ForegroundColor Cyan
$yaml = @"
tunnel: $TunnelName
credentials-file: $($credFile.FullName -replace '\\', '/')

ingress:
  - hostname: $Hostname
    service: http://localhost:8000
  - service: http_status:404
"@
Set-Content -Path $ConfigPath -Value $yaml -Encoding UTF8

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "  Config:  $ConfigPath"
Write-Host "  Creds:   $($credFile.FullName)"
Write-Host ""
Write-Host "Test:" -ForegroundColor Cyan
Write-Host "  1. .\scripts\start-personal.ps1"
Write-Host "  2. curl https://$Hostname/api/health"
Write-Host ""
