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
}
