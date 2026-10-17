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
  SourceSnapshot,
  FileContentResponse,
  FileTreeResponse,
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

export async function fetchSystemStatus(repoId?: string): Promise<SystemStatusData> {
  const url = repoId
    ? `${config.apiBaseUrl}/api/v1/system/status?repo_id=${encodeURIComponent(repoId)}`
    : `${config.apiBaseUrl}/api/v1/system/status`;
  const res = await fetch(url);
  return handleResponse<SystemStatusData>(res, "System status fetch failed");
}

export async function fetchRecentInvestigations(
  limit = 10,
  repoId?: string
): Promise<{ investigations: import("../types/discovery").SavedInvestigation[]; total: number }> {
  const params = new URLSearchParams({ limit: limit.toString() });
  if (repoId) params.append("repo_id", repoId);
  const url = `${config.apiBaseUrl}/api/v1/investigation/recent?${params.toString()}`;
  try {
    const res = await fetch(url);
    if (res.ok) {
      const data = await res.json();
      const mapped: import("../types/discovery").SavedInvestigation[] = (data.investigations || []).map((inv: any) => ({
        investigation_id: inv.investigation_id,
        question: inv.question,
        summary: inv.summary || "",
        sources: inv.repository_id || inv.graph_name,
        approach: inv.verification_status || "COMPLETED",
        action_id: "",
        action_title: "",
        action_desc: "",
        action_status: inv.status || "COMPLETED",
        created_at: inv.created_at ? Math.floor(new Date(inv.created_at).getTime() / 1000) : undefined,
        input_mode: inv.investigation_mode,
        repository_id: inv.repository_id,
        graph_name: inv.graph_name,
        commit_sha: inv.commit_sha,
      }));
      return { investigations: mapped, total: data.total || mapped.length };
    }
  } catch (err) {
    console.warn("Unified recent investigations endpoint unavailable, falling back to discover store:", err);
  }
  return fetchSavedInvestigations(limit);
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
export async function fetchRepositorySnapshot(
  repoId: string,
  refresh = false
): Promise<SourceSnapshot> {
  const url = `${config.apiBaseUrl}/api/v1/ingest/snapshot/${encodeURIComponent(repoId)}?refresh=${refresh}`;
  const res = await fetch(url);
  return handleResponse<SourceSnapshot>(res, "Failed to load repository snapshot");
}

export async function fetchFileContent(
  repoId: string,
  filePath: string,
  startLine = 1,
  endLine = 200
): Promise<FileContentResponse> {
  const params = new URLSearchParams({
    repo_id: repoId,
    file_path: filePath,
    start_line: startLine.toString(),
    end_line: endLine.toString(),
  });
  const url = `${config.apiBaseUrl}/api/v1/ingest/file-content?${params.toString()}`;
  const res = await fetch(url);
  return handleResponse<FileContentResponse>(res, "Failed to fetch file content");
}

export async function fetchFileTree(
  repoId: string,
  subpath?: string,
  maxDepth = 5
): Promise<FileTreeResponse> {
  const params = new URLSearchParams({ repo_id: repoId, max_depth: maxDepth.toString() });
  if (subpath) params.append("subpath", subpath);
  const url = `${config.apiBaseUrl}/api/v1/ingest/file-tree?${params.toString()}`;
  const res = await fetch(url);
  return handleResponse<FileTreeResponse>(res, "Failed to load repository file tree");
}


export async function runInvestigation(
  question: string,
  moduleIdentifier?: string | null,
  repoId?: string | null,
  maxBudget = 5,
  investigationMode?: string | null
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
      investigation_mode: investigationMode || null,
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

export async function saveInternalAction(actionId: string): Promise<IssueProposal> {
  const url = `${config.apiBaseUrl}/api/v1/action/save-internal`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action_id: actionId }),
  });
  return handleResponse<IssueProposal>(res, "Failed to save internal action");
}

// Universal Discovery Endpoints (Phase 7 GAF)
export async function fetchPublicSources(): Promise<{
  sources: Record<string, import("../types/discovery").SourceConnectorInfo>;
  total_connectors: number;
}> {
  const url = `${config.apiBaseUrl}/api/v1/discover/sources`;
  const res = await fetch(url);
  return handleResponse(res, "Failed to fetch source connectors");
}

export async function askUniversalGaf(
  question: string,
  selectedSources?: string[],
  maxResults = 5,
  options?: {
    inputMode?: string;
    repositoryId?: string | null;
    graphName?: string | null;
    commitSha?: string | null;
  }
): Promise<import("../types/discovery").UniversalInvestigationResult> {
  const url = `${config.apiBaseUrl}/api/v1/discover/ask-gaf`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      selected_sources: selectedSources,
      max_results: maxResults,
      input_mode: options?.inputMode || "public",
      repository_id: options?.repositoryId || null,
      graph_name: options?.graphName || null,
      commit_sha: options?.commitSha || null,
    }),
  });
  return handleResponse<import("../types/discovery").UniversalInvestigationResult>(
    res,
    "Universal Ask GAF investigation failed"
  );
}

export async function fetchPublicSubgraph(
  limit = 50
): Promise<import("../types/discovery").PublicSubgraphResponse> {
  const url = `${config.apiBaseUrl}/api/v1/discover/subgraph?limit=${limit}`;
  const res = await fetch(url);
  return handleResponse<import("../types/discovery").PublicSubgraphResponse>(
    res,
    "Failed to load public knowledge graph"
  );
}

