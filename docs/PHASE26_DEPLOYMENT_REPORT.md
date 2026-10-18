# Phase 26 — Cloud Deployment Execution & Preflight Audit Report

**Project:** NexusAct — Graph-Native AI That Investigates, Simulates, and Acts  
**Architecture:** GraphAction Fabric (GAF)  
**Track:** **Agents That Act on Connected Data**  
**Repository:** `https://github.com/VishwanathArchakMR/NexusAct`  
**Baseline Commit:** `4d81cf686aa6fce3112921cc7569812a32221f2c`  
**Execution Date:** 2026-10-18  
**Phase Status:** **PREFLIGHT AUDIT COMPLETE — STOPPED AT AUTHENTICATION CHECKPOINT**  

---

## 1. Local Development Preservation Audit (Strict Invariant)

Prior to any deployment operations, the active local development environment was audited to establish an immutable baseline and ensure zero regression:

| Component | Status | Verified Configuration & State |
| :--- | :---: | :--- |
| **Commit SHA** | `4d81cf6` | Working tree clean, tracked on `origin/master`. |
| **FalkorDB Instance** | **READY** | Running on `127.0.0.1:6379` via `nexusact_falkordb` container. |
| **Primary Graph** | `nexusact_main` | **1,872 nodes, 2,288 relationships** verified intact. |
| **Registered Repositories** | **12** | All 12 codebase repositories present in registry. |
| **Financial Datasets** | **13** | All 13 financial callsets present with provenance. |
| **FastAPI Backend** | **READY** | Running on `http://127.0.0.1:8000` (Health: UP, Readiness: READY). |
| **Vite Frontend** | **READY** | Running on `http://localhost:5173` (HTTP 200 OK). |
| **Local Persistent Volume** | **PRESERVED** | `nexusact_falkordb_data` untouched. Production uses distinct `nexusact_falkordb_data_prod`. |

---

## 2. FalkorDB Multi-Architecture Registry & Cypher Compatibility Verification

The prompt instructed:
> *"The local configuration currently pins FalkorDB v4.4.1. The published Docker image for this version is listed as linux/amd64, so do not blindly deploy it on ARM64... Inspect the actual architecture manifests... prefer a production-only pinned ARM64-compatible v4 C-engine image, initially evaluating falkordb/falkordb:v4.20.4."*

### Authoritative Docker Hub Registry Inspection
Using Docker Hub Registry API v2, the exact multi-platform manifests were fetched and inspected:

1. **`falkordb/falkordb:v4.4.1` Manifest:**
   - Media Type: `application/vnd.docker.distribution.manifest.list.v2+json`
   - **`linux/amd64`:** Digest `sha256:34d62779b609a6ff7ad3e592a1c19dad149572ae6ae6b5b74fcef380eb574f5a`
   - **`linux/arm64`:** Digest `sha256:3af26d6f0c78827c17fbd2c283588f95699194d88075f81368dbf0f2954bb188`
   - **Conclusion:** `v4.4.1` ALREADY HAS NATIVE `linux/arm64` SUPPORT in the official registry!

2. **Candidate Evaluation: `falkordb/falkordb:v4.20.4`:**
   - Ran candidate container on isolated host port `6380` without touching local port `6379`.
   - Executed full test suite of NexusAct Cypher queries:
     - Node, relationship, and index creation: **PASSED**
     - Ephemeral `GRAPH.COPY` and `GRAPH.DELETE` sandbox simulation: **PASSED**
     - Multi-hop financial circular routing: **PASSED**
     - **ShortestPath Traversal:** **FAILED**
       - Query: `MATCH p = shortestPath((a:Module {name: 'entry'})-[:DEPENDS_ON*1..5]->(b:Module {name: 'leaf'})) RETURN length(p)`
       - Error: `redis.exceptions.ResponseError: FalkorDB currently only supports shortestPaths in WITH or RETURN clauses`
   - **Critical Compatibility Finding:** FalkorDB v4.20.4 introduced a breaking parser change that rejects `shortestPath` in `MATCH` statements, which would break NexusAct's multi-hop module resolution.
   - **Resolution:** Because `falkordb/falkordb:v4.4.1` natively supports `linux/arm64` (and `linux/amd64`) and executes all of NexusAct's queries without syntax errors, retaining the tested, pinned `v4.4.1` for production is the optimal, safe, and compatible path.

---

## 3. Cloud Access & Authentication Audit

