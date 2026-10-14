# ==============================================================================
# NexusAct (GraphAction Fabric) — Quality & Validation Check (PowerShell)
# ==============================================================================

Write-Host "=== Running NexusAct Quality & Validation Suite ===" -ForegroundColor Cyan
$failed = $false

# 1. Python Formatting & Linting
Write-Host "`n[1/6] Checking Python formatting and linting (ruff)..." -ForegroundColor Yellow
& .\.venv\Scripts\ruff.exe check .
if ($LASTEXITCODE -ne 0) { $failed = $true; Write-Host "[FAIL] Ruff check failed." -ForegroundColor Red }
else { Write-Host "[PASS] Ruff check passed." -ForegroundColor Green }

& .\.venv\Scripts\ruff.exe format --check .
if ($LASTEXITCODE -ne 0) { $failed = $true; Write-Host "[FAIL] Ruff format check failed." -ForegroundColor Red }
else { Write-Host "[PASS] Ruff format check passed." -ForegroundColor Green }

# 2. Python Type Checking
Write-Host "`n[2/6] Checking Python types (mypy)..." -ForegroundColor Yellow
& .\.venv\Scripts\mypy.exe backend mcp_server
if ($LASTEXITCODE -ne 0) { $failed = $true; Write-Host "[FAIL] Mypy type check failed." -ForegroundColor Red }
else { Write-Host "[PASS] Mypy type check passed." -ForegroundColor Green }

# 3. Python Automated Test Suite
Write-Host "`n[3/6] Running Pytest suite (Smoke, Capabilities, Integration, Unit)..." -ForegroundColor Yellow
& .\.venv\Scripts\pytest.exe -v
if ($LASTEXITCODE -ne 0) { $failed = $true; Write-Host "[FAIL] Pytest tests failed." -ForegroundColor Red }
else { Write-Host "[PASS] All Pytest tests passed." -ForegroundColor Green }

# 4. Frontend Linting
Write-Host "`n[4/6] Checking Frontend linting (oxlint)..." -ForegroundColor Yellow
Push-Location frontend
& npm.cmd run lint
if ($LASTEXITCODE -ne 0) { $failed = $true; Write-Host "[FAIL] Frontend lint failed." -ForegroundColor Red }
else { Write-Host "[PASS] Frontend lint passed." -ForegroundColor Green }

# 5. Frontend Unit Tests
Write-Host "`n[5/6] Running Frontend tests (vitest)..." -ForegroundColor Yellow
& npm.cmd test
if ($LASTEXITCODE -ne 0) { $failed = $true; Write-Host "[FAIL] Frontend tests failed." -ForegroundColor Red }
else { Write-Host "[PASS] Frontend tests passed." -ForegroundColor Green }

# 6. Frontend Production Build
Write-Host "`n[6/6] Verifying Frontend production build..." -ForegroundColor Yellow
& npm.cmd run build
if ($LASTEXITCODE -ne 0) { $failed = $true; Write-Host "[FAIL] Frontend build failed." -ForegroundColor Red }
else { Write-Host "[PASS] Frontend build succeeded." -ForegroundColor Green }
Pop-Location

# Summary
Write-Host "`n==================================================" -ForegroundColor Cyan
if ($failed) {
    Write-Host "QUALITY CHECKS FAILED! Please address the issues listed above." -ForegroundColor Red
    exit 1
} else {
    Write-Host "ALL QUALITY CHECKS PASSED SUCCESSFULLY!" -ForegroundColor Green
    exit 0
}
