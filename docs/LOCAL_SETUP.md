# NexusAct — Local Development Setup & Operations Guide

## 1. System Prerequisites

The following software must be installed on your workstation:
- **Operating System:** Windows 10/11 (with WSL2), macOS, or Linux
- **Python:** Version 3.11 or 3.12 (validated with Python 3.12.8)
- **Node.js & npm:** Node.js v18+ (validated with Node v22.18.0, npm 10.9.3)
- **Docker & Docker Compose:** Docker 24+ (validated with Docker 29.1.3, Compose v2.40.3)
- **Git:** Git 2.40+ (validated with Git 2.50.1)

## 2. Environment Initialization

NexusAct uses a central `.env` file for all process configuration:
```powershell
# Windows PowerShell
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```

Review `.env` to verify standard local ports:
- `BACKEND_PORT=8000`
- `FALKORDB_PORT=6379`
- `FALKORDB_PRIMARY_GRAPH=nexusact_main`
- `CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173`

## 3. Automated One-Command Setup

Run the setup script:
```powershell
# Windows
.\scripts\setup.ps1

# Linux / macOS
chmod +x ./scripts/*.sh
./scripts/setup.sh
```

## 4. Starting the Services

### Option A: Complete System Launch
```powershell
# Windows
.\scripts\start.ps1

# Linux / macOS
./scripts/start.sh
```

### Option B: Individual Processes
1. **FalkorDB Database:**
   ```bash
   docker compose up -d
   ```
   *Verify with:* `docker ps`

2. **FastAPI Backend:**
   ```powershell
   .\.venv\Scripts\uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   *API Swagger Docs:* `http://127.0.0.1:8000/api/docs`

3. **React Frontend:**
   ```powershell
   cd frontend
   npm run dev
   ```
   *Dashboard:* `http://localhost:5173`

4. **MCP Diagnostic Server (Stdio):**
   ```powershell
   .\.venv\Scripts\python -m mcp_server.server
   ```

## 5. Stopping Services
```powershell
docker compose down
```
*Note: Your graph data in `nexusact_falkordb_data` persists across stop/start cycles.*
