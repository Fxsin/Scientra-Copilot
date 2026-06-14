import type {
  HealthResponse,
  PaperEvidence, EvidenceChunksResponse, EvidenceQueryResponse,
  PaperMetadata, PaperSummary, PaperTags, PapersResponse,
  QueryRequest, QueryResponse, QueryResultItem,
  ResearchMapTopic, StatsResponse,
  AgentAskRequest, AgentAskResponse,
  QueryAssetsRequest, QueryAssetsResponse,
} from "./types";
import { sanitizeResult } from "./types";

/* ── API base URL ── */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_SCIENTRA_API_URL?.replace(/\/$/, "") ||
  `http://127.0.0.1:${process.env.NEXT_PUBLIC_SCIENTRA_API_PORT || "8710"}` ||
  "http://127.0.0.1:8710";

// Log API base URL once in development for troubleshooting
if (typeof window !== "undefined" && process.env.NODE_ENV === "development") {
  console.log(
    `%c[Scientra API] %c${API_BASE_URL}`,
    "color: #0891b2; font-weight: bold;",
    "color: #64748b;",
  );
}

/* ── Schema guard: detect old API ── */

export type SchemaStatus = "ok" | "outdated" | "empty" | "error";

export interface SchemaCheckResult {
  status: SchemaStatus;
  message: string;
  apiBaseUrl: string;
}

/**
 * Check if a /research-map response matches the expected v2 schema.
 * Old schema: {topics: [], papers: []}
 * New schema: {clusters, mature_topics, growing_topics, gap_topics, topic_relationships}
 */
export function checkResearchMapSchema(data: unknown): SchemaCheckResult {
  if (!data || typeof data !== "object") {
    return {
      status: "error",
      message: "Research Map API returned invalid data.",
      apiBaseUrl: API_BASE_URL,
    };
  }

  const d = data as Record<string, unknown>;
  const keys = Object.keys(d);

  // Detect old schema: {topics: [], papers: []}
  if (
    keys.length === 2 &&
    keys.includes("topics") &&
    keys.includes("papers") &&
    Array.isArray(d.topics) &&
    d.topics.length === 0
  ) {
    return {
      status: "outdated",
      message:
        "Research Map API returned an outdated or empty schema. " +
        "Please restart the API server with the latest code. " +
        `Current API: ${API_BASE_URL}`,
      apiBaseUrl: API_BASE_URL,
    };
  }

  // Check for new schema markers
  const hasClusters = "clusters" in d;
  const hasTopics = "mature_topics" in d || "growing_topics" in d;
  const hasRelationships = "topic_relationships" in d;

  if (hasClusters || hasTopics || hasRelationships) {
    const totalTopics =
      (Array.isArray(d.clusters) ? d.clusters.length : 0) +
      (Array.isArray(d.mature_topics) ? (d.mature_topics as unknown[]).length : 0) +
      (Array.isArray(d.growing_topics) ? (d.growing_topics as unknown[]).length : 0) +
      (Array.isArray(d.gap_topics) ? (d.gap_topics as unknown[]).length : 0);

    if (totalTopics === 0) {
      return {
        status: "empty",
        message: "Research Map loaded but no topics were generated yet. Import more papers.",
        apiBaseUrl: API_BASE_URL,
      };
    }

    return {
      status: "ok",
      message: `Research Map schema OK (${totalTopics} topics).`,
      apiBaseUrl: API_BASE_URL,
    };
  }

  return {
    status: "outdated",
    message:
      "Research Map API returned an unrecognized schema. " +
      "The API server may need to be restarted. " +
      `Current API: ${API_BASE_URL}`,
    apiBaseUrl: API_BASE_URL,
  };
}

/* ── Error taxonomy ── */

export type ApiErrorKind =
  | "network_error"   // ECONNREFUSED, DNS failure, CORS block — server not running
  | "http_error"      // 4xx / 5xx from server
  | "parse_error"     // response is not valid JSON
  | "schema_error";   // JSON is valid but fields don't match expected types

export class ApiError extends Error {
  kind: ApiErrorKind;
  status: number;
  url: string;
  responseText: string | null;

  constructor(opts: {
    kind: ApiErrorKind;
    message: string;
    status?: number;
    url?: string;
    responseText?: string | null;
  }) {
    super(opts.message);
    this.name = "ApiError";
    this.kind = opts.kind;
    this.status = opts.status ?? 0;
    this.url = opts.url ?? "";
    this.responseText = opts.responseText ?? null;
  }
}

