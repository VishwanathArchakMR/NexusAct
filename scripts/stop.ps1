param(
    [switch]$StopDatabase
)

Write-Host "=== Stopping NexusAct Local Services ===" -ForegroundColor Cyan

# Stop background PowerShell jobs if running
Get-Job -Name "NexusAct-Backend", "NexusAct-Frontend" -ErrorAction SilentlyContinue | Stop-Job -ErrorAction SilentlyContinue | Remove-Job -Force -ErrorAction SilentlyContinue

# Stop FastAPI / Uvicorn processes
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*backend.app.main*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "[STOP] Backend FastAPI server stopped." -ForegroundColor Yellow

# Stop Node / Vite dev servers
Get-Process node -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*vite*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "[STOP] Frontend Vite server stopped." -ForegroundColor Yellow

# Optionally stop FalkorDB container if requested (NEVER delete volume)
if ($StopDatabase) {
    Write-Host "[STOP] Stopping FalkorDB container (volume preserved)..." -ForegroundColor Yellow
    docker stop nexusact_falkordb 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        wsl -d Ubuntu -u root docker stop nexusact_falkordb 2>&1 | Out-Null
    }
    Write-Host "[OK] FalkorDB container stopped (persistent volume intact)." -ForegroundColor Green
}

Write-Host "[OK] All requested NexusAct development services stopped." -ForegroundColor Green
