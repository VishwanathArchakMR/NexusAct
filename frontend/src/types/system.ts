/**
 * System and telemetry data types for NexusAct Frontend.
 */

export type ServiceStatus = "ONLINE" | "OFFLINE" | "LOADING" | "ERROR" | "DEGRADED" | "READY" | "UNAVAILABLE";

export interface LivenessData {
  status: string;
  app_name: string;
  app_version: string;
  app_env: string;
}

export interface ReadinessDatabaseDetails {
  connected: boolean;
  host: string;
  port: number;
  graph: string;
  details?: {
    graph_name: string;
    connected: boolean;
    status: string;
    node_count: number;
    edge_count: number;
  };
  error?: string;
}

export interface ReadinessData {
  status: "READY" | "UNAVAILABLE" | "DEGRADED";
  database: ReadinessDatabaseDetails;
  schema_version: string;
}

export interface SystemStatusData {
  app_name: string;
  app_env: string;
  version: string;
  backend_status: string;
  falkordb_status: string;
  falkordb_host: string;
  falkordb_port: number;
  primary_graph: string;
  node_count: number;
  edge_count: number;
  mcp_server_configured: boolean;
  mcp_port: number;
  active_repo_id?: string;
  active_repo_name?: string;
  commit_sha?: string;
  freshness_status?: string;
  llm_provider?: string;
  llm_configured?: boolean;
  planner_provider?: string;
  planner_model?: string;
  explanation_provider?: string;
  explanation_model?: string;
  credentials_detected?: boolean;
  action_service_configured?: boolean;
  action_approval_required?: boolean;
  mcp_tools?: string[];
  subsystem_health?: Record<string, string>;
}

export interface LLMTestResult {
  status: "GEMINI_ACTIVE" | "FALLBACK_ACTIVE" | "NOT_CONFIGURED" | "PROVIDER_UNAVAILABLE";
  provider: string;
  model: string;
  latency_ms: number;
  message: string;
  credentials_detected: boolean;
}