In accordance with Section 2:
> *"Check whether the OCI CLI and account credentials are already configured. Verify access without printing credentials or secret configuration. If no usable OCI account session or credentials exist, do not invent or request private keys in the chat, and do not pretend a deployment has occurred. Stop at that checkpoint with the exact manual steps for me to sign in or configure the OCI CLI."*

### System Inspection Results:
- **OCI CLI (`oci`):** Not installed in Windows host or WSL2 environment.
- **OCI Credentials Directory (`~/.oci`):** Does not exist (`Test-Path $HOME\.oci` -> `False`).
- **Cloud Environment Variables:** No `OCI_*` or `ORACLE_*` credentials present.
- **SSH Key Pair:** Existing SSH public key detected at `C:\Users\vishw\.ssh\id_ed25519.pub`.

Because no authenticated OCI cloud session exists on this machine, **automated provisioning cannot proceed without user cloud credentials**. In strict compliance with the cost and security guardrails, execution was stopped at this checkpoint.

---

## 4. Manual Steps for the User to Proceed with Deployment

To deploy NexusAct to an Oracle Cloud Always Free VM (or any alternative free Linux VM), follow these straightforward steps:

### Option A: Provisioning via the Oracle Cloud Web Console (Fastest & Simplest)

1. **Log in to Oracle Cloud Console:**
   - Go to [https://cloud.oracle.com](https://cloud.oracle.com).
2. **Create Always Free Instance:**
   - Navigate to **Compute** → **Instances** → **Create Instance**.
   - **Image:** Ubuntu 24.04 LTS (Minimal or standard) or Oracle Linux 9.
   - **Shape:** Click **Change Shape** → select **Ampere (Arm)** → `VM.Standard.A1.Flex`.
   - Allocate **2 OCPUs** and **12 GB RAM** (100% Always Free eligible).
   - **Storage:** Use the default boot volume (47 GB or up to 100 GB, within the 200 GB Always Free limit).
   - **Networking:** Assign a public IPv4 address.
   - **SSH Key:** Paste your existing public SSH key located at:
     ```
     C:\Users\vishw\.ssh\id_ed25519.pub
     ```
   - Click **Create**.
3. **Configure Subnet Security List (Firewall):**
   - In the instance details, click on the **Virtual Cloud Network (VCN)** → **Security Lists** → **Default Security List**.
   - Add Ingress Rules:
     - **Port 80 (HTTP):** Source `0.0.0.0/0`, TCP Port `80`
     - **Port 443 (HTTPS):** Source `0.0.0.0/0`, TCP Port `443`
     - **Port 22 (SSH):** Already permitted.
4. **Point a Free Domain (e.g. DuckDNS):**
   - Note the instance's Public IP (e.g. `150.136.x.x`).
   - At [duckdns.org](https://www.duckdns.org), create a free subdomain (e.g. `nexusact.duckdns.org`) pointing to that IP.
5. **Connect & Deploy:**
   SSH into the VM from PowerShell:
   ```powershell
   ssh -i C:\Users\vishw\.ssh\id_ed25519 ubuntu@<VM_PUBLIC_IP>
   ```
   Run the quick launch commands:
   ```bash
   # 1. Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh
   sudo usermod -aG docker $USER && newgrp docker

   # 2. Clone Repository
   git clone https://github.com/VishwanathArchakMR/NexusAct.git
   cd NexusAct

   # 3. Create .env.prod
   cp .env.example .env.prod
   # Set DOMAIN=nexusact.duckdns.org, PUBLIC_DEMO_MODE=true, GEMINI_API_KEY=... in .env.prod

   # 4. Start Production Stack
   docker compose --env-file .env.prod -f docker-compose.prod.yml up --build -d
   ```

---

### Option B: Configure OCI CLI for Automated Deployment

If you prefer the agent to provision the VM via OCI CLI:
1. Install OCI CLI on Windows:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -Command "iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.ps1'))"
   ```
2. Configure credentials:
   ```powershell
   oci setup config
   ```
   Enter your User OCID, Tenancy OCID, and select your home region.
3. Once configured, instruct me to proceed and I will provision the instance and deploy automatically.

---

## 5. Local Development Health Re-Verification

- `.\scripts\status.ps1` confirms all local services remain healthy and untouched:
  - FalkorDB: `127.0.0.1:6379` (1,872 nodes, 2,288 relationships)
  - FastAPI: `http://127.0.0.1:8000` (READY)
  - Vite: `http://localhost:5173` (READY)
- No local data was deleted, migrated, or altered.
- All production configuration files remain cleanly isolated in `docker-compose.prod.yml` and `Caddyfile`.