export async function fetchSavedInvestigations(
  limit = 10
): Promise<{ investigations: import("../types/discovery").SavedInvestigation[]; total: number }> {
  const url = `${config.apiBaseUrl}/api/v1/discover/investigations?limit=${limit}`;
  const res = await fetch(url);
  return handleResponse(res, "Failed to load saved investigations");
}

export async function confirmInvestigationAction(
  actionId: string
): Promise<{ action_id: string; status: string; message: string }> {
  const url = `${config.apiBaseUrl}/api/v1/discover/actions/confirm`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action_id: actionId }),
  });
  return handleResponse(res, "Failed to confirm action");
}

export async function fetchPanelExplanation(
  payload: import("../types/investigation").PanelExplanationRequest
): Promise<import("../types/investigation").PanelExplanationResponse> {
  const url = `${config.apiBaseUrl}/api/v1/investigation/explain-panel`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<import("../types/investigation").PanelExplanationResponse>(
    res,
    "Failed to generate panel explanation"
  );
}

export async function testLLMConnectivity(): Promise<import("../types/system").LLMTestResult> {
  const url = `${config.apiBaseUrl}/api/v1/system/llm-test`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  return handleResponse<import("../types/system").LLMTestResult>(
    res,
    "Failed to test LLM connectivity"
  );
}

// Financial Investigation Endpoints (Phase 21 GAF)
export async function fetchFinancialDatasets(): Promise<import("../types/investigation").FinancialDatasetMetadata[]> {
  const url = `${config.apiBaseUrl}/api/v1/finance/datasets`;
  const res = await fetch(url);
  return handleResponse<import("../types/investigation").FinancialDatasetMetadata[]>(
    res,
    "Failed to fetch financial datasets"
  );
}

export async function fetchActiveFinancialDataset(): Promise<import("../types/investigation").FinancialDatasetMetadata | null> {
  const url = `${config.apiBaseUrl}/api/v1/finance/datasets/active`;
  const res = await fetch(url);
  return handleResponse<import("../types/investigation").FinancialDatasetMetadata | null>(
    res,
    "Failed to fetch active financial dataset"
  );
}

export async function activateFinancialDataset(datasetId: string): Promise<import("../types/investigation").FinancialDatasetMetadata> {
  const url = `${config.apiBaseUrl}/api/v1/finance/datasets/${encodeURIComponent(datasetId)}/activate`;
  const res = await fetch(url, { method: "POST" });
  return handleResponse<import("../types/investigation").FinancialDatasetMetadata>(
    res,
    "Failed to activate financial dataset"
  );
}

export async function deleteFinancialDataset(datasetId: string): Promise<{ message: string }> {
  const url = `${config.apiBaseUrl}/api/v1/finance/datasets/${encodeURIComponent(datasetId)}`;
  const res = await fetch(url, { method: "DELETE" });
  return handleResponse<{ message: string }>(res, "Failed to delete financial dataset");
}

export async function previewFinancialDataset(file: File): Promise<import("../types/investigation").DatasetPreviewResponse> {
  const url = `${config.apiBaseUrl}/api/v1/finance/preview`;
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(url, {
    method: "POST",
    body: formData,
  });
  return handleResponse<import("../types/investigation").DatasetPreviewResponse>(
    res,
    "Failed to preview financial dataset"
  );
}

export async function ingestFinancialDataset(
  file: File,
  datasetName: string,
  columnMapping?: import("../types/investigation").ColumnMapping
): Promise<import("../types/investigation").FinancialDatasetMetadata> {
  const url = `${config.apiBaseUrl}/api/v1/finance/ingest`;
  const formData = new FormData();
  formData.append("file", file);
  formData.append("dataset_name", datasetName);
  if (columnMapping) {
    formData.append("column_mapping", JSON.stringify(columnMapping));
  }
  const res = await fetch(url, {
    method: "POST",
    body: formData,
  });
  return handleResponse<import("../types/investigation").FinancialDatasetMetadata>(
    res,
    "Failed to ingest financial dataset"
  );
}

export async function loadSampleBenchmarkDataset(): Promise<import("../types/investigation").FinancialDatasetMetadata> {
  const url = `${config.apiBaseUrl}/api/v1/finance/load-sample`;
  const res = await fetch(url, { method: "POST" });
  return handleResponse<import("../types/investigation").FinancialDatasetMetadata>(
    res,
    "Failed to load sample benchmark dataset"
  );
}

export async function investigateFinancialDataset(
  datasetId?: string,
  maxHops = 4
): Promise<import("../types/investigation").FinancialInvestigationResult> {
  const url = `${config.apiBaseUrl}/api/v1/finance/investigate`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, max_hops: maxHops }),
  });
  return handleResponse<import("../types/investigation").FinancialInvestigationResult>(
    res,
    "Financial dataset investigation failed"
  );
}

export async function fetchFinancialSubgraph(
  datasetId?: string,
  centerAccountId?: string,
  depth = 2,
  limit = 80
): Promise<import("../types/investigation").SubgraphResponse> {
  const params = new URLSearchParams();
  if (centerAccountId) params.append("center_account_id", centerAccountId);
  params.append("depth", depth.toString());
  params.append("limit", limit.toString());
  const dsParam = datasetId ? encodeURIComponent(datasetId) : "active";
  const url = `${config.apiBaseUrl}/api/v1/finance/datasets/${dsParam}/subgraph?${params.toString()}`;
  const res = await fetch(url);
  return handleResponse<import("../types/investigation").SubgraphResponse>(
    res,
    "Failed to load financial transaction subgraph"
  );
}



