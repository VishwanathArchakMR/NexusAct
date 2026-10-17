#!/usr/bin/env pwsh
# ==============================================================================
# NexusAct (GraphAction Fabric) — Runtime Status & Health Diagnostic
# ==============================================================================
# Inspects:
# 1. FalkorDB connection & Cypher engine readiness via scripts/falkordb_probe.py
# 2. FastAPI backend /health and /api/v1/health/readiness endpoints
# 3. Vite React frontend endpoint (http://localhost:5173)
# ==============================================================================

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent $ScriptDir

Set-Location $ProjectRoot

Write-Host "`n=== NexusAct Runtime Status Inspection ===" -ForegroundColor Cyan

$allHealthy = $true

# 1. Inspect FalkorDB
Write-Host "`n[1/3] Checking FalkorDB Graph Database..." -ForegroundColor Yellow
$probeOutput = & "$ProjectRoot\.venv\Scripts\python.exe" "$ProjectRoot\scripts\falkordb_probe.py" 2>&1 | Out-String
$probeExit = $LASTEXITCODE

if ($probeExit -eq 0) {
    Write-Host "  [READY] FalkorDB 127.0.0.1:6379 - Live Cypher engine operational" -ForegroundColor Green
    $falkorStatus = "READY"
} elseif ($probeExit -eq 2) {
    Write-Host "  [DEGRADED] FalkorDB is replaying AOF dataset into memory" -ForegroundColor Yellow
    $falkorStatus = "LOADING"
    $allHealthy = $false
} else {
    Write-Host "  [FAILED] FalkorDB not responding: $($probeOutput.Trim())" -ForegroundColor Red
    $falkorStatus = "FAILED"
    $allHealthy = $false
}

# 2. Inspect FastAPI Backend
Write-Host "`n[2/3] Checking FastAPI Backend..." -ForegroundColor Yellow
$backendStatus = "FAILED"
try {
    $healthResp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 3 -ErrorAction Stop
    $readinessResp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/ready" -TimeoutSec 3 -ErrorAction Stop
    
    if ($healthResp.status -eq "OK" -and $readinessResp.status -eq "READY") {
        Write-Host "  [READY] FastAPI http://127.0.0.1:8000 - Health: OK, Readiness: READY" -ForegroundColor Green
        $backendStatus = "READY"
    } else {
        Write-Host "  [DEGRADED] FastAPI returned non-ready status: $($readinessResp | ConvertTo-Json -Compress)" -ForegroundColor Yellow
        $backendStatus = "DEGRADED"
        $allHealthy = $false
    }
} catch {
    Write-Host "  [FAILED] FastAPI backend not responding on http://127.0.0.1:8000: $_" -ForegroundColor Red
    $allHealthy = $false
}

# 3. Inspect Vite Frontend
Write-Host "`n[3/3] Checking Vite Frontend..." -ForegroundColor Yellow
$frontendStatus = "FAILED"
try {
    $frontResp = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
    if ($frontResp.StatusCode -eq 200) {
        Write-Host "  [READY] Vite Frontend http://localhost:5173 - Responding HTTP 200" -ForegroundColor Green
        $frontendStatus = "READY"
    } else {
        Write-Host "  [DEGRADED] Vite Frontend returned status code $($frontResp.StatusCode)" -ForegroundColor Yellow
        $frontendStatus = "DEGRADED"
        $allHealthy = $false
    }
} catch {
    Write-Host "  [STOPPED] Vite Frontend not responding on http://localhost:5173 (may be running headless or stopped)" -ForegroundColor DarkGray
    $frontendStatus = "STOPPED"
}

# Summary Table
Write-Host "`n======================================================================" -ForegroundColor DarkGray
Write-Host "  Component       Status       Endpoint / Target" -ForegroundColor White
Write-Host "  ----------------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  FalkorDB        $($falkorStatus.PadRight(12)) 127.0.0.1:6379" -ForegroundColor $(if ($falkorStatus -eq "READY") { "Green" } else { "Red" })
Write-Host "  FastAPI         $($backendStatus.PadRight(12)) http://127.0.0.1:8000" -ForegroundColor $(if ($backendStatus -eq "READY") { "Green" } else { "Red" })
Write-Host "  Vite Frontend   $($frontendStatus.PadRight(12)) http://localhost:5173" -ForegroundColor $(if ($frontendStatus -eq "READY") { "Green" } else { "Yellow" })
Write-Host "======================================================================" -ForegroundColor DarkGray

Write-Host "  Logs:" -ForegroundColor White
Write-Host "    Backend stdout: $ProjectRoot\logs\backend.log" -ForegroundColor DarkGray
Write-Host "    Backend stderr: $ProjectRoot\logs\backend.err.log" -ForegroundColor DarkGray
Write-Host "  API Docs:         http://127.0.0.1:8000/docs" -ForegroundColor DarkCyan

if ($allHealthy) {
    Write-Host "`n[PASS] All core NexusAct services are healthy and ready.`n" -ForegroundColor Green
    exit 0
} else {
    Write-Host "`n[WARN] One or more core NexusAct services are degraded or offline.`n" -ForegroundColor Yellow
    exit 1
}
