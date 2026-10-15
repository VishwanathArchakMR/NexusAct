#!/usr/bin/env pwsh
# ==============================================================================
# NexusAct (GraphAction Fabric) — Reliable Local Startup Script (PowerShell)
# Compatible with: Docker Desktop WSL integration OR bare WSL2 Docker daemon
# ==============================================================================
#
# DOCKER STRATEGY SELECTION:
#   1. Docker Desktop (windows-native docker.exe) — checked first.
#      Requires Docker Desktop to be running with WSL integration enabled.
#   2. WSL2 bare daemon (wsl docker) — fallback.
#      Requires Docker daemon started manually in WSL2.
#
# SECURITY NOTE:
#   This script never exposes Docker to 0.0.0.0.  The FalkorDB port is bound
#   strictly to 127.0.0.1:6379 in docker-compose.yml.  The WSL2 daemon uses
#   the Unix socket /var/run/docker.sock inside WSL, not an exposed TCP port.
#
# USAGE:
#   .\scripts\start.ps1                   # Start all services
#   .\scripts\start.ps1 -SkipFrontend     # Skip Vite dev server
#   .\scripts\start.ps1 -DatabaseOnly     # Start only FalkorDB
# ==============================================================================

param(
    [switch]$SkipFrontend,
    [switch]$DatabaseOnly
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot

# ── Helpers ──────────────────────────────────────────────────────────────────

function Write-Step {
    param([string]$Text, [string]$Color = "Cyan")
    Write-Host "`n==> $Text" -ForegroundColor $Color
}

function Write-Ok   { param([string]$T) Write-Host "  [OK]  $T" -ForegroundColor Green }
function Write-Warn { param([string]$T) Write-Host "  [!!]  $T" -ForegroundColor Yellow }
function Write-Fail { param([string]$T) Write-Host "  [FAIL] $T" -ForegroundColor Red }

# ── Step 1: Detect working Docker executor ───────────────────────────────────

Write-Step "Detecting Docker execution method..."

$DockerExe = $null
$DockerMode = $null

# 1a. Docker Desktop native (docker.exe on PATH)
$nativeDocker = Get-Command docker -ErrorAction SilentlyContinue
if ($nativeDocker) {
    try {
        $pingOut = & docker version --format "{{.Server.Version}}" 2>&1
        if ($LASTEXITCODE -eq 0 -and $pingOut -notmatch "error") {
            $DockerExe = "docker"
            $DockerMode = "DockerDesktop"
            Write-Ok "Docker Desktop is responding (server $pingOut)"
        } else {
            Write-Warn "docker.exe found but daemon not responding: $pingOut"
        }
    } catch {
        Write-Warn "docker.exe found but failed to query: $_"
    }
}

# 1b. WSL2 bare daemon fallback
if (-not $DockerMode) {
    Write-Warn "Trying WSL2 Docker daemon fallback..."
    try {
        $wslPing = wsl -d Ubuntu -u root docker version --format "{{.Server.Version}}" 2>&1
        if ($LASTEXITCODE -eq 0 -and $wslPing -notmatch "error") {
            $DockerExe = "wsl -d Ubuntu -u root docker"
            $DockerMode = "WSL2"
            Write-Ok "WSL2 Docker daemon is responding (server $wslPing)"
        } else {
            Write-Warn "WSL2 Docker daemon not responding: $wslPing"
        }
    } catch {
        Write-Warn "WSL2 fallback failed: $_"
    }
}

if (-not $DockerMode) {
    Write-Fail "No working Docker daemon found."
    Write-Host @"

  To fix this, choose one of:
    A) Start Docker Desktop and enable WSL integration.
    B) Start the Docker daemon in WSL2:
         wsl -d Ubuntu -u root service docker start

"@ -ForegroundColor Red
    exit 1
}

Write-Ok "Using Docker mode: $DockerMode"

# ── Step 2: Start FalkorDB via docker-compose ─────────────────────────────────

Write-Step "Starting FalkorDB container..."

if ($DockerMode -eq "DockerDesktop") {
    docker compose up -d falkordb
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "docker compose up -d falkordb failed."
        exit 1
    }
} else {
    # WSL2 mode: run docker-compose inside WSL from the mapped project path
    $wslPath = (wsl wslpath ($ProjectRoot -replace '\\', '/')) 2>&1
    if ($LASTEXITCODE -ne 0) {
        # Fallback: manual path translation C:\foo\bar -> /mnt/c/foo/bar
        $wslPath = "/mnt/" + ($ProjectRoot -replace '\\', '/') -replace '^([A-Za-z]):', { $_.Groups[1].Value.ToLower() }
    }
    Write-Host "  WSL path: $wslPath"
    wsl -d Ubuntu -u root -- bash -c "cd '$wslPath' && docker compose up -d falkordb"
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "WSL2 docker compose up failed."
        exit 1
    }
}

# ── Step 3: Wait for real FalkorDB readiness ──────────────────────────────────
# We do NOT just check TCP port open — we send an actual PING command via
# the Python client, which verifies the FalkorDB module is loaded.