/* ── Low-level fetch ── */

interface FetchMeta {
  url: string;
  status: number;
  responseText: string | null;
}

async function fetchJson<T>(
  path: string,
  init?: RequestInit,
): Promise<{ data: T; meta: FetchMeta }> {
  const url = `${API_BASE_URL}${path}`;
  let res: Response;

  // 1. Network attempt
  try {
    res = await fetch(url, {
      headers: { Accept: "application/json" },
      ...init,
    });
  } catch (err: unknown) {
    const msg = err instanceof TypeError ? err.message : String(err);
    console.error(`[api] NETWORK ERROR — ${url} — ${msg}`);
    throw new ApiError({
      kind: "network_error",
      message: `Cannot reach Scientra Copilot API at ${API_BASE_URL}.\nIs the server running? Run: python Scripts/run_api_server.py\n\nFrontend API Base URL: ${API_BASE_URL}`,
      status: 0,
      url,
    });
  }

  // 2. HTTP error
  if (!res.ok) {
    let body: string | null = null;
    try {
      body = await res.text();
    } catch {
      // ignore
    }
    // Always include status and url as separate args so they display even if object is empty
    console.error(
      `[api] HTTP ${res.status} ${res.statusText} — ${url}`,
      body?.slice(0, 300) || "(empty body)",
    );
    throw new ApiError({
      kind: "http_error",
      message: `API returned ${res.status} ${res.statusText}\nURL: ${url}\nFrontend API Base URL: ${API_BASE_URL}`,
      status: res.status,
      url,
      responseText: body,
    });
  }

  // 3. JSON parse
  let json: unknown;
  try {
    json = await res.json();
  } catch (err: unknown) {
    console.error("[api] parse_error", { url, error: String(err) });
    throw new ApiError({
      kind: "parse_error",
      message: `Response from ${url} is not valid JSON.\nFrontend API Base URL: ${API_BASE_URL}`,
      status: res.status,
      url,
    });
  }

  return {
    data: json as T,
    meta: { url, status: res.status, responseText: null },
  };
}

/* ── GET endpoints ── */

export function getHealth(): Promise<HealthResponse> {
  return fetchJson<HealthResponse>("/health").then((r) => r.data);
}

export function getStats(): Promise<StatsResponse> {
  return fetchJson<StatsResponse>("/stats").then((r) => r.data);
}

export function getPapers(params?: {
  page?: number;
  page_size?: number;
  q?: string;
  year?: number;
  toxin?: string;
  species?: string;
  method?: string;
  tag?: string;
  sort?: string;
}): Promise<PapersResponse> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.page_size) sp.set("page_size", String(params.page_size));
  if (params?.q) sp.set("q", params.q);
  if (params?.year) sp.set("year", String(params.year));
  if (params?.toxin) sp.set("toxin", params.toxin);
  if (params?.species) sp.set("species", params.species);
  if (params?.method) sp.set("method", params.method);
  if (params?.tag) sp.set("tag", params.tag);
  if (params?.sort) sp.set("sort", params.sort);
  const qs = sp.toString();
  return fetchJson<PapersResponse>(`/papers${qs ? "?" + qs : ""}`).then((r) => r.data);
}

/* ── POST /query ── */

interface RawQueryResult {
  source_path?: string;
  [key: string]: unknown;
}

interface RawQueryResponse {
  query: string;
  mode: string;
  top_k: number;
  level: string;
  total: number;
  results: RawQueryResult[];
  include_candidate_tags: boolean;
  policy: Record<string, string>;
}

export async function queryLiterature(
  request: QueryRequest,
): Promise<QueryResponse> {
  const { data: raw } = await fetchJson<RawQueryResponse>("/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  return {
    query: raw.query,
    mode: raw.mode as QueryResponse["mode"],
    top_k: raw.top_k,
    level: raw.level as QueryResponse["level"],
    total: raw.total,
    results: raw.results.map(
      (r) =>
        sanitizeResult(r as unknown as Record<string, unknown>) as unknown as QueryResultItem,
    ),
    include_candidate_tags: raw.include_candidate_tags,
    policy: raw.policy,
  };
}

/* ── GET /paper/{paper_id}/* ── */

interface RawPaperEnvelope {
  paper_id: string;
  source_path?: string;
  [key: string]: unknown;
}

