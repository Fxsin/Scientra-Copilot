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

/* ── POST /query ── */

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

/** A single result item from the query API. source_path is stripped. */
export interface QueryResultItem {
  paper_id: string;
  title: string | null;
  year: number | null;
  doi: string | null;
  level: string;
  record_id: string;
  chunk_id: string | null;
  score: number;
  matched_tags: string[];
  assigned_tags: Record<string, string[]>;
  candidate_tags: Record<string, string[]>;
  text_preview: string;
  citation_anchor: string | null;
  source_section: string | null;
}

export interface QueryResponse {
  query: string;
  mode: QueryMode;
  top_k: number;
  level: QueryLevel;
  total: number;
  results: QueryResultItem[];
  include_candidate_tags: boolean;
  policy: Record<string, string>;
}

/* ── GET /paper/{paper_id}/metadata ── */

export interface PaperMetadata {
  paper_id: string;
  metadata: Record<string, unknown>;
}

/* ── GET /paper/{paper_id}/tags ── */

export interface TagEvidence {
  category?: string;
  matched_terms?: string[];
  source?: string[];
  source_section?: string[];
  score?: number;
  assignable_score?: number;
  confidence?: string;
  reason?: string;
}

export interface PaperTags {
  paper_id: string;
  assigned_tags: Record<string, string[]>;
  candidate_tags: Record<string, string[]>;
  evidence: Record<string, TagEvidence>;
}

/* ── GET /paper/{paper_id}/summary ── */

export interface PaperSummary {
  paper_id: string;
  title: string | null;
  summary: string;
  citation_anchors: string[];
}

/* ── Parsed citation anchor from summary text ── */

export interface ParsedCitationAnchor {
  id: string;
  source_section: string | null;
  page: string | null;
  paragraph: number | null;
}

/* ── Sensitive field blocklist ── */

export const SENSITIVE_FIELDS = [
  "source_path",
  "pdf_path",
  "raw_text_path",
  "tei_xml_path",
  "tei_path",
  "lancedb_path",
  "sqlite_path",
  "api_key",
  "secret",
  "token",
  "bearer_token",
  "source_pdf",
] as const;

/** Regex patterns for sensitive values that should never be rendered. */
const SENSITIVE_PATTERNS = [
  /^sk-/i,                           // OpenAI / Anthropic API keys
  /^Bearer\s/i,                      // Bearer tokens
  /^[A-Z]:\\/i,                      // Windows local paths (G:\, C:\, etc.)
  /^\/home\//i,                      // Linux home paths
  /^\/Users\//i,                     // macOS home paths
];

/** Check if a string value looks like a sensitive path or token. */
function isSensitiveValue(value: string): boolean {
  return SENSITIVE_PATTERNS.some((p) => p.test(value));
}

/** Strip sensitive fields and values from a raw API object. */
export function sanitizeResult(
  raw: Record<string, unknown>,
): Record<string, unknown> {
  const safe: Record<string, unknown> = {};
  for (const key of Object.keys(raw)) {
    const keyLower = key.toLowerCase();
    // Block sensitive field names
    if (
      (SENSITIVE_FIELDS as readonly string[]).some(
        (f) => keyLower === f || keyLower.endsWith("_" + f),
      )
    )
      continue;
    const val = raw[key];
    // Block sensitive values
    if (typeof val === "string" && isSensitiveValue(val)) continue;
    // Recursively sanitize nested objects
    if (val && typeof val === "object" && !Array.isArray(val)) {
      safe[key] = sanitizeResult(val as Record<string, unknown>);
    } else {
      safe[key] = val;
    }
  }
  return safe;
}

/* ── GET /paper/{paper_id}/related ── */

export interface RelatedPaper {
  paper_id: string;
  title: string | null;
  year: number | null;
  doi: string | null;
  journal: string | null;
  similarity_score: number;
  shared_tags: string[];
  shared_mechanisms: string[];
  shared_methods: string[];
  shared_toxins: string[];
  reason: string;
  text_preview: string;
}

export interface RelatedPapersResponse {
  paper_id: string;
  related_papers: RelatedPaper[];
}

/* ── GET /network/knowledge ── */

export type NetworkNodeType = "paper" | "toxin" | "host" | "mechanism" | "method";

