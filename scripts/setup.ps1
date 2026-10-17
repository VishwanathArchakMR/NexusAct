# ==============================================================================
# NexusAct (GraphAction Fabric) — Setup Script (PowerShell)
# ==============================================================================

Write-Host "=== Setting up NexusAct Foundation ===" -ForegroundColor Cyan

# 1. Check Python
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pyVer = python --version
    Write-Host "[OK] Python detected: $pyVer" -ForegroundColor Green
} else {
    Write-Error "Python is not installed or not in PATH."
    exit 1
}

# 2. Check Node & npm
if (Get-Command npm -ErrorAction SilentlyContinue) {
    $nodeVer = node --version
    $npmVer = npm --version
    Write-Host "[OK] Node $nodeVer and npm $npmVer detected" -ForegroundColor Green
} else {
    Write-Error "Node.js and npm are required."
    exit 1
}

# 3. Initialize .env
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "[OK] Created .env" -ForegroundColor Green
} else {
    Write-Host "[OK] .env already exists" -ForegroundColor Green
}

# 4. Setup Python Virtual Environment
if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment in .venv..." -ForegroundColor Cyan
    python -m uv venv .venv
}

Write-Host "Syncing Python dependencies with uv..." -ForegroundColor Cyan
python -m uv sync --extra dev
Write-Host "[OK] Python dependencies installed." -ForegroundColor Green

# 5. Setup Frontend
Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
Push-Location frontend
npm install
Pop-Location
Write-Host "[OK] Frontend dependencies installed." -ForegroundColor Green

Write-Host "`n=== Setup Complete! Run .\scripts\start.ps1 to launch services ===" -ForegroundColor Green