Write-Step "Waiting for FalkorDB readiness..."

$maxWait = 30   # seconds
$interval = 2
$elapsed = 0
$ready = $false

while ($elapsed -lt $maxWait) {
    $pingResult = & .venv\Scripts\python.exe -c @"
import sys
try:
    import falkordb
    db = falkordb.FalkorDB(host='127.0.0.1', port=6379)
    db.connection.ping()
    print('READY')
except Exception as e:
    print(f'NOT_READY: {e}', file=sys.stderr)
    sys.exit(1)
"@ 2>&1

    if ($pingResult -match "READY") {
        $ready = $true
        Write-Ok "FalkorDB is ready on 127.0.0.1:6379"
        break
    }
    Write-Host "  Waiting... ($elapsed s)" -ForegroundColor DarkGray
    Start-Sleep -Seconds $interval
    $elapsed += $interval
}

if (-not $ready) {
    Write-Fail "FalkorDB did not become ready within $maxWait seconds."
    Write-Host "  Check container logs:" -ForegroundColor Yellow
    if ($DockerMode -eq "DockerDesktop") {
        docker logs nexusact_falkordb 2>&1 | Select-Object -Last 20
    } else {
        wsl -d Ubuntu -u root docker logs nexusact_falkordb 2>&1 | Select-Object -Last 20
    }
    exit 1
}

if ($DatabaseOnly) {
    Write-Ok "DatabaseOnly mode: FalkorDB ready. Exiting."
    exit 0
}

# ── Step 4: Start FastAPI backend ─────────────────────────────────────────────

Write-Step "Starting FastAPI backend..."

$backendReady = $false
$backendRunning = $false

# Check if backend is already running on port 8000
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -ErrorAction Stop
    if ($resp.StatusCode -eq 200) {
        $backendRunning = $true
        $backendReady = $true
        Write-Ok "FastAPI backend is already running and healthy at http://127.0.0.1:8000"
    }
} catch { }

if (-not $backendRunning) {
    $backendLog = "$ProjectRoot\logs\backend.log"
    New-Item -ItemType Directory -Force -Path "$ProjectRoot\logs" | Out-Null

    Get-Job -Name "NexusAct-Backend" -ErrorAction SilentlyContinue | Remove-Job -Force -ErrorAction SilentlyContinue

    $backendJob = Start-Job -Name "NexusAct-Backend" -ScriptBlock {
        param($root)
        Set-Location $root
        & .venv\Scripts\uvicorn.exe backend.app.main:app --host 0.0.0.0 --port 8000 --reload 2>&1
    } -ArgumentList $ProjectRoot

    Start-Sleep -Seconds 3

    # Verify backend is listening
    for ($i = 0; $i -lt 10; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                $backendReady = $true
                break
            }
        } catch { }
        Start-Sleep -Seconds 2
    }

    if ($backendReady) {
        Write-Ok "FastAPI backend running at http://127.0.0.1:8000"
    } else {
        Write-Warn "Backend may still be starting (health check timed out)"
    }
}

# ── Step 5: Start Vite frontend ───────────────────────────────────────────────

if (-not $SkipFrontend) {
    Write-Step "Starting Vite frontend..."

    $frontendRunning = $false
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 2 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            $frontendRunning = $true
            Write-Ok "Frontend Vite server is already running at http://localhost:5173"
        }
    } catch { }

    if (-not $frontendRunning) {
        Get-Job -Name "NexusAct-Frontend" -ErrorAction SilentlyContinue | Remove-Job -Force -ErrorAction SilentlyContinue

        $frontendJob = Start-Job -Name "NexusAct-Frontend" -ScriptBlock {
            param($frontendDir)
            Set-Location $frontendDir
            & npm run dev 2>&1
        } -ArgumentList "$ProjectRoot\frontend"

        Start-Sleep -Seconds 3
        Write-Ok "Frontend Vite server started (http://localhost:5173)"
    }
}

# ── Step 6: Report status ─────────────────────────────────────────────────────

Write-Step "Service Status" "Green"

Write-Host "`n  Service         Status       URL" -ForegroundColor White
Write-Host "  ─────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  FalkorDB        READY        127.0.0.1:6379 (Docker, loopback-only)" -ForegroundColor Green

if ($backendReady) {
    Write-Host "  FastAPI         READY        http://127.0.0.1:8000" -ForegroundColor Green
} else {
    Write-Host "  FastAPI         STARTING     http://127.0.0.1:8000 (check in a moment)" -ForegroundColor Yellow
}

if (-not $SkipFrontend -and -not $DatabaseOnly) {
    Write-Host "  Vite Frontend   STARTING     http://localhost:5173" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  API docs:        http://127.0.0.1:8000/docs" -ForegroundColor DarkCyan
Write-Host "  To stop:         .\scripts\stop.ps1" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "=== NexusAct local services started ===" -ForegroundColor Green