export interface NetworkNode {
  id: string;
  label: string;
  type: NetworkNodeType;
  paper_id?: string;
  title?: string | null;
  year?: number | null;
  journal?: string | null;
  count?: number;
  tags?: string[];
  color: string;
  // Force Graph 2D runtime properties
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number;
  fy?: number;
}

export interface NetworkLink {
  source: string | NetworkNode;
  target: string | NetworkNode;
  type: string;
  weight: number;
  label: string;
}

export interface NetworkStats {
  node_count: number;
  link_count: number;
  paper_count: number;
  toxin_count: number;
  host_count: number;
  mechanism_count: number;
  method_count: number;
}

export interface KnowledgeNetworkResponse {
  nodes: NetworkNode[];
  links: NetworkLink[];
  stats: NetworkStats;
}

/* ── GET /network/clusters ── */

export interface ClusterPaper {
  paper_id: string;
  title: string | null;
  year: number | null;
  centrality_score: number;
}

export interface KnowledgeCluster {
  cluster_id: string;
  name: string;
  node_count: number;
  paper_count: number;
  central_papers: ClusterPaper[];
  top_toxins: string[];
  top_mechanisms: string[];
  top_methods: string[];
  top_hosts: string[];
  keywords: string[];
  summary: string;
}

export interface ClustersResponse {
  clusters: KnowledgeCluster[];
  total: number;
}

export interface ClusterContext {
  cluster_id: string;
  name: string;
  summary: string;
  paper_count: number;
  top_papers: {
    paper_id: string;
    title: string | null;
    year: number | null;
    tags: string[];
  }[];
  top_tags: string[];
  top_toxins: string[];
  top_mechanisms: string[];
  top_methods: string[];
  top_hosts: string[];
}

/* ── GET /network/similarity ── */

export interface SimilarityNode {
  id: string;
  type: "paper";
  paper_id: string;
  title: string | null;
  year: number | null;
  journal: string | null;
  tags: string[];
  // ForceGraph2D runtime props
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number;
  fy?: number;
}

export interface SimilarityLink {
  source: string;
  target: string;
  type: "similarity";
  score: number;
  shared_tags: string[];
  reason: string;
}

export interface SimilarityStats {
  node_count: number;
  link_count: number;
  min_score: number;
  max_score: number;
  avg_score: number;
}

export interface SimilarityNetworkResponse {
  nodes: SimilarityNode[];
  links: SimilarityLink[];
  stats: SimilarityStats;
}

export interface CitationNetworkResponse {
  enabled: boolean;
  reason: string;
  nodes: never[];
  links: never[];
}

/* ── GET /network/concept ── */

export interface ConceptNode {
  id: string;
  label: string;
  type: string;
  color: string;
  paper_count: number;
  x?: number;
  y?: number;
}
export interface ConceptLink {
  source: string;
  target: string;
  type: string;
  weight: number;
  label: string;
}
export interface ConceptNetworkResponse {
  nodes: ConceptNode[];
  links: ConceptLink[];
  stats: { node_count: number; link_count: number };
}

/* ── GET /network/cluster-graph ── */

export interface ClusterGraphNode {
  id: string;
  label: string;
  type: string;
  color: string;
  paper_count: number;
  central_papers: { paper_id: string; title: string | null; year: number | null; centrality_score: number }[];
  summary: string;
  x?: number;
  y?: number;
}
export interface ClusterGraphResponse {
  nodes: ClusterGraphNode[];
  links: ConceptLink[];
  stats: { node_count: number; link_count: number };
}

/* ── GET /research-map ── */

export interface ResearchTopic {
  cluster_id: string;
  name: string;
  paper_count: number;
  year_span?: number;
  year_range: string;
  method_diversity?: number;
  key_methods?: string[];
  top_tags?: string[];
  confidence?: string;
  summary: string;
  recent_count?: number;
  growth_rate?: string;
  gap_tags?: string[];
  connected_to?: string[];
  opportunity?: string;
}

export interface TopicRelationship {
  source: string;
  target: string;
  shared_tags: string[];
  strength: number;
}

export interface ResearchMapResponse {
  mature_topics: ResearchTopic[];
  growing_topics: ResearchTopic[];
  gap_topics: ResearchTopic[];
  cluster_stats: ResearchTopic[];
  topic_relationships: TopicRelationship[];
}
