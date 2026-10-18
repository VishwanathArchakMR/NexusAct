# NexusAct — Pre-Deployment Verification Checklist

**Project:** NexusAct — Graph-Native AI That Investigates, Simulates, and Acts  
**Document:** Pre-Deployment Quality Gates & Operational Checklist  
**Revision:** Phase 25 Release Candidate  
**Date:** 2026-10-18  

---

## 1. Automated Local Quality Gates

Run these commands locally prior to initiating any deployment. All must pass with zero errors.

### Python Backend Gates
```bash
# 1. Linting & Code Style
.\.venv\Scripts\ruff.exe check .
# Expected: All checks passed!

# 2. Code Formatting
.\.venv\Scripts\ruff.exe format --check .
# Expected: 152 files already formatted

# 3. Static Type Analysis
.\.venv\Scripts\mypy.exe backend mcp_server
# Expected: Success: no issues found in 73 source files

# 4. Comprehensive Backend Unit & Integration Tests
.\.venv\Scripts\pytest.exe -q
# Expected: 176 passed in ~60s (including test_public_demo_mode.py)
```

### TypeScript / React Frontend Gates
```bash
cd frontend

# 1. ESLint / OxLint
npm run lint
# Expected: Found 0 warnings and 0 errors.

# 2. Vitest Test Suite
npm test
# Expected: 8 test files passed, 26 tests passed

# 3. Production Compilation & Bundle Check
npm run build
# Expected: built in < 1s with dist/ assets generated
cd ..
```

### Container Configuration Gates
```bash
# 1. Validate Production Docker Compose Specification
docker compose -f docker-compose.prod.yml config
# Expected: Valid YAML representation, exit code 0

# 2. Verify Port Isolation
# Confirm that ONLY caddy publishes ports 80 and 443.
# FalkorDB (6379) and FastAPI (8000) MUST NOT appear under published ports.
```

---

## 2. Security & Secret Exposure Audit

- [x] **No Version-Controlled Secrets:** Ensure `.env` is listed in `.gitignore` and has never been committed.
- [x] **No Hardcoded API Keys:** Grep search confirmed zero raw Gemini, Google, or GitHub tokens in code or configs.
- [x] **Safe Example Configurations:** `.env.example` contains only empty string placeholders and explanatory comments.
- [x] **Server-Side API Key Isolation:** `GEMINI_API_KEY`, `GOOGLE_API_KEY`, and `GITHUB_TOKEN` are passed exclusively to the backend container via environment variables and are never baked into client bundles.
- [x] **Public Demo Mode Gated:** When `PUBLIC_DEMO_MODE=true`, mutations (`/api/v1/ingest`, `/api/v1/finance/ingest`, `/api/v1/action/execute`) return HTTP 403 Forbidden.

---

## 3. Server Preflight Checklist (For Subsequent Phase)

Before executing `docker compose -f docker-compose.prod.yml up` on the target VM:

1. **OS & Architecture Check:**
   ```bash
   uname -m
   # aarch64 (Ampere A1) or x86_64
   cat /etc/os-release
   # Ubuntu 22.04/24.04 LTS or Oracle Linux 8/9
   ```
2. **Resource Allocation Check:**
   ```bash
   free -m
   # Verify at least 4 GB available RAM (12-24 GB recommended on OCI A1)
   df -h /
   # Verify at least 20 GB free disk space
   ```
3. **Firewall & Security List:**
   - Ingress permitted on TCP port `80` (HTTP).
   - Ingress permitted on TCP port `443` (HTTPS).
   - Ingress permitted on TCP port `22` (SSH).
   - Port `6379` strictly BLOCKED from external internet.
   - Port `8000` strictly BLOCKED from external internet.
4. **DNS Propagation:**
   ```bash
   dig +short <YOUR_DOMAIN>
   # Must return the public IP address of the VM
   ```
5. **Docker Engine & Compose:**
   ```bash
   docker --version && docker compose version
   ```

---

## 4. Post-Deployment Smoke Test Protocol

Once the production stack is started on the VM:

1. **Check Container Status:**
   ```bash
   docker compose -f docker-compose.prod.yml ps
   # All 4 containers (caddy, frontend, backend, falkordb) must show Up (healthy)
   ```
2. **Verify Backend Health via Local Loopback:**
   ```bash
   curl -s http://localhost/health | grep '"status":"UP"'
   curl -s http://localhost/ready | grep '"status":"READY"'
   ```
3. **Verify Public HTTPS:**
   - Open browser to `https://<YOUR_DOMAIN>/health`.
   - Verify valid Let's Encrypt SSL certificate.
4. **Verify Application Functionality:**
   - Open `https://<YOUR_DOMAIN>`.
   - Verify Graph Explorer renders nodes and relationships.
   - Run a test query in Graph AI Chat (e.g., `"Which modules depend on client?"`).
   - Run a Counterfactual Scenario Simulation on a candidate module.
   - Check Reviewers & Authors expertise ranking.
   - Switch to Financial tab and verify AML benchmark graph exploration.
5. **Verify Public Demo Mode Protection:**
   ```bash
   curl -i -X POST https://<YOUR_DOMAIN>/api/v1/ingest \
     -H "Content-Type: application/json" \
     -d '{"repository_path": "."}'
   # MUST return HTTP/2 403 Forbidden
   ```
