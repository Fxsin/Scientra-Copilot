/* ── /health ── */

export interface HealthResponse {
  api_status: string;
  lancedb_status: string;
  table_counts: Record<string, number>;
  embedding_model: string | null;
  timestamp: string;
}

/* ── /stats ── */

export interface StatsResponse {
  paper_count: number;
  metadata_embedding_count: number;
  summary_embedding_count: number;
  chunk_embedding_count: number;
  tag_distribution: Record<string, number>;
  year_distribution: Record<string, number>;
}

/* ── /papers ── */

export interface PaperItem {
  paper_id: string;
  title: string;
  authors: string[];
  year: number | null;
  journal: string;
  doi: string;
  tags: string[];
  species: string[];
  toxin: string[];
  abstract_snippet: string;
  summary_snippet: string | null;
}

export interface PapersResponse {
  papers: PaperItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/* ── /query ── */

export type QueryMode = "keyword" | "vector" | "hybrid";
export type QueryLevel = "metadata" | "summary" | "chunks" | "all";

export interface QueryRequest {
  query: string;
  mode: QueryMode;
  top_k: number;
  level: QueryLevel;
  toxin?: string | string[];
  host?: string | string[];
  mechanism?: string | string[];
  method?: string | string[];
  year_range?: number[];
  paper_id?: string;
  doi?: string;
  include_candidate_tags?: boolean;
}

export interface QueryResultItem {
  paper_id: string;
  title?: string;
  journal?: string;
  year?: number;
  doi?: string;
  authors?: string[];
  tags?: string[];
  score?: number;
  // Extended fields used by older components
  record_id?: string;
  citation_anchor?: string;
  source_section?: string;
  level?: string;
  text_preview?: string;
  matched_tags?: string[];
  assigned_tags?: string[] | Record<string, string[]>;
}

export interface QueryResponse {
  query: string;
  mode: string;
  top_k: number;
  level: string;
  total: number;
  results: QueryResultItem[];
  include_candidate_tags: boolean;
  policy: Record<string, string>;
}

/* ── /paper/{id}/... ── */

export interface PaperMetadata {
  paper_id: string;
  title: string;
  journal: string;
  year: number | null;
  doi: string;
  authors: string[];
  tags: string[];
  species: string[];
  toxin: string[];
  method: string[];
  mechanism: string[];
  abstract?: string;
  metadata?: Record<string, unknown>;
}

export interface PaperTags {
  paper_id: string;
  tags: string[];
  species: string[];
  toxin: string[];
  method: string[];
  mechanism: string[];
  assigned_tags?: string[] | Record<string, string[]>;
  candidate_tags?: string[] | Record<string, string[]>;
}

export interface PaperSummary {
  paper_id: string;
  summary_path: string | null;
  text: string | null;
  sections: Record<string, string[]>;
  title?: string;
  summary?: string;
  citation_anchors?: unknown[];
}

/* ── Network / Research Map ── */

export interface NetworkNode {
  id: string;
  label: string;
  type: string;
  group?: string;
  size?: number;
  color?: string;
  count?: number;
  x?: number;
  y?: number;
  title?: string;
  year?: number;
  journal?: string;
  tags?: string[];
}

export interface NetworkLink {
  source: string | NetworkNode;
  target: string | NetworkNode;
  value?: number;
  type?: string;
  weight?: number;
  label?: string;
}

export interface KnowledgeNetworkResponse {
  status?: string; source?: string; paper_count?: number;
  node_count?: number; edge_count?: number;
  generated_at?: string;
  nodes: NetworkNode[] | KnowledgeNode[];
  links?: NetworkLink[];
  edges?: KnowledgeEdge[];
  node_groups?: string[];
  insights?: string[];
  message?: string;
  stats?: {
    node_count: number;
    link_count: number;
    paper_count: number;
    toxin_count: number;
    host_count: number;
    mechanism_count: number;
    method_count: number;
  };
}

export interface ResearchMapTopic {
  cluster_id?: string;
  id?: string;
  name: string;
  type?: string;
  trend?: string;
  paper_count: number;
  count?: number;
  avg_year?: number;
  year_range?: [number, number] | number[];
  keywords?: string[];
  summary?: string;
  papers?: TopicPaper[];
  representative_papers?: TopicPaper[];
  method_diversity?: number;
  key_methods?: string[];
  top_tags?: string[];
  confidence?: string;
  recent_count?: number;
  growth_rate?: string;
  gap_tags?: string[];
  connected_to?: string[];
  opportunity?: string;
  year_span?: string;
  year_distribution?: YearCount[];
  recent_ratio?: number;
  trend_label?: "emerging" | "active" | "stable" | "dormant" | "sparse" | "unknown";
  trend_reason?: string;
  evolution_phases?: TopicEvolutionPhase[];
  related_topics?: RelatedTopicRef[];
  cohesion_score?: number;
  cohesion_label?: string;
  facet_distribution?: FacetDistributionItem[];
  is_merged?: boolean;
  subtopics?: SubtopicRef[];
  merge_info?: {
    merged_from: string[];
    merge_reason: string;
    max_similarity: number;
  } | null;
  merged_into?: {
    from_cluster_id: string;
    parent_cluster_id: string;
    message: string;
  };
}

export interface SubtopicRef {
  cluster_id: string;
  name: string;
  paper_count: number;
  keywords: string[];
  year_range: [number, number] | number[];
  merge_reason: string;
  similarity_to_parent: number;
}

export interface TopicPaper {
  paper_id: string;
  title: string;
  authors?: string[];
  year?: number | null;
  journal?: string | null;
  doi?: string | null;
  summary?: string | null;
  evidence?: Record<string, unknown> | null;
  topic_relevance?: number;
  relevance_label?: "high" | "medium" | "low";
  relevance_reason?: string;
  research_facets?: ResearchFacet[];
}

export interface ResearchFacet {
  facet: string;
  label: string;
  score: number;
  confidence: "high" | "medium" | "low";
  matched_terms: string[];
  evidence_sources: string[];
}

export interface FacetDistributionItem {
  facet: string;
  label: string;
  paper_count: number;
  ratio: number;
  top_papers?: { paper_id: string; title: string }[];
}

export interface YearCount { year: number; count: number; }
export interface TopicEvolutionPhase {
  phase: "early" | "middle" | "recent";
  label: string;
  year_range: [number, number];
  paper_count: number;
  keywords: string[];
  representative_papers: TopicPaper[];
  papers?: TopicPaper[];
  summary?: string;
  evidence_coverage?: {
    papers_with_evidence: number;
    total_papers: number;
  };
}

export interface RelatedTopicRef {
  cluster_id: string;
  name: string;
  type?: string;
  paper_count?: number;
  similarity: number;
  shared_keywords?: string[];
  reason?: string;
}

export interface TopicRelationship {
  source_topic_id: string;
  target_topic_id: string;
  similarity: number;
  reason?: string;
  shared_keywords?: string[];
  source?: string;
  target?: string;
  weight?: number;
  strength?: number;
  shared_tags?: string[];
}

export interface ResearchMapResponse {
  mature_topics: ResearchMapTopic[];
  growing_topics: ResearchMapTopic[];
  gap_topics: ResearchMapTopic[];
  topic_relationships: TopicRelationship[];
  cluster_stats: ResearchMapTopic[];
  clusters: ResearchMapTopic[];
  network_stats: { total_nodes: number; total_edges: number };
}

export interface RelatedPapersResponse {
  paper_id: string;
  related: RelatedPaper[];
  source: "vector" | "keyword" | "empty";
  count: number;
  reason?: string | null;
}

export interface CitationNetworkResponse {
  nodes: NetworkNode[];
  edges: NetworkLink[];
}

export interface SimilarityNetworkResponse {
  nodes: NetworkNode[];
  links: NetworkLink[];
  edges: NetworkLink[];
  stats: { node_count: number; link_count: number; avg_score?: number };
}

export interface ConceptNetworkResponse {
  nodes: NetworkNode[];
  edges: NetworkLink[];
}

export interface ClusterGraphResponse {
  clusters: { id: string; name: string; size: number }[];
}

export interface ClustersResponse {
  clusters: { id: string; name: string; summary: string; paper_count: number }[];
}

export interface ClusterContext {
  cluster_id: string;
  papers: PaperItem[];
  summary: string;
}

// ── Evidence types ──

export interface EvidenceMethod { name?: string; purpose?: string; evidence_type?: string; quote?: string; confidence?: string; }
export interface EvidenceKeyResult { result?: string; measured_variable?: string; direction?: string; condition?: string; quote?: string; confidence?: string; }
export interface EvidenceCoreFinding { finding?: string; quote?: string; confidence?: string; }
export interface EvidenceDiscussionPoint { point?: string; type?: string; quote?: string; confidence?: string; }
export interface EvidenceLimitation { limitation?: string; quote?: string; confidence?: string; }
export interface EvidenceOpenQuestion { question?: string; quote?: string; confidence?: string; }
export interface ResultDiscussionLink { result_index?: number; discussion_index?: number; link_type?: string; basis?: string; confidence?: string; }

export interface PaperEvidence {
  paper_id?: string; status?: string; extraction_mode?: string;
  methods?: EvidenceMethod[]; key_results?: EvidenceKeyResult[];
  core_findings?: EvidenceCoreFinding[]; discussion_points?: EvidenceDiscussionPoint[];
  limitations?: EvidenceLimitation[]; open_questions?: EvidenceOpenQuestion[];
  result_discussion_links?: ResultDiscussionLink[];
  coverage?: Record<string, boolean>; fallback_used?: boolean;
}

export interface EvidenceChunkItem {
  chunk_id?: string; paper_id: string; chunk_type: string; text: string;
  source_section?: string; quote?: string; confidence?: string;
  title?: string; year?: number | null; journal?: string | null; score?: number;
}

export type EvidenceChunkType =
  | "all" | "key_result" | "core_finding" | "discussion_point"
  | "method" | "limitation" | "open_question" | "claim"
  | "figure" | "table";

export interface EvidenceQueryRequest {
  query: string;
  limit?: number;
  chunk_type?: EvidenceChunkType;
}

export interface EvidenceSearchResult {
  chunk_id?: string;
  paper_id: string;
  title?: string;
  year?: number | null;
  journal?: string | null;
  chunk_type: string;
  text: string;
  quote?: string;
  source_section?: string;
  confidence?: string;
  score?: number;
}

/* ── /hotspots ── */

export interface TrendingTopic {
  id: string; name: string; facet: string; facet_label: string;
  paper_count: number; recent_paper_count: number; recent_ratio: number;
  year_range: number[]; latest_year: number; growth_score: number;
  trend_label: "hot" | "active" | "stable" | "dormant";
  evidence_coverage: { structured: number; total: number; ratio: number };
  top_keywords: string[]; representative_papers: any[];
}

export interface HotPaper {
  paper_id: string; title: string; year: number | null; journal: string;
  topic_name: string; score: number; reason: string;
  evidence_counts: { key_results: number; core_findings: number; methods: number; discussion_points: number };
}

export interface EmergingFacet {
  facet: string; label: string; paper_count: number; recent_paper_count: number;
  recent_ratio: number; subtopic_count: number; trend_label: string;
  evidence_coverage_ratio: number; top_subtopics: string[];
}

/* ── /research-gaps ── */

export interface ResearchGap {
  id: string; title: string; gap_type: string; description: string;
  facet?: string; facet_label?: string; subtopic?: string;
  paper_count?: number; ratio?: number; evidence_coverage?: number;
  method_count?: number;
  confidence: number; impact: number; feasibility: number;
  suggested_action: string;
}

export interface ResearchGapsResponse {
  status: string; source: string; paper_count: number; gap_count: number;
  gaps: ResearchGap[];
  message?: string;
}

/* ── /knowledge-network ── */

export interface KnowledgeNode { id: string; type: string; label: string; group: string; size: number; metadata?: Record<string, unknown>; }
export interface KnowledgeEdge { id: string; source: string; target: string; type: string; weight: number; metadata?: Record<string, unknown>; }
/* ── /report ── */

export interface ReportSection { id: string; title: string; summary: string; items: any[]; }
export interface ReportResponse {
  status: string; source: string; generated_at: string; paper_count: number;
  report_title: string; executive_summary: string[]; coverage_summary: any;
  research_map_summary: any; hotspots_summary: any; research_gaps_summary: any;
  knowledge_network_summary: any; evidence_summary: any;
  recommended_actions: string[]; sections: ReportSection[];
  message?: string;
}

export interface HotspotsResponse {
  status: string; source: string; paper_count: number; generated_at: string;
  trending_topics: TrendingTopic[]; hot_papers: HotPaper[];
  emerging_facets: EmergingFacet[]; method_shifts: any[];
  evidence_signals: { chunk_type_distribution: Record<string, number> };
  insights: string[];
  message?: string;
}

export interface EvidenceQueryResponse {
  results: EvidenceSearchResult[];
  source: string;
}

export interface EvidenceChunksResponse { paper_id?: string; chunks: EvidenceChunkItem[]; chunk_count: number; }

/** Human-readable chunk type labels */
export const CHUNK_TYPE_LABELS: Record<string, string> = {
  all: "All",
  key_result: "Key result",
  core_finding: "Core finding",
  discussion_point: "Discussion",
  method: "Method",
  limitation: "Limitation",
  open_question: "Open question",
  claim: "Claim",
};

export const CHUNK_TYPE_COLORS: Record<string, string> = {
  key_result: "bg-emerald-50 text-emerald-600 border-emerald-200",
  core_finding: "bg-blue-50 text-blue-600 border-blue-200",
  discussion_point: "bg-purple-50 text-purple-600 border-purple-200",
  method: "bg-amber-50 text-amber-600 border-amber-200",
  limitation: "bg-red-50 text-red-600 border-red-200",
  open_question: "bg-cyan-50 text-cyan-600 border-cyan-200",
  claim: "bg-slate-100 text-slate-500 border-slate-200",
};

/* ── Hybrid Parse Report ── */

export interface ParserAvailabilityStatus {
  grobid_available: boolean;
  opendataloader_available: boolean;
  marker_available: boolean;
  pymupdf_available: boolean;
  hybrid_parser_enabled: boolean;
  error?: string;
}

export interface ParserOutputItem {
  parser_name: string;
  status: "success" | "skipped" | "failed" | "fallback";
  output_type: string;
  output_paths: string[];
  quality_score: number;
  warnings: string[];
  errors: string[];
  created_at: string;
}

export interface ParseQualityReportData {
  metadata_score: number;
  markdown_score: number;
  layout_score: number;
  reference_score: number;
  figure_score: number;
  table_score: number;
  overall_score: number;
  problems: string[];
  recommendations: string[];
}

export interface ParseReportResponse {
  paper_id: string;
  status: "hybrid_parsed" | "legacy_only";
  message?: string;
  manifest?: Record<string, unknown>;
  quality_report?: ParseQualityReportData | null;
  parser_used?: {
    metadata_source: string;
    markdown_source: string;
    layout_source: string;
    figures_source: string;
    tables_source: string;
    references_source: string;
  };
  output_paths?: {
    final_markdown_path: string;
    manifest_path: string;
  };
  warnings?: string[];
  errors?: string[];
  legacy_files?: string[];
  hint?: string;
}

export interface RelatedPaper {
  paper_id: string;
  title: string;
  authors?: string[];
  year?: number | null;
  journal?: string | null;
  doi?: string | null;
  similarity?: number;
  reason?: string;
  summary?: string | null;
  evidence?: Record<string, unknown> | null;
  topic_relevance?: number;
  relevance_label?: string;
  relevance_reason?: string;
}

export interface SimilarityNode {
  id: string;
  label: string;
  group?: string;
}

export interface SimilarityLink {
  source: string;
  target: string;
  score: number;
}

/* ── Legacy compat (used by existing components, not yet refactored) ── */

export interface ParsedCitationAnchor {
  id?: string;
  source_id?: string;
  source_section?: string | null;
  page?: string | null;
  paragraph?: number | null;
  text_preview?: string;
}

export interface KnowledgeCluster {
  id: string;
  name: string;
  summary: string;
  paper_count: number;
  key_findings: string[];
  representative_papers: string[];
  top_toxins?: string[];
  top_mechanisms?: string[];
  top_methods?: string[];
  top_hosts?: string[];
  node_count?: number;
  cluster_id?: string;
  central_papers?: { paper_id: string; title?: string }[];
}

export type ResearchTopic = ResearchMapTopic;

export interface TagEvidence {
  tag: string;
  papers: number;
  evidence: string;
  category?: string;
  confidence?: string;
  score?: number;
  matched_terms?: string[];
  source?: string[];
  reason?: string;
}

// Extend PaperMetadata for components that access extra fields
export interface PaperMetadataExtended extends PaperMetadata {
  abstract?: string;
  metadata?: Record<string, unknown>;
}

// Extend QueryResultItem for components that access extra fields
export interface QueryResultItemExtended extends QueryResultItem {
  record_id?: string;
  citation_anchor?: string;
  source_section?: string;
  level?: string;
  text_preview?: string;
  score?: number;
}

// Extend PaperTags for components that access extra fields
export interface PaperTagsExtended extends PaperTags {
  assigned_tags?: string[];
  candidate_tags?: string[];
}

// Extend NetworkNode/NetworkLink for graph components
export interface NetworkNodeExtended extends NetworkNode {
  x?: number;
  y?: number;
  title?: string;
  metadata?: Record<string, unknown>;
}

export interface NetworkLinkExtended extends NetworkLink {
  type?: string;
  weight?: number;
  label?: string;
}

/* ── Phase 0.9: Agent Chat Types ── */

export interface AgentCitation {
  ref_id: string;
  chunk_id: string;
  paper_id: string;
  paper_title: string;
  paper_year: number | null;
  text_snippet: string;
  linked_evidence_id: string;
  source: string;
  confidence: string;
}

export interface AgentContextItem {
  chunk_id: string;
  paper_id: string;
  chunk_type: string;
  text: string;
  source: string;
  score: number;
}

export interface AgentContextPack {
  chunks: AgentContextItem[];
  papers: Record<string, unknown>;
}

export interface TokenUsage {
  provider: string;
  model: string;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  estimated_input_cost_usd: number | null;
  estimated_output_cost_usd: number | null;
  estimated_total_cost_usd: number | null;
  currency: string;
  source: string;
  note?: string | null;
}

export interface AgentAskResponse {
  question: string;
  answer: string;
  citations: AgentCitation[];
  context_used: number;
  papers_cited: number;
  model: string;
  elapsed_ms: number;
  intent: string;
  context: AgentContextPack | null;
  token_usage?: TokenUsage | null;
}

export type AgentAnswerMode = "auto" | "llm" | "evidence_only";

export interface AgentAskRequest {
  question: string;
  top_k?: number;
  chunk_types?: string[];
  include_assets?: boolean;
  include_evidence?: boolean;
  paper_id?: string | null;
  use_llm?: boolean;
  return_context?: boolean;
}

export interface QueryAssetResult {
  chunk_id: string;
  paper_id: string;
  chunk_type: string;
  text: string;
  score: number;
  linked_evidence_id: string;
  linked_evidence_ids: string[];
  source_asset_ids: string[];
  entities: string[];
  linked_claims: string[];
  linked_methods: string[];
  confidence: string;
  quality_score: number;
  citation_key: string;
  metadata: Record<string, unknown>;
}

export interface QueryAssetsResponse {
  query: string;
  results: QueryAssetResult[];
  count: number;
  unique_papers: number;
  warnings: string[];
  elapsed_ms: number;
}

export interface QueryAssetsRequest {
  query: string;
  top_k?: number;
  chunk_types?: string[];
  paper_id?: string | null;
  min_quality_score?: number;
  include_metadata?: boolean;
}

/* ── Helpers ── */

/** Strip source_path and any server-internal fields from a query result. */
export function sanitizeResult(
  raw: Record<string, unknown>,
): Record<string, unknown> {
  const safe = { ...raw };
  delete safe["source_path"];
  delete safe["_internal"];
  return safe;
}

/* ── Phase 2.1: AI Settings ── */

export interface AISettingsResponse {
  enabled: boolean;
  provider: string;
  model: string;
  base_url: string;
  temperature: number;
  max_tokens: number;
  enabled_tasks: Record<string, boolean>;
  api_key_configured: boolean;
  api_key_preview: string;
}

export interface AISettingsUpdate {
  enabled?: boolean;
  provider?: string;
  model?: string;
  api_key?: string;
  base_url?: string;
  temperature?: number;
  max_tokens?: number;
  enabled_tasks?: Record<string, boolean>;
}

export interface AITestResponse {
  status: "ok" | "failed";
  provider: string;
  model: string;
  error?: string;
  latency_note?: string;
  usage?: {
    input_tokens: number;
    output_tokens: number;
  };
}

/* ── Phase 2.2: AI Enrichment ── */

export interface AISummaryV2Response {
  paper_id: string;
  available: boolean;
  message?: string;
  status?: string;
  title?: string;
  research_question?: string;
  core_finding?: string;
  method_summary?: string[];
  key_evidence?: {
    claim: string;
    evidence: string;
    evidence_type: string;
    source_hint?: string;
  }[];
  main_claims?: string[];
  limitations?: string[];
  future_directions?: string[];
  important_entities?: {
    name: string;
    type: string;
    role: string;
  }[];
  confidence?: number;
  warnings?: string[];
  model?: string;
  provider?: string;
  usage?: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost_estimate: number;
  };
  generated_at?: string;
}

