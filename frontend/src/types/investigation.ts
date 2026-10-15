/**
 * Type contracts for NexusAct Graph Intelligence and Investigation Engine.
 */

export type VerificationStatus = "VERIFIED" | "SUPPORTED" | "CONTRADICTED" | "UNKNOWN";

export interface VerificationCheck {
  name: string;
  passed: boolean;
  details: string;
}

export interface PathVerificationResult {
  status: VerificationStatus;
  target_module_id: string;
  checked_paths_count: number;
  valid_paths_count: number;
  invalid_paths_count: number;
  checks: VerificationCheck[];
  limitations: string[];
  validated_node_ids: string[];
  validated_edge_ids: string[];
  is_truncated: boolean;
}

export interface ImpactedModule {
  module_id: string;
  module_name: string;
  hops: number;
  path: string[];
  source_files: string[];
}

export interface TraceImpactOutput {
  target_module_id: string;
  target_module_name: string;
  max_depth: number;
  impacted_modules: ImpactedModule[];
  total_impacted_count: number;
  is_truncated: boolean;
  evidence_type: string;
  traversal_direction: string;
  caveat: string;
}

export interface ScoreBreakdown {
  files_touched_score: number;
  recency_score: number;
  ownership_score: number;
  review_history_score: number;
  files_touched_count: number;
  commits_count: number;
  days_since_last_touch: number;
  has_review_history: boolean;
}

export interface ReviewerCandidate {
  person_id: string;
  name: string;
  email: string;
  composite_score: number;
  rank: number;
  breakdown: ScoreBreakdown;
  rationale: string;
  missing_evidence: string[];
}

export interface WhoKnowsOutput {
  target_module_id: string;
  investigated_modules: string[];
  candidates: ReviewerCandidate[];
  scoring_formula: string;
  evidence_status: string;
}

export interface PageRankEntry {
  module_id: string;
  module_name: string;
  score: number;
  rank: number;
}

export interface PageRankOutput {
  graph_name: string;
  target_label: string;
  target_relationship: string;
  top_modules: PageRankEntry[];
  interpretation: string;
}

export interface DisappearedPath {
  dependent_module_id: string;
  dependent_module_name: string;
  broken_path: string[];
}

export interface SimulationResult {
  scenario_id: string;
  target_module_id: string;
  target_module_name: string;
  disappeared_paths_count: number;
  disappeared_paths: DisappearedPath[];
  disconnected_modules: string[];
  surviving_modules_count: number;
  surviving_edges_count: number;
  blast_radius_score: number;
  disclaimer: string;
}

export interface InvestigationStep {
  step_number: number;
  tool_name: string;
  arguments: Record<string, unknown>;
  purpose: string;
  status: "COMPLETED" | "FAILED" | "REJECTED";
  result_summary: string;
  execution_time_ms: number;
}

export interface IssueProposal {
  action_id: string;
  investigation_id: string;
  target_repository: string;
  title: string;
  body: string;
  payload_hash: string;
  state: "PROPOSED" | "APPROVED" | "SUBMITTING" | "VERIFIED" | "FAILED" | "UNKNOWN";
  can_execute: boolean;
  reason?: string | null;
  created_at: string;
}

export interface ActionExecutionResult {
  action_id: string;
  state: "PROPOSED" | "APPROVED" | "SUBMITTING" | "VERIFIED" | "FAILED" | "UNKNOWN";
  external_issue_id?: number | null;
  external_issue_url?: string | null;
  read_back_verified: boolean;
  message: string;
  error_details?: string | null;
  executed_at: string;
}

export interface InvestigationReport {
  investigation_id: string;
  question: string;
  target_module_id: string;
  target_module_name: string;
  status: string;
  steps: InvestigationStep[];
  verification?: PathVerificationResult | null;
  summary: string;
  impact_result?: TraceImpactOutput | null;
  reviewer_result?: WhoKnowsOutput | null;
  pagerank_result?: PageRankOutput | null;
  simulation_result?: SimulationResult | null;
  action_proposal?: { title: string; body: string } | null;
  budget_used: number;
  budget_remaining: number;
  timestamp: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties?: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  evidence_type: string;
  properties?: Record<string, unknown>;
}

export interface SubgraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
}

export interface ModuleSuggestion {
  id: string;
  name: string;
  file_path?: string | null;
}

export interface IngestionReport {
  repository_path: string;
  repository_name: string;
  commit_sha: string;
  file_count: number;
  module_count: number;
  import_edge_count: number;
  commit_count: number;
  contributor_count: number;
  resolved_imports_count: number;
  unresolved_imports_count: number;
  ingested_at: string;
  status: string;
}
