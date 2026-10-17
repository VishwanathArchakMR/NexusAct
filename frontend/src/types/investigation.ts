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
  hops: number;
}

export interface SurvivingPath {
  dependent_module_id: string;
  dependent_module_name: string;
  surviving_path: string[];
  hops: number;
}

export interface SimulationResult {
  scenario_id: string;
  target_module_id: string;
  target_module_name: string;
  baseline_paths_count: number;
  baseline_node_count: number;
  disappeared_paths_count: number;
  disappeared_paths: DisappearedPath[];
  surviving_paths_count: number;
  surviving_paths: SurvivingPath[];
  newly_isolated_modules: string[];
  surviving_modules_count: number;
  surviving_edges_count: number;
  blast_radius_score: number;
  is_incomplete: boolean;
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
  state: "PROPOSED" | "SAVED" | "APPROVED" | "SUBMITTING" | "VERIFIED" | "FAILED" | "UNKNOWN";
  can_execute: boolean;
  reason?: string | null;
  created_at: string;
}

export interface ActionExecutionResult {
  action_id: string;
  state: "PROPOSED" | "SAVED" | "APPROVED" | "SUBMITTING" | "VERIFIED" | "FAILED" | "UNKNOWN";
  external_issue_id?: number | null;
  external_issue_url?: string | null;
  read_back_verified: boolean;
  message: string;
  error_details?: string | null;
  executed_at: string;
}

export interface VulnerabilityFinding {
  vuln_id: string;
  package_name: string;
  package_version: string;
  ecosystem: string;
  severity: string;
  summary: string;
  details: string;
  fixed_version?: string | null;
  affected_version_range?: string | null;
  source_url: string;
  affected_modules: string[];
  reachability_status?: string | null;
}

export interface SecurityTriageOutput {
  repository_id: string;
  graph_name: string;
  manifests_inspected: string[];
  dependencies_analyzed_count: number;
  total_vulnerabilities_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  vulnerabilities_found: VulnerabilityFinding[];
  evidence_status: string;
  disclaimer: string;
  uncertainties: string[];
  remediation_proposal?: string | null;
}

export interface FraudPattern {
  pattern_type: string;
  severity: string;
  description: string;
  involved_nodes: string[];
  evidence_criteria: string;
  multi_hop_path?: string[];
  transaction_evidence?: Array<{ from: string; to: string; amount: number; time: string }>;
  risk_score?: number;
  amount_involved?: number;
  total_volume_usd?: number;
  details?: string;
  participating_nodes?: string[];
}

export interface BenignControl {
  account_id: string;
  status: string;
  reason?: string;
  status_reason?: string;
}

export interface FraudInvestigationOutput {
  graph_name: string;
  investigation_question: string;
  risk_indicator: string;
  risk_score?: number;
  risk_factors?: Array<{
    factor: string;
    weight: number;
    contribution: number;
    evidence: string;
  }>;
  patterns_detected: FraudPattern[];
  benign_controls: BenignControl[];
  total_suspicious_volume_usd: number;
  recommended_action: string;
  synthetic_disclaimer: string;
  uncertainties: string[];
  evidence_chain?: string[];
}

export interface SourceSnapshot {
  snapshot_id: string;
  repository_id: string;
  source_type: "local" | "github";
  canonical_source: string;
  default_branch?: string | null;
  commit_sha: string;
  working_tree_fingerprint?: string | null;
  graph_name: string;
  source_checked_at: string;
  ingested_at?: string | null;
  parser_version: string;
  ingestion_status: string;
  module_count: number;
  edge_count: number;
  known_gaps: string[];
  freshness_status: "FRESH" | "UPDATED" | "STALE_SOURCE_UNAVAILABLE" | "INGESTION_FAILED" | "SNAPSHOT_UNRESOLVED";
}

export interface SymbolOutlineItem {
  name: string;
  kind: "function" | "class" | "method";
  start_line: number;
  end_line: number;
  signature?: string;
  docstring?: string;
}

export interface FileGraphLinkage {
  has_graph_module: boolean;
  module_id?: string;
  module_name?: string;
  dependencies: string[];
  dependents: string[];
  modeled_level: string;
}

export interface FileTreeNode {
  name: string;
  path: string;
  type: "file" | "directory";
  size_bytes?: number;
  language?: string;
  has_graph_module?: boolean;
  module_id?: string;
  children?: FileTreeNode[];
}

export interface FileTreeResponse {
  repository_id: string;
  repository_name: string;
  commit_sha: string;
  total_files: number;
  total_directories: number;
  tree: FileTreeNode[];
  truncated: boolean;
}