function sanitizeEnvelope<T>(raw: RawPaperEnvelope): T {
  const safe = sanitizeResult(raw as unknown as Record<string, unknown>);
  return safe as unknown as T;
}

export async function getPaperMetadata(
  paperId: string,
): Promise<PaperMetadata> {
  const { data: raw } = await fetchJson<RawPaperEnvelope>(
    `/paper/${encodeURIComponent(paperId)}/metadata`,
  );
  return sanitizeEnvelope<PaperMetadata>(raw);
}

export async function getPaperTags(paperId: string): Promise<PaperTags> {
  const { data: raw } = await fetchJson<RawPaperEnvelope>(
    `/paper/${encodeURIComponent(paperId)}/tags`,
  );
  return sanitizeEnvelope<PaperTags>(raw);
}

export async function getPaperSummary(
  paperId: string,
): Promise<PaperSummary> {
  const { data: raw } = await fetchJson<RawPaperEnvelope>(
    `/paper/${encodeURIComponent(paperId)}/summary`,
  );
  return sanitizeEnvelope<PaperSummary>(raw);
}

/* ── GET /paper/{paper_id}/related ── */

import type {
  CitationNetworkResponse,
  ClustersResponse,
  ClusterContext,
  ClusterGraphResponse,
  ConceptNetworkResponse,
  KnowledgeNetworkResponse,
  RelatedPapersResponse,
  ResearchMapResponse,
  SimilarityNetworkResponse,
} from "./types";

export async function getRelatedPapers(
  paperId: string,
  limit = 5,
): Promise<RelatedPapersResponse> {
  return fetchJson<RelatedPapersResponse>(
    `/paper/${encodeURIComponent(paperId)}/related?limit=${Math.min(limit, 20)}`,
  ).then((r) => r.data);
}

export async function getKnowledgeNetworkLegacy(
  limit = 500,
): Promise<KnowledgeNetworkResponse> {
  return fetchJson<KnowledgeNetworkResponse>(
    `/network/knowledge?limit=${limit}`,
  ).then((r) => r.data);
}

export async function getSimilarityNetwork(
  minScore = 0.65,
): Promise<SimilarityNetworkResponse> {
  return fetchJson<SimilarityNetworkResponse>(
    `/network/similarity?min_score=${minScore}&limit=200`,
  ).then((r) => r.data);
}

export async function getCitationNetwork(): Promise<CitationNetworkResponse> {
  return fetchJson<CitationNetworkResponse>("/network/citations").then((r) => r.data);
}

export async function getConceptNetwork(
  minWeight = 2,
): Promise<ConceptNetworkResponse> {
  return fetchJson<ConceptNetworkResponse>(
    `/network/concept?min_weight=${minWeight}`,
  ).then((r) => r.data);
}

export async function getClusterGraph(): Promise<ClusterGraphResponse> {
  return fetchJson<ClusterGraphResponse>("/network/cluster-graph").then((r) => r.data);
}

export async function getClusters(): Promise<ClustersResponse> {
  return fetchJson<ClustersResponse>("/network/clusters").then((r) => r.data);
}

export async function getClusterContext(
  clusterId: string,
): Promise<ClusterContext> {
  return fetchJson<ClusterContext>(
    `/network/clusters/${encodeURIComponent(clusterId)}/context`,
  ).then((r) => r.data);
}

export async function getResearchMap(): Promise<ResearchMapResponse> {
  const { data } = await fetchJson<ResearchMapResponse>("/research-map");

  // Schema check in development
  if (typeof window !== "undefined" && process.env.NODE_ENV === "development") {
    const check = checkResearchMapSchema(data);
    if (check.status === "outdated" || check.status === "error") {
      console.warn(
        `%c[Scientra Schema] %c${check.message}`,
        "color: #d97706; font-weight: bold;",
        "color: #92400e;",
      );
    }
  }

  return data;
}

export async function getResearchMapTopic(topicId: string): Promise<{ topic: ResearchMapTopic }> {
  return fetchJson<{ topic: ResearchMapTopic }>(`/research-map/topic/${encodeURIComponent(topicId)}`).then((r) => r.data);
}

import type { HotspotsResponse } from "./types";

import type { ResearchGapsResponse } from "./types";

export async function getResearchGaps(): Promise<ResearchGapsResponse> {
  return fetchJson<ResearchGapsResponse>("/research-gaps").then((r) => r.data);
}

