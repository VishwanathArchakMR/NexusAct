# Technical Recommendation: Multi-Tenant Architecture & User Authentication Journey

## Executive Summary

NexusAct currently operates as a self-hosted or dedicated single-workspace GraphAction Fabric (GAF) environment. As NexusAct prepares for multi-user hosted evaluation, enterprise pilots, and SaaS tiering, this document provides an architectural specification for a **production-ready user account and authentication journey**.

> [!IMPORTANT]
> **Implementation Scope Notice:** In accordance with Phase 21 requirements, NexusAct does **not** introduce half-baked or synthetic authentication code. This document serves as the formal technical blueprint and roadmap for multi-tenant identity, session lifecycle, and cryptographic tenant isolation in FalkorDB.

---

## 1. Managed Auth Provider Evaluation

To ensure enterprise-grade security (SOC2 Type II, ISO 27001, OIDC/SAML compatibility), we evaluated the leading managed authentication platforms:

| Criteria | **Clerk** (Recommended) | **Supabase Auth** | **Auth0 / Okta CIP** |
| :--- | :--- | :--- | :--- |
| **Primary Strength** | Best-in-class React/Vite components, instant organization switching | Tight PostgreSQL RLS integration, open-source core | Deep enterprise SAML/SCIM, complex RBAC rules |
| **Organization / B2B** | Native Multi-Tenant Organizations with role hierarchies | Requires custom tenant mapping tables | Enterprise Add-on required |
| **Session Security** | Short-lived JWTs (60s) + HttpOnly rolling refresh cookies | JWT tokens with client-side refresh | Configurable token lifetimes |
| **Developer Experience** | High: Prebuilt `<SignIn />`, `<UserButton />`, and hook APIs | Medium: Requires custom UI forms | Medium: Universal Login redirect flow |
| **Demo Visitor Access** | Native Guest / Anonymous session promotion | Anonymous auth supported | Requires custom mock tenant |

### Recommendation: Clerk or Supabase Auth
- For hosted cloud deployment, **Clerk** offers the fastest path to turn-key multi-organization support with zero friction for hackathon judges and evaluation teams.
- For air-gapped or on-premises deployments, **Supabase Auth** (or Keycloak) provides self-hostable OIDC.

---

## 2. Token Flow & Backend Session Verification

```
[ Frontend Client ] ──( 1. Authenticate via Clerk / OIDC )──> [ Auth Provider ]
        │                                                              │
        │ 2. Short-Lived JWT (sub=usr_xxx, org_id=org_yyy)            │
        ▼                                                              ▼
[ NexusAct FastAPI Gateway ] ──( 3. Verify JWKS Public Keys )──> [ Cached JWKS ]
        │
        ├─ 4. Extract Tenant Context: tenant_id = org_yyy ?? usr_xxx
        ├─ 5. Enforce RBAC / Role Matrix (Viewer, Investigator, Admin)
        │
        ▼
[ Isolated FalkorDB Namespaces ] (fin_<tenant_id>_<dataset_id>)
```

### FastAPIDep Authenticator (`backend/app/auth/dependencies.py` design)
```python
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()


async def get_current_tenant(credentials: HTTPAuthorizationCredentials = Security(security)) -> TenantContext:
    token = credentials.credentials
    # 1. Verify token signature against provider JWKS
    payload = verify_jwt_token(token)

    tenant_id = payload.get("org_id") or payload.get("sub")
    user_id = payload.get("sub")
    role = payload.get("org_role", "investigator")

    return TenantContext(tenant_id=tenant_id, user_id=user_id, role=role)
```

---

## 3. Multi-Tenant Graph Namespace Isolation in FalkorDB

FalkorDB supports completely isolated graph instances running on the same engine instance. To guarantee zero tenant data leakage:

### Deterministic Naming Conventions
- **Codebase Graphs:** `code_<tenant_id>_<repo_id>` (e.g. `code_org_8812_repo_nexusact`)
- **Financial Graphs:** `fin_<tenant_id>_<dataset_id>` (e.g. `fin_org_8812_ds_aml_benchmark`)
- **Simulation Sandbox Graphs:** `sim_<tenant_id>_<scenario_id>` (e.g. `sim_org_8812_scen_refactor_pr`)

### Strict Tenant Scoping in Cypher Execution
Every Cypher query executed by `cypher_engine.py` or MCP tools accepts an explicit, validated `graph_name`. The FastAPI routing layer enforces:
```python
if not graph_name.startswith(f"fin_{tenant.tenant_id}_"):
    raise HTTPException(status_code=403, detail="Unauthorized access to graph namespace")
```

---

## 4. Resource Quotas, Concurrency & Rate Limiting

To prevent Denial of Service (DoS) and noisy neighbor problems in multi-tenant environments:

1. **Dataset Ingestion Quotas:**
   - Free / Evaluation Tier: Max 2 active datasets, 10,000 transaction rows per dataset.
   - Enterprise Tier: Max 50 active datasets, 500,000 rows per dataset with chunked streaming.
2. **Concurrent Cypher Query Limiter:**
   - Maximum 4 concurrent Cypher graph traversals per tenant.
   - 15-second statement timeout configured on all FalkorDB connections via `TIMEOUT 15000`.
3. **LLM Reasoning & Explanation Quotas:**
   - Per-tenant token bucket rate limiting (Redis token bucket: 60 requests/minute for Gemini 2.5 Pro).
   - In-memory and Redis semantic caching of explanations keyed by `hash(tenant_id + graph_state_fingerprint)`.

---

## 5. Data Retention, Anonymization & Customer Privacy

When handling financial transaction networks, privacy guarantees are paramount:

1. **Client-Side Pseudonymization Sniffing:**
   - Warn users if unmasked IBANs, SSNs, or cleartext names are detected in uploaded CSV/JSON headers.
   - Support client-side deterministic SHA-256 tokenization of account identifiers before graph ingestion.
2. **Deterministic Time-To-Live (TTL):**
   - Temporary investigation datasets automatically purge their FalkorDB graph (`GRAPH.DELETE fin_<tenant_id>_<dataset_id>`) after 72 hours of inactivity.
   - Permanent datasets require explicit retention opt-in by an Organization Admin.
3. **Zero-Knowledge Audit Trail:**
   - Ingestion logs preserve schema mappings, row validation metrics, and topological findings without logging cleartext transaction payloads or customer identifiers.

---

## 6. Frictionless "Visitor Demo Mode" for Judges and Evaluators

To balance rigorous enterprise multi-tenancy with an instant, frictionless judging experience:

1. **Ephemeral Demo Tenant:**
   - Unauthenticated visitors automatically receive a signed, ephemeral session cookie mapping to a sandboxed visitor ID (`visitor_<nano_id>`).
   - The visitor has instant read-only access to pre-loaded benchmark datasets (such as the bundled Phase 21 AML Transaction Benchmark).
2. **One-Click Promotion:**
   - When a visitor uploads their own dataset or wants to save a custom graph investigation, a non-intrusive prompt allows converting the ephemeral session into a permanent organization account without losing any active work.
3. **No Credit Card or Phone Verification Required:**
   - Evaluation instances remain accessible with zero registration gates for hackathon evaluation and open verification.
