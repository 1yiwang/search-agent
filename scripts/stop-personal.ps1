# Stop local Search Agent API started by start-personal.ps1
Get-Process -Name "python","cloudflared" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like "*search-agent*" -or $_.CommandLine -like "*uvicorn main*" } |
    Stop-Process -Force -ErrorAction SilentlyContinue

docker stop search-agent-api 2>$null
Write-Host "Stopped local API processes (if any were running)."