import type { ReportResponse } from "./types";

export async function getReport(): Promise<ReportResponse> {
  return fetchJson<ReportResponse>("/report").then((r) => r.data);
}

export async function getKnowledgeNetwork(): Promise<KnowledgeNetworkResponse> {
  return fetchJson<KnowledgeNetworkResponse>("/knowledge-network").then((r) => r.data);
}

export async function getHotspots(): Promise<HotspotsResponse> {
  return fetchJson<HotspotsResponse>("/hotspots").then((r) => r.data);
}

export function getPaperEvidence(paperId: string): Promise<PaperEvidence> {
  return fetchJson<PaperEvidence>(`/paper/${encodeURIComponent(paperId)}/evidence`).then((r) => r.data);
}

/* ── GET /paper/{paper_id}/parse-report ── */
import type { ParseReportResponse } from "./types";

export function getPaperParseReport(paperId: string): Promise<ParseReportResponse> {
  return fetchJson<ParseReportResponse>(
    `/paper/${encodeURIComponent(paperId)}/parse-report`,
  ).then((r) => r.data);
}

export function getPaperEvidenceChunks(paperId: string): Promise<EvidenceChunksResponse> {
  return fetchJson<EvidenceChunksResponse>(`/paper/${encodeURIComponent(paperId)}/evidence-chunks`).then((r) => r.data);
}

import type { EvidenceQueryRequest, EvidenceQueryResponse as EvidenceQueryResponseType } from "./types";

export async function queryEvidence(payload: EvidenceQueryRequest): Promise<EvidenceQueryResponseType> {
  // Normalize: don't send chunk_type if "all"
  const body: Record<string, unknown> = { query: payload.query, limit: payload.limit || 10 };
  if (payload.chunk_type && payload.chunk_type !== "all") {
    body.chunk_type = payload.chunk_type;
  }
  return fetchJson<EvidenceQueryResponseType>("/query/evidence", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => r.data);
}

/** Exposed via `export const` at the top of this file. */

/* ── POST /import/upload (multipart) ── */

import type { UploadResponse, ListJobsResponse } from "./import-types";

export async function uploadPdfs(files: File[]): Promise<UploadResponse> {
  const form = new FormData();
  for (const f of files) {
    form.append("files", f);
  }

  const url = `${API_BASE_URL}/import/upload`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      body: form,
    });
  } catch (err: unknown) {
    const msg = err instanceof TypeError ? err.message : String(err);
    console.error("[api] upload network_error", { url, error: msg });
    throw new ApiError({
      kind: "network_error",
      message: `Cannot reach API at ${API_BASE_URL}.\n${msg}`,
      status: 0,
      url,
    });
  }

  if (!res.ok) {
    const body = await res.text().catch(() => null);
    console.error("[api] upload http_error", { url, status: res.status, body });
    throw new ApiError({
      kind: "http_error",
      message: `Upload failed: ${res.status} ${res.statusText}\n${body ?? ""}`,
      status: res.status,
      url,
      responseText: body,
    });
  }

  return res.json() as Promise<UploadResponse>;
}

/* ── GET /import/jobs ── */

export function getImportJobs(): Promise<ListJobsResponse> {
  return fetchJson<ListJobsResponse>("/import/jobs").then((r) => r.data);
}

/* ── POST /import/jobs/{id}/run ── */

interface RunResponse {
  import_id: string;
  status: string;
  message: string;
}

async function postImportAction(
  path: string,
): Promise<RunResponse> {
  const url = `${API_BASE_URL}${path}`;
  let res: Response;
  try {
    res = await fetch(url, { method: "POST" });
  } catch (err: unknown) {
    const msg = err instanceof TypeError ? err.message : String(err);
    console.error("[api] import action network_error", { url, error: msg });
    throw new ApiError({
      kind: "network_error",
      message: `Cannot reach API at ${API_BASE_URL}.\n${msg}`,
      status: 0,
      url,
    });
  }
  if (!res.ok) {
    const body = await res.text().catch(() => null);
    throw new ApiError({
      kind: "http_error",
      message: `Import action failed: ${res.status} ${res.statusText}\n${body ?? ""}`,
      status: res.status,
      url,
      responseText: body,
    });
  }
  return res.json() as Promise<RunResponse>;
}

export function runImportJob(importId: string): Promise<RunResponse> {
  return postImportAction(`/import/jobs/${encodeURIComponent(importId)}/run`);
}