export interface EvidenceEnrichmentResponse {
  paper_id: string;
  available: boolean;
  message?: string;
  status?: string;
  total_chunks?: number;
  eligible_chunks?: number;
  enriched_chunks?: number;
  batch_count?: number;
  failed_batches?: number;
  chunks?: EnrichedChunk[];
  usage?: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost_estimate: number;
  };
  generated_at?: string;
}

export interface EnrichedChunk {
  chunk_id: string;
  original_text: string;
  section: string;
  evidence_type: string;
  ai_claim: string;
  ai_finding: string;
  method_mentioned: string[];
  entity_mentioned: string[];
  supports_claim: boolean | null;
  evidence_strength: string;
  limitations: string[];
  confidence: number;
  warnings: string[];
}

/* ── Phase 2.3: Research Gaps & Hypotheses ── */

export interface AIGapsResponse {
  paper_id: string;
  available: boolean;
  message?: string;
  status?: string;
  gaps?: ResearchGap[];
  warnings?: string[];
  usage?: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost_estimate: number;
  };
  generated_at?: string;
}

export interface ResearchGap {
  gap_id: string;
  gap_statement: string;
  gap_type: string;
  based_on_evidence: string[];
  missing_information: string;
  why_it_matters: string;
  confidence: number;
  warnings: string[];
}

