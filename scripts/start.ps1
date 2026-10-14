# ==============================================================================
# NexusAct (GraphAction Fabric) — Service Launcher (PowerShell)
# ==============================================================================

param (
    [switch]$DatabaseOnly,
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

Write-Host "=== Starting NexusAct Services ===" -ForegroundColor Cyan

# 1. Start FalkorDB
if (-not $BackendOnly -and -not $FrontendOnly) {
    Write-Host "Starting FalkorDB container via Docker..." -ForegroundColor Cyan
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        docker compose up -d
    } else {
        wsl -d Ubuntu -u root docker compose -f /mnt/c/NexusAct/docker-compose.yml up -d
    }
    
    # Wait for ping readiness
    Write-Host "Verifying FalkorDB readiness on 127.0.0.1:6379..." -ForegroundColor Yellow
    $ready = $false
    for ($i = 0; $i -lt 10; $i++) {
        Start-Sleep -Seconds 1
        $conn = Test-NetConnection -ComputerName 127.0.0.1 -Port 6379 -InformationLevel Quiet
        if ($conn) {
            $ready = $true
            break
        }
    }
    if ($ready) {
        Write-Host "[OK] FalkorDB is ready and listening on port 6379." -ForegroundColor Green
    } else {
        Write-Warning "FalkorDB did not respond within 10 seconds. Check docker ps."
    }
}

if ($DatabaseOnly) {
    Write-Host "[OK] FalkorDB started. Exiting (-DatabaseOnly)." -ForegroundColor Green
    exit 0
}

# 2. Launch Backend
if (-not $FrontendOnly) {
    Write-Host "Starting FastAPI Backend on http://127.0.0.1:8000..." -ForegroundColor Cyan
    Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload"
    Write-Host "[OK] FastAPI Backend launched in background." -ForegroundColor Green
}

# 3. Launch Frontend
if (-not $BackendOnly) {
    Write-Host "Starting Vite Frontend on http://localhost:5173..." -ForegroundColor Cyan
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c cd frontend && npm run dev"
    Write-Host "[OK] Vite Frontend launched in background." -ForegroundColor Green
}

Write-Host "`nAll requested services are running!" -ForegroundColor Green
Write-Host "Frontend Dashboard: http://localhost:5173" -ForegroundColor Cyan
Write-Host "Backend API Docs:   http://127.0.0.1:8000/api/docs" -ForegroundColor Cyan
Write-Host "Health Check:       http://127.0.0.1:8000/api/v1/health" -ForegroundColor Cyan
Write-Host "Readiness Check:    http://127.0.0.1:8000/api/v1/ready" -ForegroundColor Cyan
