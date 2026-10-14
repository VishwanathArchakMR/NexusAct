#!/usr/bin/env bash
set -euo pipefail

echo "=== Running NexusAct Quality & Validation Suite ==="

# 1. Python Formatting & Linting
echo -e "\n[1/6] Checking Python formatting and linting (ruff)..."
.venv/bin/ruff check .
.venv/bin/ruff format --check .

# 2. Python Type Checking
echo -e "\n[2/6] Checking Python types (mypy)..."
.venv/bin/mypy backend mcp_server

# 3. Python Tests
echo -e "\n[3/6] Running Pytest suite..."
.venv/bin/pytest -v

# 4. Frontend Linting
echo -e "\n[4/6] Checking Frontend linting (oxlint)..."
(cd frontend && npm run lint)

# 5. Frontend Tests
echo -e "\n[5/6] Running Frontend tests (vitest)..."
(cd frontend && npm test)

# 6. Frontend Build
echo -e "\n[6/6] Verifying Frontend production build..."
(cd frontend && npm run build)

echo -e "\n=================================================="
echo -e "ALL QUALITY CHECKS PASSED SUCCESSFULLY!"