export interface AIHypothesesResponse {
  paper_id: string;
  available: boolean;
  message?: string;
  status?: string;
  hypotheses?: Hypothesis[];
  warnings?: string[];
  usage?: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost_estimate: number;
  };
  generated_at?: string;
}

export interface Hypothesis {
  hypothesis_id: string;
  hypothesis_statement: string;
  rationale: string;
  linked_gap_id: string;
  supporting_evidence: string[];
  testable_prediction: string;
  suggested_experiment: string;
  risk_level: string;
  confidence: number;
  warnings: string[];
}

/* ── Phase 2.3.1: Gap-Hypothesis Quality ── */

export interface GapHypothesisQualityResponse {
  paper_id: string;
  available: boolean;
  message?: string;
  status?: string;
  gap_count?: number;
  hypothesis_count?: number;
  gap_scores?: GapScore[];
  hypothesis_scores?: HypothesisScore[];
  overall_quality_score?: number;
  recommendation?: "accept" | "manual_review" | "reject" | "insufficient_data";
  metrics?: {
    invalid_linked_gap_count: number;
    high_overclaim_risk_count: number;
    safety_ethics_warnings: number;
  };
  top_warnings?: string[];
  generated_at?: string;
}

export interface GapScore {
  gap_id: string;
  evidence_grounding_score: number;
  specificity_score: number;
  novelty_score: number;
  overclaim_risk: "low" | "medium" | "high";
  weighted_score: number;
  warnings: string[];
}

export interface HypothesisScore {
  hypothesis_id: string;
  linked_gap_valid: boolean;
  testability_score: number;
  rationale_grounding_score: number;
  experiment_feasibility_score: number;
  over_specificity_risk: "low" | "medium" | "high";
  safety_or_ethics_warning: string[];
  weighted_score: number;
  warnings: string[];
}
