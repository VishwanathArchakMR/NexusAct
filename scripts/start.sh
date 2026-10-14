#!/usr/bin/env bash
set -euo pipefail

echo "=== Starting NexusAct Services ==="

# 1. Start FalkorDB
echo "Starting FalkorDB via docker compose..."
docker compose up -d

echo "Verifying FalkorDB readiness on 127.0.0.1:6379..."
for i in {1..10}; do
    if nc -z 127.0.0.1 6379 2>/dev/null || (exec 3<>/dev/tcp/127.0.0.1/6379) 2>/dev/null; then
        echo "[OK] FalkorDB is ready."
        break
    fi
    sleep 1
done

# 2. Launch Backend
echo "Starting FastAPI Backend..."
.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!
echo "[OK] Backend running with PID $BACKEND_PID"

# 3. Launch Frontend
echo "Starting Frontend..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!
echo "[OK] Frontend running with PID $FRONTEND_PID"

echo -e "\nAll services launched!"
echo "Frontend: http://localhost:5173"
echo "API Docs: http://127.0.0.1:8000/api/docs"
