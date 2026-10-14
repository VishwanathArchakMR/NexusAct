#!/usr/bin/env bash
set -euo pipefail

echo "=== Setting up NexusAct Foundation ==="

# 1. Check Python
if command -v python3 &>/dev/null; then
    echo "[OK] Python detected: $(python3 --version)"
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    echo "[OK] Python detected: $(python --version)"
    PYTHON_BIN="python"
else
    echo "[ERROR] Python is not installed or not in PATH."
    exit 1
fi

# 2. Check Node & npm
if command -v npm &>/dev/null; then
    echo "[OK] Node $(node --version) and npm $(npm --version) detected"
else
    echo "[ERROR] Node.js and npm are required."
    exit 1
fi

# 3. Initialize .env
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "[OK] Created .env"
else
    echo "[OK] .env already exists"
fi

# 4. Setup Python Virtual Environment
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment in .venv..."
    $PYTHON_BIN -m uv venv .venv || $PYTHON_BIN -m venv .venv
fi

echo "Installing Python dependencies..."
$PYTHON_BIN -m uv sync || .venv/bin/pip install -e ".[dev]"
echo "[OK] Python dependencies installed."

# 5. Setup Frontend
echo "Installing frontend dependencies..."
(cd frontend && npm install)
echo "[OK] Frontend dependencies installed."

echo -e "\n=== Setup Complete! Run ./scripts/start.sh to launch services ==="
