# NexusAct — Future Deployment Portability & Hosting Architecture

## 1. Local Execution is the Current Target

Phase 1 explicitly targets local computer execution. No cloud accounts, paid services, or public hosting environments are required or configured for Phase 1.

## 2. Decoupled Architecture Principles

To ensure zero lock-in and seamless future deployment portability:

1. **Independent Frontend:** The React frontend compiles to a self-contained static single-page application (`dist/index.html`, `dist/assets/*`). It can be hosted on any static object store or CDN (Vercel, Netlify, Cloudflare Pages, S3).
2. **Environment-Driven Routing:** The frontend references `VITE_API_BASE_URL` rather than hardcoded `localhost:8000`. Deploying to a remote server requires only setting this environment variable during build.
3. **Containerized Database:** FalkorDB runs as a standard container with volume persistence (`/data`). It can be deployed on any container runner with persistent volume support (Docker Compose on VPS, Fly.io, Railway, Kubernetes with PVC).
4. **Stateless Backend:** The FastAPI application maintains no in-memory state between requests; all state resides in FalkorDB. The backend can scale horizontally or run as a containerized service (Cloud Run, ECS, Fly.io).

## 3. Important Hosting Realities to Keep in Mind
- Deploying the frontend to a static host (e.g. Vercel) does **not** host the backend or FalkorDB.
- FalkorDB requires a stateful persistent disk; ephemeral container runtimes without mounted storage will lose graph data upon container recycling.
- When containerized, the backend connects to FalkorDB via the internal Docker bridge (`falkordb:6379`), whereas on the host it connects via `127.0.0.1:6379`. This is handled seamlessly through `FALKORDB_HOST`.
