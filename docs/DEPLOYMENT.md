# NexusAct — Deployment Guide (Phase 5)

## Summary of Findings

This document records the honest deployment analysis performed for NexusAct Phase 5.

---

## 1. Zero-Cost Deployment Constraints (Honest Assessment)

NexusAct requires **three co-located services**:

| Service | Requirement |
|---|---|
| **FalkorDB** | Persistent Redis-protocol graph database (AOF or RDB). Requires a running container or managed service. |
| **FastAPI Backend** | Python 3.12, git installed, MCP server (port 8001), persistent file cache for repo clones. |
| **React SPA** | Static file hosting (nginx or CDN). Cheap/free on its own. |

The constraint is **FalkorDB**. It cannot be replaced by a flat file or ephemeral process.

### Free-tier options reviewed

| Platform | FalkorDB | Persistent Storage | Sleep Behaviour | Verdict |
|---|---|---|---|---|
| **Render.com Free** | Not available as managed | No persistent disk | Sleeps after 15 min idle | ❌ Insufficient (no DB, no disk) |
| **FalkorDB Cloud Free** | ✅ 100 MB RAM | ⚠️ No automated backups; deleted after ~1–14 days inactivity | No sleep | ⚠️ Usable for demos only; data can be lost |
| **Railway.app Trial** | Via Docker image | ✅ 0.5 GB volume (free), 5 GB (Hobby $5/mo) | No sleep (usage-billed) | ✅ Best zero-cost option (usage < $5 trial) |
| **Fly.io Free** | Via Docker image | ✅ 3 GB persistent volumes | No sleep | ✅ Good; generous free tier |

---

## 2. Recommended Local Deployment (Always Works)

The production docker-compose runs all three services locally with full persistence:

```powershell
# Copy and edit environment
cp .env.example .env

# Build and start all services (FalkorDB + Backend + Frontend)
docker compose -f docker-compose.prod.yml up --build -d

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Open frontend
Start-Process "http://localhost:3000"

# Stop (data preserved)
docker compose -f docker-compose.prod.yml down
```

**Data persistence**: FalkorDB graph data is stored in the `nexusact_falkordb_data` named Docker volume.
Repo clone cache is stored in `nexusact_repo_cache`.

Both volumes survive `docker compose down` and `docker restart`.

---

## 3. Live Deployment Option A: FalkorDB Cloud + Render.com (Demo Quality)

> [!WARNING]
> FalkorDB Cloud Free tier deletes inactive instances after ~14 days.
> Render.com Free tier sleeps after 15 minutes of inactivity.
> This combination is adequate for **hackathon demos only**, not production.

### Step 1: FalkorDB Cloud

1. Create a free instance at [app.falkordb.cloud](https://app.falkordb.cloud)
2. Note the connection details: `Host`, `Port`, `Password`
3. The free tier provides **100 MB RAM** (sufficient for the NexusAct graph model)

### Step 2: Deploy Backend to Render.com

1. Push code to GitHub (`git push origin master`)
2. Create a new **Web Service** on [render.com](https://render.com), connect your GitHub repo
3. Set **Runtime**: Docker, **Dockerfile Path**: `backend/Dockerfile`
4. Set **Root Directory**: `.` (project root)
5. Set environment variables:
   ```
   APP_ENV=production
   FALKORDB_HOST=<your-falkordb-cloud-host>
   FALKORDB_PORT=<your-falkordb-cloud-port>
   FALKORDB_PASSWORD=<your-falkordb-cloud-password>
   CORS_ORIGINS=https://<your-render-frontend-url>
   GITHUB_TOKEN=<optional>
   ```
6. Deploy. Note the backend URL (e.g., `https://nexusact-api.onrender.com`)

### Step 3: Deploy Frontend to Render.com Static Site

1. Create a **Static Site** on Render, connect same GitHub repo
2. Set **Root Directory**: `frontend`
3. Set **Build Command**: `npm ci && npm run build`
4. Set **Publish Directory**: `frontend/dist`
5. Set **Environment Variables**: `VITE_API_BASE_URL=https://nexusact-api.onrender.com`
6. Deploy

> [!NOTE]
> On Render Free, the backend sleeps after 15 minutes of inactivity.
> Add a UptimeRobot monitor (free) to ping `https://nexusact-api.onrender.com/health` every 10 minutes to prevent sleep during demos.

---

## 4. Live Deployment Option B: Railway.app (Better Persistence)

Railway's trial credit ($5) can run NexusAct for several days to weeks depending on usage.

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Create project from existing GitHub repo
railway init

# Deploy backend with Dockerfile
railway up --service backend

# Set environment variables
railway variables set APP_ENV=production FALKORDB_HOST=... CORS_ORIGINS=...

# Add persistent volume for FalkorDB
# (via Railway dashboard: Add Volume, mount at /data)
```

---

## 5. Persistence Strategy

### FalkorDB Data Persistence (Local Docker)
- **Mechanism**: AOF (Append-Only File) + everysec fsync — set in `docker-compose.prod.yml`
- **Location**: Docker named volume `nexusact_falkordb_data`
- **Backup**: `docker run --rm -v nexusact_falkordb_data:/data -v $(pwd):/backup alpine tar czf /backup/falkordb_backup.tar.gz /data`

### Repository Clone Cache
- **Location**: Docker named volume `nexusact_repo_cache` mounted at `/home/nexusact/.cache/nexusact`
- **Re-ingestion**: Cached clones mean subsequent ingests don't require re-cloning

---

## 6. Security Hardening Implemented

| Feature | Implementation |
|---|---|
| **CORS** | Explicit origin whitelist; no `*` wildcard |
| **TrustedHostMiddleware** | Enabled in `APP_ENV=production`; rejects forged Host headers |
| **API Docs** | Swagger/ReDoc disabled in production (`APP_ENV=production`) |
| **Non-root Docker user** | Backend and frontend containers run as `nexusact` (uid/gid: system) |
| **FalkorDB loopback** | Local: `127.0.0.1:6379` binding; Docker: internal network only |
| **No dynamic Cypher injection** | All queries use parameterized inputs |
| **Graph isolation** | Each repo gets dedicated graph (`repo_{slug}`); `PROTECTED_GRAPHS` blocks deletion |
| **Action hash binding** | Issue proposals require exact SHA-256 hash match before GitHub submission |

---

## 7. Quality Gates (Phase 16 Final)

| Suite | Result |
|---|---|
| `ruff check .` | ✅ 0 errors |
| `ruff format --check .` | ✅ Clean formatting |
| `mypy backend mcp_server` | ✅ 0 errors |
| `pytest -q` | ✅ **136/136 tests passing** |
| `oxlint` (frontend) | ✅ 0 errors, 0 warnings |
| `vitest run` | ✅ **18/18 tests passing** |
| `tsc -b && vite build` | ✅ Clean build |
