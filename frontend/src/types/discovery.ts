/**
 * Type contracts for Universal Public-Data Discovery and GAF Investigations.
 */

export interface SourceConnectorInfo {
  source_id: string;
  display_name: string;
  healthy: boolean;
  message: string;
  entity_types: string[];
  requires_auth: boolean;
}

export interface UniversalEntity {
  id: string;
  type: string;
  name: string;
  source: string;
  url: string;
}

export interface UniversalRelationship {
  source: string;
  target: string;
  type: string;
  confidence: string;
  evidence: string;
  provenance_url: string;
}

export interface UniversalInvestigationPlan {
  plan_id: string;
  question: string;
  target_entity_types: string[];
  relationship_focus: string[];
  selected_source_ids: string[];
  search_keywords: string[];
  max_results_per_source: number;
  traversal_depth: number;
  is_heuristic_fallback: boolean;
  input_mode?: string;
  repository_id?: string | null;
  graph_name?: string | null;
  commit_sha?: string | null;
}

export interface UniversalInvestigationResult {
  investigation_id: string;
  question: string;
  plan: UniversalInvestigationPlan;
  sources_queried: Record<
    string,
    {
      source_id: string;
      records_fetched: number;
      error?: string | null;
      coverage_notes: string[];
    }
  >;
  records_ingested: number;
  entities: UniversalEntity[];
  relationships: UniversalRelationship[];
  paths: Array<{
    nodes: Array<{ id: string; label: string; type: string }>;
    relationships: Array<{ type: string; confidence: string; evidence: string; provenance: string }>;
  }>;
  findings: string[];
  summary: string;
  approach?: string;
  next_action?: {
    id: string;
    title: string;
    description: string;
    status: string;
  } | null;
  coverage_limitations: string[];
  execution_time_ms: number;
  input_mode?: string;
  repository_id?: string | null;
  graph_name?: string | null;
  commit_sha?: string | null;
  context?: Record<string, unknown>;
  scoped_subgraph?: PublicSubgraphResponse;
}

export interface SavedInvestigation {
  investigation_id: string;
  question: string;
  summary: string;
  sources: string;
  approach: string;
  action_id: string;
  action_title: string;
  action_desc: string;
  action_status: string;
  created_at?: number;
  input_mode?: string;
  repository_id?: string | null;
  graph_name?: string | null;
  commit_sha?: string | null;
}

export interface PublicSubgraphResponse {
  nodes: Array<{
    id: string;
    type: string;
    label: string;
    properties?: Record<string, unknown>;
  }>;
  edges: Array<{
    source: string;
    target: string;
    type: string;
    properties?: Record<string, unknown>;
  }>;
  total_nodes: number;
  total_edges: number;
}
