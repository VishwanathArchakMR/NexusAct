# ==============================================================================
# NexusAct (GraphAction Fabric) — Safe Service Shutdown Script (PowerShell)
# ==============================================================================

Write-Host "=== Stopping NexusAct Local Services ===" -ForegroundColor Cyan

# Stop FastAPI / Uvicorn processes
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*uvicorn*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "[STOP] Backend FastAPI server stopped." -ForegroundColor Yellow

# Stop Node / Vite dev servers
Get-Process node -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*vite*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "[STOP] Frontend Vite server stopped." -ForegroundColor Yellow

Write-Host "[OK] All NexusAct development services stopped." -ForegroundColor Green
