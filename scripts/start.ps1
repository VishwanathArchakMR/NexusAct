#!/usr/bin/env pwsh
# ==============================================================================
# NexusAct (GraphAction Fabric) - Reliable Local Startup Script (PowerShell)
# Compatible with: Docker Desktop WSL integration OR bare WSL2 Docker daemon
# ==============================================================================
#
# DOCKER STRATEGY SELECTION:
#   1. Docker Desktop (windows-native docker.exe) - checked first.
#      Requires Docker Desktop to be running with WSL integration enabled.
#   2. WSL2 bare daemon (wsl docker) - fallback.
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

# -- Helpers ------------------------------------------------------------------

function Write-Step {
    param([string]$Text, [string]$Color = "Cyan")
    Write-Host "`n==> $Text" -ForegroundColor $Color
}

function Write-Ok   { param([string]$T) Write-Host "  [OK]  $T" -ForegroundColor Green }
function Write-Warn { param([string]$T) Write-Host "  [!!]  $T" -ForegroundColor Yellow }
function Write-Fail { param([string]$T) Write-Host "  [FAIL] $T" -ForegroundColor Red }

# -- Step 1: Detect working Docker executor -----------------------------------

Write-Step "Detecting Docker execution method..."

$DockerMode = $null

# 1a. Docker Desktop native (docker.exe on PATH)
$nativeDocker = Get-Command docker -ErrorAction SilentlyContinue
if ($nativeDocker) {
    try {
        $pingOut = & docker version --format "{{.Server.Version}}" 2>&1
        if ($LASTEXITCODE -eq 0 -and $pingOut -notmatch "error") {
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
        if ($LASTEXITCODE -ne 0 -or $wslPing -match "error") {
            Write-Warn "WSL2 Docker service is stopped; attempting to start it..."
            wsl -d Ubuntu -u root service docker start | Out-Null
            Start-Sleep -Seconds 2
            $wslPing = wsl -d Ubuntu -u root docker version --format "{{.Server.Version}}" 2>&1
        }
        if ($LASTEXITCODE -eq 0 -and $wslPing -notmatch "error") {
            $DockerMode = "WSL2"
            # Ensure WSL2 does not terminate when idle by running persistent keeper
            Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-WindowStyle", "Hidden", "-Command", "wsl.exe -d Ubuntu -u root -- exec sleep 86400") -WindowStyle Hidden
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

# -- Step 2: Start FalkorDB via docker-compose ---------------------------------

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

# -- Step 3: Wait for real FalkorDB readiness ----------------------------------
# Uses the authoritative falkordb_probe.py to verify:
# 1. Redis connection
# 2. Cypher engine operational (disposable probe graph query)
# 3. Gracefully retries transient LOADING state (AOF log replay)

Write-Step "Waiting for FalkorDB readiness..."

$maxWait = 45   # seconds bounded timeout for dataset replay and Cypher init
$interval = 2
$elapsed = 0
$ready = $false
$lastProbeOutput = ""

while ($elapsed -lt $maxWait) {
    # Suppress NativeCommandError while testing readiness
    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $probeOutput = & "$ProjectRoot\.venv\Scripts\python.exe" "$ProjectRoot\scripts\falkordb_probe.py" 2>&1 | Out-String
    $probeExit = $LASTEXITCODE
    $ErrorActionPreference = $oldEap

    $lastProbeOutput = $probeOutput.Trim()

    if ($probeExit -eq 0 -and $lastProbeOutput -like "READY*") {
        $ready = $true
        Write-Ok "FalkorDB is ready on 127.0.0.1:6379 (verified via live Cypher probe)"
        break
    } elseif ($probeExit -eq 2 -or $lastProbeOutput -like "LOADING*") {
        Write-Host "  FalkorDB is loading persistent dataset into memory... ($elapsed s)" -ForegroundColor Yellow
    } elseif ($probeExit -eq 3 -or $lastProbeOutput -like "CONNECTION_REFUSED*") {
        Write-Host "  Waiting for FalkorDB port to respond... ($elapsed s)" -ForegroundColor DarkGray
    } elseif ($probeExit -eq 6 -or $lastProbeOutput -like "MODULE_MISSING*") {
        Write-Host "  Waiting for FalkorDB Cypher module initialization... ($elapsed s)" -ForegroundColor DarkGray
    } else {
        Write-Host "  FalkorDB probe: $lastProbeOutput ($elapsed s)" -ForegroundColor DarkGray
    }

    Start-Sleep -Seconds $interval
    $elapsed += $interval
}

if (-not $ready) {
    Write-Fail "FalkorDB did not become ready within $maxWait seconds."
    Write-Host "  Last probe output: $lastProbeOutput" -ForegroundColor Red
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

# -- Step 4: Start FastAPI backend ---------------------------------------------

Write-Step "Starting FastAPI backend..."

$backendReady = $false
$backendRunning = $false

# Check if backend is already running on port 8000
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    if ($resp.StatusCode -eq 200) {
        $backendRunning = $true
        $backendReady = $true
        Write-Ok "FastAPI backend is already running and healthy at http://127.0.0.1:8000"
    }
} catch { }

if (-not $backendRunning) {
    New-Item -ItemType Directory -Force -Path "$ProjectRoot\logs" | Out-Null

    # Stop any orphan uvicorn processes
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*backend.app.main*"
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

    Start-Process -FilePath "$ProjectRoot\.venv\Scripts\python.exe" `
        -ArgumentList "-m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000" `
        -WorkingDirectory $ProjectRoot `
        -RedirectStandardOutput "$ProjectRoot\logs\backend.log" `
        -RedirectStandardError "$ProjectRoot\logs\backend.err.log" `
        -WindowStyle Hidden

    # Verify backend is listening
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 2
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                $backendReady = $true
                break
            }
        } catch { }
    }

    if ($backendReady) {
        Write-Ok "FastAPI backend running at http://127.0.0.1:8000"
    } else {
        Write-Warn "Backend health check timed out. Check logs at $ProjectRoot\logs\backend.err.log"
    }
}

# -- Step 5: Start Vite frontend -----------------------------------------------

if (-not $SkipFrontend) {
    Write-Step "Starting Vite frontend..."

    $frontendRunning = $false
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            $frontendRunning = $true
            Write-Ok "Frontend Vite server is already running at http://localhost:5173"
        }
    } catch { }

    if (-not $frontendRunning) {
        Start-Process -FilePath "cmd.exe" `
            -ArgumentList "/c npm run dev" `
            -WorkingDirectory "$ProjectRoot\frontend" `
            -WindowStyle Hidden

        for ($i = 0; $i -lt 10; $i++) {
            Start-Sleep -Seconds 2
            try {
                $resp = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
                if ($resp.StatusCode -eq 200) {
                    $frontendRunning = $true
                    break
                }
            } catch { }
        }

        if ($frontendRunning) {
            Write-Ok "Frontend Vite server started (http://localhost:5173)"
        } else {
            Write-Warn "Frontend Vite server may still be starting."
        }
    }
}

# -- Step 6: Report status -----------------------------------------------------

Write-Step "Service Status" "Green"

$falkorStatus = if ($ready) { "READY" } else { "FAILED" }
$backendStatus = if ($backendReady) { "READY" } else { "FAILED" }
$frontendStatus = if ($SkipFrontend -or $DatabaseOnly) { "SKIPPED" } elseif ($frontendRunning) { "READY" } else { "DEGRADED" }

Write-Host "`n  Service         Status       URL / Endpoint" -ForegroundColor White
Write-Host "  ----------------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  FalkorDB        $($falkorStatus.PadRight(12)) 127.0.0.1:6379 (Cypher operational)" -ForegroundColor $(if ($ready) { "Green" } else { "Red" })
Write-Host "  FastAPI         $($backendStatus.PadRight(12)) http://127.0.0.1:8000" -ForegroundColor $(if ($backendReady) { "Green" } else { "Red" })
if (-not $DatabaseOnly) {
    Write-Host "  Vite Frontend   $($frontendStatus.PadRight(12)) http://localhost:5173" -ForegroundColor $(if ($frontendRunning) { "Green" } elseif ($SkipFrontend) { "DarkGray" } else { "Yellow" })
}

Write-Host "`n  Logs:" -ForegroundColor White
Write-Host "    Backend stdout: $ProjectRoot\logs\backend.log" -ForegroundColor DarkGray
Write-Host "    Backend stderr: $ProjectRoot\logs\backend.err.log" -ForegroundColor DarkGray
Write-Host "  API Docs:         http://127.0.0.1:8000/docs" -ForegroundColor DarkCyan
Write-Host "  Readiness check:  http://127.0.0.1:8000/ready" -ForegroundColor DarkCyan
Write-Host "  Status helper:    .\scripts\status.ps1" -ForegroundColor DarkCyan
Write-Host "  To stop:          .\scripts\stop.ps1" -ForegroundColor DarkCyan
Write-Host "`n=== NexusAct local services started ===" -ForegroundColor Green

if (-not $backendReady) {
    Write-Fail "FastAPI backend failed to start cleanly. Check logs at $ProjectRoot\logs\backend.err.log"
    exit 1
}

