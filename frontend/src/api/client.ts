/**
 * API client for fetching telemetry, running investigations, querying graph, and actions.
 */

import { config } from "../config/env";
import type { LivenessData, ReadinessData, SystemStatusData } from "../types/system";
import type {
  IngestionReport,
  InvestigationReport,
  IssueProposal,
  ActionExecutionResult,
  ModuleSuggestion,
  SubgraphResponse,
  TraceImpactOutput,
  WhoKnowsOutput,
  PageRankOutput,
  SimulationResult,
  RepositoryRecord,
  SourceMetadataOutput,
} from "../types/investigation";

export class ApiError extends Error {
  statusCode: number;

  constructor(statusCode: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
  }
}

async function handleResponse<T>(res: Response, errorPrefix: string): Promise<T> {
  if (!res.ok) {
    let msg = `${errorPrefix} (Status ${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson.detail) {
        msg = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // ignore
    }
    throw new ApiError(res.status, msg);
  }
  return res.json();
}

// System Health Endpoints
export async function fetchLiveness(): Promise<LivenessData> {
  const url = `${config.apiBaseUrl}/api/v1/health`;
  const res = await fetch(url);
  return handleResponse<LivenessData>(res, "Liveness check failed");
}

export async function fetchReadiness(): Promise<ReadinessData> {
  const url = `${config.apiBaseUrl}/api/v1/ready`;
  const res = await fetch(url);
  if (res.status === 200 || res.status === 503) {
    return res.json();
  }
  throw new ApiError(res.status, `Readiness check failed with status ${res.status}`);
}

export async function fetchSystemStatus(): Promise<SystemStatusData> {
  const url = `${config.apiBaseUrl}/api/v1/system/status`;
  const res = await fetch(url);
  return handleResponse<SystemStatusData>(res, "System status fetch failed");
}

// Ingestion & Repository Endpoints
export async function triggerIngestion(repoPath?: string, repoId?: string): Promise<IngestionReport> {
  const url = `${config.apiBaseUrl}/api/v1/ingest`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repository_path: repoPath, repo_id: repoId }),
  });
  return handleResponse<IngestionReport>(res, "Ingestion failed");
}

export async function fetchRepositories(): Promise<RepositoryRecord[]> {
  const url = `${config.apiBaseUrl}/api/v1/ingest/repositories`;
  const res = await fetch(url);
  return handleResponse<RepositoryRecord[]>(res, "Failed to load repositories");
}

export async function registerRepository(payload: {
  source_type: "local" | "github";
  url_or_path: string;
  display_name?: string;
}): Promise<RepositoryRecord> {
  const url = `${config.apiBaseUrl}/api/v1/ingest/register`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<RepositoryRecord>(res, "Registration failed");
}

export async function cloneAndIngest(payload: {
  repo_id?: string;
  url_or_path?: string;
  source_type?: "local" | "github";
  display_name?: string;
}): Promise<IngestionReport> {
  const url = `${config.apiBaseUrl}/api/v1/ingest/clone-and-ingest`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<IngestionReport>(res, "Repository clone and ingestion failed");
}

export async function refreshRepository(repoId: string): Promise<IngestionReport> {
  const url = `${config.apiBaseUrl}/api/v1/ingest/refresh/${encodeURIComponent(repoId)}`;
  const res = await fetch(url, { method: "POST" });
  return handleResponse<IngestionReport>(res, "Repository refresh failed");
}

export async function fetchSourceMetadata(repoId: string): Promise<SourceMetadataOutput> {
  const url = `${config.apiBaseUrl}/api/v1/ingest/sources/${encodeURIComponent(repoId)}`;
  const res = await fetch(url);
  return handleResponse<SourceMetadataOutput>(res, "Failed to load source metadata");
}

export async function fetchModules(query?: string, limit = 50, repoId?: string): Promise<ModuleSuggestion[]> {
  const params = new URLSearchParams();
  if (query) params.append("query", query);
  params.append("limit", limit.toString());
  if (repoId) params.append("repo_id", repoId);
  const url = `${config.apiBaseUrl}/api/v1/ingest/modules?${params.toString()}`;
  const res = await fetch(url);
  return handleResponse<ModuleSuggestion[]>(res, "Failed to load modules");
}

// Investigation & Agent Endpoints
export async function runInvestigation(
  question: string,
  moduleIdentifier?: string | null,
  repoId?: string | null,
  maxBudget = 5
): Promise<InvestigationReport> {
  const url = `${config.apiBaseUrl}/api/v1/investigate`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      module_identifier: moduleIdentifier || null,
      repo_id: repoId || null,
      max_budget: maxBudget,
    }),
  });
  return handleResponse<InvestigationReport>(res, "Investigation request failed");
}

// Direct Tool Endpoints
export async function runTraceImpact(moduleIdentifier: string, maxDepth = 4, graphName?: string): Promise<TraceImpactOutput> {
  const url = `${config.apiBaseUrl}/api/v1/tools/trace-impact`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ module_identifier: moduleIdentifier, max_depth: maxDepth, graph_name: graphName }),
  });
  return handleResponse<TraceImpactOutput>(res, "Trace impact failed");
}

export async function runWhoKnows(moduleIdentifier: string, limit = 5, graphName?: string): Promise<WhoKnowsOutput> {
  const url = `${config.apiBaseUrl}/api/v1/tools/who-knows`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ module_identifier: moduleIdentifier, limit, graph_name: graphName }),
  });
  return handleResponse<WhoKnowsOutput>(res, "Who knows failed");
}

export async function runPageRank(limit = 10, graphName?: string): Promise<PageRankOutput> {
  const url = `${config.apiBaseUrl}/api/v1/tools/page-rank`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ limit, graph_name: graphName }),
  });
  return handleResponse<PageRankOutput>(res, "PageRank calculation failed");
}

export async function runSimulation(moduleIdentifier: string, graphName?: string): Promise<SimulationResult> {
  const url = `${config.apiBaseUrl}/api/v1/tools/simulate`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ module_identifier: moduleIdentifier, graph_name: graphName }),
  });
  return handleResponse<SimulationResult>(res, "Simulation failed");
}

// Subgraph Visualization Endpoint
export async function fetchSubgraph(
  centerModuleId?: string,
  depth = 2,
  limit = 100,
  repoId?: string
): Promise<SubgraphResponse> {
  const params = new URLSearchParams();
  if (centerModuleId) params.append("center_module_id", centerModuleId);
  params.append("depth", depth.toString());
  params.append("limit", limit.toString());
  if (repoId) params.append("repo_id", repoId);
  const url = `${config.apiBaseUrl}/api/v1/graph/subgraph?${params.toString()}`;
  const res = await fetch(url);
  return handleResponse<SubgraphResponse>(res, "Failed to load graph visualization");
}

// Action Endpoints
export async function proposeAction(investigationId: string, title: string, body: string): Promise<IssueProposal> {
  const url = `${config.apiBaseUrl}/api/v1/action/propose`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ investigation_id: investigationId, title, body }),
  });
  return handleResponse<IssueProposal>(res, "Failed to propose action");
}

export async function executeAction(actionId: string, approvedPayloadHash: string): Promise<ActionExecutionResult> {
  const url = `${config.apiBaseUrl}/api/v1/action/execute`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action_id: actionId, approved_payload_hash: approvedPayloadHash }),
  });
  return handleResponse<ActionExecutionResult>(res, "Failed to execute action");
}
