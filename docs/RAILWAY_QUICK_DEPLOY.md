# NexusAct on Railway — fast manual configuration

This deployment uses separate Railway services because Railway does not run the Compose stack as a single service.

## Services to create

Use the repository `VishwanathArchakMR/NexusAct`, branch `master`.

1. **falkordb** — choose Docker Image `falkordb/falkordb:v4.4.1`. No public domain or TCP proxy. Attach a persistent volume at `/data`. Set `BROWSER=0` and `REDIS_ARGS=--appendonly yes --appendfsync everysec`.
2. **backend** — GitHub repository, root directory left blank (repository root), Dockerfile path `backend/Dockerfile`. Keep the existing root `/railway.json` for this current backend service, or set the equivalent build settings manually if Config as Code is disabled. Health check `/health`. Do not create a public domain.
   Variables: `APP_ENV=production`, `PUBLIC_DEMO_MODE=true`, `FALKORDB_HOST=${{falkordb.RAILWAY_PRIVATE_DOMAIN}}`, `FALKORDB_PORT=6379`, `FALKORDB_PRIMARY_GRAPH=nexusact_main`, `CORS_ORIGINS=https://${{gateway.RAILWAY_PUBLIC_DOMAIN}}`, `LLM_PROVIDER=none`, `LOG_LEVEL=INFO`. If Railway has not automatically set `PORT`, use `PORT=8000`. AI keys are optional for the fallback demo.
3. **frontend** — same GitHub repository and branch, root directory `/frontend`, Dockerfile path `Dockerfile`. Health check `/`. Set build variable `VITE_API_BASE_URL` to an empty string so requests use the same origin. If a Config File Path option is available, select `/frontend/railway.json`; otherwise configure the build/health check directly in Settings.
4. **gateway** — same repository and branch, Root Directory `/gateway`, Builder `Dockerfile`, Dockerfile Path `Dockerfile`. The gateway folder contains its own Dockerfile and Caddyfile, so no Config-as-code path is required. Only this service gets a public domain; target port `80`. Health check `/gateway-health`. Configure the health check path `/gateway-health` directly in Settings; avoid the deprecated Config-as-code screen.
   Variables: `BACKEND_UPSTREAM=${{NexusAct.RAILWAY_PRIVATE_DOMAIN}}:8000` and `FRONTEND_UPSTREAM=${{frontend.RAILWAY_PRIVATE_DOMAIN}}:80`.

## Order

Create FalkorDB first, then backend, then frontend, and gateway last. After creating the gateway domain, the backend's `CORS_ORIGINS` variable should resolve to that domain; redeploy backend if needed. Wait for the backend `/ready` endpoint to return `READY` before judging graph workflows.

The backend seeds a small fictional graph only when the configured primary graph contains no `Module` nodes. It never deletes the graph or imports local data. The labels explicitly mark the sample as synthetic.

## Safety and cost

Only the gateway should be public. Do not add a public domain or TCP proxy to FalkorDB or backend. Keep `PUBLIC_DEMO_MODE=true`. Do not import or copy the developer's local graph. Railway's trial uses limited credits, so monitor the usage balance and stop unneeded services after judging.
