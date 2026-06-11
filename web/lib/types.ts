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
  nodes: NetworkNode[];
  links: NetworkLink[];
  stats: {
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
  cluster_id: string;
  name: string;
  paper_count: number;
  year_range: string;
  method_diversity: number;
  key_methods: string[];
  top_tags: string[];
  confidence: string;
  summary: string;
  recent_count: number;
  growth_rate: string;
  gap_tags: string[];
  connected_to: string[];
  opportunity: string;
  year_span?: string;
}

export interface ResearchMapResponse {
  mature_topics: ResearchMapTopic[];
  growing_topics: ResearchMapTopic[];
  gap_topics: ResearchMapTopic[];
  topic_relationships: { source: string; target: string; weight?: number; strength?: number; shared_tags?: string[] }[];
  cluster_stats: ResearchMapTopic[];
  clusters: { id: string; name: string; size: number }[];
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

export interface RelatedPaper {
  paper_id: string;
  title: string;
  authors?: string[];
  year?: number | null;
  journal?: string | null;
  doi?: string | null;
  similarity?: number;
  reason?: string;
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