export interface FileContentResponse {
  file_path: string;
  repository_id: string;
  commit_sha: string;
  start_line: number;
  end_line: number;
  total_lines: number;
  content: string;
  language: string;
  symbols?: SymbolOutlineItem[];
  graph_linkage?: FileGraphLinkage;
}


export interface InvestigationReport {
  investigation_id: string;
  question: string;
  target_module_id: string;
  target_module_name: string;
  status: string; // COMPLETED | AMBIGUOUS | UNRESOLVED | FAILED
  investigation_mode?: string | null;
  steps: InvestigationStep[];
  verification?: PathVerificationResult | null;
  summary: string;
  impact_result?: TraceImpactOutput | null;
  reviewer_result?: WhoKnowsOutput | null;
  pagerank_result?: PageRankOutput | null;
  simulation_result?: SimulationResult | null;
  neighborhood_result?: GraphNeighborhoodOutput | null;
  shortest_path_result?: ShortestPathOutput | null;
  source_metadata_result?: SourceMetadataOutput | null;
  security_triage_result?: SecurityTriageOutput | null;
  fraud_result?: FraudInvestigationOutput | null;
  source_snapshot?: SourceSnapshot | null;
  snapshot_id?: string | null;
  freshness_status?: string | null;
  working_tree_fingerprint?: string | null;
  action_proposal?: { title: string; body: string } | null;
  ambiguity_candidates?: CandidateMatch[] | null;
  repository_id?: string | null;
  graph_name?: string | null;
  commit_sha?: string | null;
  unresolved_reason?: string | null;
  is_heuristic_fallback?: boolean;
  budget_used: number;
  budget_remaining: number;
  timestamp: string;
}

export interface NeighborhoodNode {
  id: string;
  name: string;
  direction: string;
  source_file?: string | null;
}

export interface GraphNeighborhoodOutput {
  target_module_id: string;
  target_module_name: string;
  incoming_dependents: NeighborhoodNode[];
  outgoing_dependencies: NeighborhoodNode[];
  total_neighbors: number;
}

export interface ShortestPathOutput {
  source_id: string;
  target_id: string;
  connected: boolean;
  hops: number;
  path_nodes: string[];
  explanation: string;
}

export interface CandidateMatch {
  module_id: string;
  module_name: string;
  match_type: string;
}

export interface SourceCapability {
  source_id: string;
  source_type: "local" | "github";
  repository_identifier: string;
  data_categories: string[];
  status: string;
  retrieval_timestamp: string;
  data_freshness?: string | null;
  known_gaps: string[];
  error_details?: string | null;
}

export interface RepositoryRecord {
  id: string;
  name: string;
  owner?: string | null;
  repo?: string | null;
  source_type: "local" | "github";
  url_or_path: string;
  graph_name: string;
  default_branch: string;
  commit_sha: string;
  file_count: number;
  module_count: number;
  edge_count: number;
  contributor_count: number;
  commit_count: number;
  last_ingested_at?: string | null;
  status: string;
  capabilities: SourceCapability[];
  known_gaps: string[];
  parser_warnings: string[];
  extra_metadata?: Record<string, unknown>;
}

export interface SourceMetadataOutput {
  repository_id: string;
  repository_name: string;
  graph_name: string;
  commit_sha: string;
  sources: SourceCapability[];
  known_gaps: string[];
  disclaimer: string;
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
  provenance?: string;
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
  repository_id?: string;
  graph_name?: string;
  commit_sha: string;
  file_count: number;
  module_count: number;
  import_edge_count: number;
  commit_count: number;
  contributor_count: number;
  resolved_imports_count: number;
  unresolved_imports_count: number;
  skipped_files_count?: number;
  parser_warnings?: string[];
  data_gaps?: string[];
  ingested_at: string;
  status: string;
}

export interface InvestigationRequest {
  question: string;
  module_identifier?: string | null;
  repo_id?: string | null;
  graph_name?: string | null;
  max_budget?: number;
}

export interface PanelExplanationRequest {
  investigation_id: string;
  panel_id: string;
  question: string;
  target_id?: string | null;
  repo_id?: string | null;
  commit_sha?: string | null;
  data_summary?: Record<string, unknown>;
}

export interface PanelExplanationResponse {
  summary: string;
  what_you_are_looking_at: string;
  what_nexusact_found: string;
  why_it_matters: string;
  evidence_and_relationships: string[];
  confidence_and_limitations: string;
  recommended_next_step: string;
  provider_status: "gemini" | "cached" | "fallback";
  cache_key: string;
  model_name?: string | null;
}