export function retryImportJob(importId: string): Promise<RunResponse> {
  return postImportAction(`/import/jobs/${encodeURIComponent(importId)}/retry`);
}

export function runAllImportJobs(): Promise<RunResponse> {
  return postImportAction("/import/jobs/run-all");
}

/* ── Phase 0.9: Literature Agent Chat ── */

export async function askLiteratureAgent(
  params: AgentAskRequest,
): Promise<AgentAskResponse> {
  const body = JSON.stringify({
    question: params.question,
    top_k: params.top_k ?? 10,
    chunk_types: params.chunk_types ?? null,
    include_assets: params.include_assets ?? true,
    include_evidence: params.include_evidence ?? true,
    paper_id: params.paper_id ?? null,
    use_llm: params.use_llm ?? false,
    return_context: params.return_context ?? true,
  });

  const res = await fetch(`${API_BASE_URL}/v1/agent/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError({
      kind: "http_error",
      message: `Agent API error (${res.status}): ${text.slice(0, 200)}`,
      status: res.status,
      url: `${API_BASE_URL}/v1/agent/ask`,
      responseText: text,
    });
  }

  return res.json() as Promise<AgentAskResponse>;
}

export async function queryAssets(
  params: QueryAssetsRequest,
): Promise<QueryAssetsResponse> {
  const body = JSON.stringify({
    query: params.query,
    top_k: params.top_k ?? 10,
    chunk_types: params.chunk_types ?? null,
    paper_id: params.paper_id ?? null,
    min_quality_score: params.min_quality_score ?? 0,
    include_metadata: params.include_metadata ?? true,
  });

  const res = await fetch(`${API_BASE_URL}/query/assets`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError({
      kind: "http_error",
      message: `Query assets error (${res.status}): ${text.slice(0, 200)}`,
      status: res.status,
      url: `${API_BASE_URL}/query/assets`,
      responseText: text,
    });
  }

  return res.json() as Promise<QueryAssetsResponse>;
}

/* ── Phase 2I: Web Import Center API ── */

import type {
  SessionCreateResponse,
  UploadSession,
  UploadResult,
  ImportPlan,
  PlanUpdateRequest,
  ConfirmImportResult,
  SessionListResponse,
  BatchUploadRequest,
} from "./import-types";

/** Create a new upload session */
export async function createUploadSession(): Promise<SessionCreateResponse> {
  return postJson<SessionCreateResponse>("/import/upload-session");
}

/** Get upload session details */
export async function getUploadSession(
  sessionId: string,
): Promise<UploadSession> {
  return fetchJson<UploadSession>(
    `/import/upload-session/${encodeURIComponent(sessionId)}`,
  ).then((r) => r.data);
}

/** Upload files as base64 batch */
export async function uploadFilesBatch(
  sessionId: string,
  files: { filename: string; content_base64: string; relative_path?: string }[],
): Promise<UploadResult> {
  const body: BatchUploadRequest = { files };
  return postJson<UploadResult>(
    `/import/upload-session/${encodeURIComponent(sessionId)}/upload-batch`,
    body,
  );
}

/** Upload files via multipart form data */
export async function uploadFilesMultipart(
  sessionId: string,
  files: File[],
): Promise<UploadResult> {
  const form = new FormData();
  for (const f of files) {
    form.append("files", f);
  }

  const url = `${API_BASE_URL}/import/upload-session/${encodeURIComponent(sessionId)}/files`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      body: form,
    });
  } catch (err: unknown) {
    const msg = err instanceof TypeError ? err.message : String(err);
    throw new ApiError({
      kind: "network_error",
      message: `Cannot reach API at ${API_BASE_URL}.\n${msg}`,
      status: 0,
      url,
    });
  }

  if (!res.ok) {
    const text = await res.text().catch(() => null);
    throw new ApiError({
      kind: "http_error",
      message: `Upload failed: ${res.status} ${res.statusText}\n${text ?? ""}`,
      status: res.status,
      url,
      responseText: text,
    });
  }

  return res.json() as Promise<UploadResult>;
}

/** Generate import plan */
export async function generateImportPlan(
  sessionId: string,
): Promise<ImportPlan> {
  return postJson<ImportPlan>(
    `/import/upload-session/${encodeURIComponent(sessionId)}/plan`,
  );
}

/** Update import plan with manual selections */
export async function updateImportPlan(
  sessionId: string,
  updates: PlanUpdateRequest,
): Promise<ImportPlan> {
  return patchJson<ImportPlan>(
    `/import/upload-session/${encodeURIComponent(sessionId)}/plan`,
    updates,
  );
}

/** Confirm and execute import */
export async function confirmImport(
  sessionId: string,
): Promise<ConfirmImportResult> {
  return postJson<ConfirmImportResult>(
    `/import/upload-session/${encodeURIComponent(sessionId)}/confirm`,
  );
}

/** List all upload sessions */
export async function listUploadSessions(): Promise<SessionListResponse> {
  return fetchJson<SessionListResponse>("/import/upload-sessions").then(
    (r) => r.data,
  );
}

/* ── Import Status Overview ── */

export interface ImportStatusResponse {
  article_bundles: {
    new: DirectoryScan;
    processing: DirectoryScan;
    processed: DirectoryScan;
    failed: DirectoryScan;
  };
  single_papers: {
    new: DirectoryScan;
    processed: DirectoryScan;
    failed: DirectoryScan;
  };
  loose_supplementary: {
    new: DirectoryScan;
    review_needed: DirectoryScan;
    failed: DirectoryScan;
  };
  web_uploads: {
    staging: DirectoryScan;
    imported: DirectoryScan;
    failed: DirectoryScan;
  };
  summary: ImportStatusSummary;
  generated_at: string;
}

export interface DirectoryScan {
  items: ScanItem[];
  count: number;
  path_key: string;
}

export interface ScanItem {
  name: string;
  relative_path: string;
  type: "directory" | "file";
  file_count?: number;
  dir_count?: number;
  pdf_count?: number;
  spreadsheet_count?: number;
  size?: number;
}

export interface ImportStatusSummary {
  article_bundles_new: number;
  article_bundles_processed: number;
  article_bundles_failed: number;
  single_papers_new: number;
  loose_supplementary_new: number;
  loose_supplementary_review_needed: number;
  web_uploads_staging: number;
  web_uploads_failed: number;
  total_pending: number;
  total_attention_needed: number;
}

/** Fetch comprehensive import status overview */
export async function getImportStatus(): Promise<ImportStatusResponse> {
  return fetchJson<ImportStatusResponse>("/import/status").then((r) => r.data);
}

/* ── Dry-run processing ── */

export interface DryRunResult {
  total_bundles: number;
  processed: number;
  failed: number;
  dry_run?: boolean;
  archive_mode?: string;
  safe?: boolean;
  note: string;
  next_commands?: string[];
  next_actions?: string[];
  results: {
    bundle_id: string;
    bundle_name: string;
    status: string;
    action: string;
    would_copy_main?: string;
    would_copy_suppl_count?: number;
  }[];
}

/** Dry-run article bundle processing */
export async function dryRunProcess(): Promise<DryRunResult> {
  return postJson<DryRunResult>("/import/process/dry-run");
}

/** Execute article bundle processing (copy-only, safe) */
export async function executeProcess(): Promise<DryRunResult> {
  return postJson<DryRunResult>("/import/process");
}

/* ── Low-level helpers ── */

async function postJson<T>(
  path: string,
  body?: unknown,
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (err: unknown) {
    const msg = err instanceof TypeError ? err.message : String(err);
    throw new ApiError({
      kind: "network_error",
      message: `Cannot reach API at ${API_BASE_URL}.\n${msg}`,
      status: 0,
      url,
    });
  }

  if (!res.ok) {
    const text = await res.text().catch(() => null);
    throw new ApiError({
      kind: "http_error",
      message: `API error (${res.status}): ${text ?? res.statusText}`,
      status: res.status,
      url,
      responseText: text,
    });
  }

  return res.json() as Promise<T>;
}

async function patchJson<T>(
  path: string,
  body?: unknown,
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (err: unknown) {
    const msg = err instanceof TypeError ? err.message : String(err);
    throw new ApiError({
      kind: "network_error",
      message: `Cannot reach API at ${API_BASE_URL}.\n${msg}`,
      status: 0,
      url,
    });
  }

  if (!res.ok) {
    const text = await res.text().catch(() => null);
    throw new ApiError({
      kind: "http_error",
      message: `API error (${res.status}): ${text ?? res.statusText}`,
      status: res.status,
      url,
      responseText: text,
    });
  }

  return res.json() as Promise<T>;
}
