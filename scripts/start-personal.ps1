# Start local Search Agent API + Cloudflare Tunnel (Mode B)
# Usage: .\scripts\start-personal.ps1
# Stop:  Ctrl+C (stops tunnel; close backend window or run stop-personal.ps1)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "_cloudflared.ps1")
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Host "Missing backend venv. Run: cd backend; python -m venv .venv; pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $Backend ".env"))) {
    Write-Host "Missing backend\.env — copy .env.example and add keys." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Search Agent — personal API" -ForegroundColor Cyan
Write-Host "  Backend:  http://localhost:8000"
Write-Host "  Health:   http://localhost:8000/api/health"
Write-Host ""
Write-Host "  Open https://search.yiwang.dev (or localhost:3000) after tunnel is up."
Write-Host "  Press Ctrl+C to stop tunnel (backend in other window keeps running)." -ForegroundColor Yellow
Write-Host ""

function Test-BackendHealth {
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 3
        return ($r.status -eq "ok")
    } catch {
        return $false
    }
}

# Check if backend already running (e.g. python main.py in another terminal)
if (Test-BackendHealth) {
    Write-Host "Backend already running on :8000 (reusing it)." -ForegroundColor Green
} else {
    Write-Host "Starting backend on :8000..." -ForegroundColor Cyan
    $backendCmd = "Set-Location '$Backend'; & '$Python' -m uvicorn main:app --host 127.0.0.1 --port 8000"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
    Start-Sleep -Seconds 3
    $healthOk = $false
    foreach ($i in 1..20) {
        if (Test-BackendHealth) { $healthOk = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $healthOk) {
        Write-Host "Backend did not start. If :8000 is already in use, run:" -ForegroundColor Red
        Write-Host "  .\scripts\start-tunnel.ps1" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "Backend is up." -ForegroundColor Green
}

$Cloudflared = Get-CloudflaredExe
$tokenPath = Join-Path $env:USERPROFILE ".cloudflared\token.txt"
$namedConfig = Join-Path $env:USERPROFILE ".cloudflared\config.yml"

if ($Cloudflared -and (Test-Path $tokenPath)) {
    $token = (Get-Content $tokenPath -Raw).Trim()
    Write-Host "Starting tunnel via token (api-search.yiwang.dev)..." -ForegroundColor Cyan
    & $Cloudflared tunnel run --token $token
} elseif (Test-Path $namedConfig) {
    if (-not $Cloudflared) {
        Write-Host "cloudflared not found but config.yml exists." -ForegroundColor Red
        exit 1
    }
    Write-Host "Starting named Cloudflare tunnel (api-search.yiwang.dev)..." -ForegroundColor Cyan
    & $Cloudflared tunnel run search-agent
} elseif ($Cloudflared) {
    Write-Host "No named tunnel config at $namedConfig" -ForegroundColor Yellow
    Write-Host "Run: .\scripts\write-tunnel-config.ps1" -ForegroundColor Yellow
    Write-Host "  (or put Dashboard run-token in %USERPROFILE%\.cloudflared\token.txt)" -ForegroundColor Yellow
    Write-Host "Using quick tunnel (random URL) for now..." -ForegroundColor Yellow
    Write-Host ""
    & $Cloudflared tunnel --url http://localhost:8000
} else {
    Write-Host "cloudflared not installed. API only on http://localhost:8000" -ForegroundColor Yellow
    Write-Host "Install: winget install Cloudflare.cloudflared" -ForegroundColor Yellow
    Write-Host "Press Ctrl+C to stop."
    while ($true) { Start-Sleep -Seconds 3600 }
}
