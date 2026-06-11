import type {
  HealthResponse,
  PaperEvidence, EvidenceChunksResponse, EvidenceQueryResponse,
  PaperMetadata, PaperSummary, PaperTags, PapersResponse,
  QueryRequest, QueryResponse, QueryResultItem,
  ResearchMapTopic, StatsResponse,
} from "./types";
import { sanitizeResult } from "./types";

/* ── API base URL ── */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_SCIENTRA_API_URL?.replace(/\/$/, "") ||
  `http://127.0.0.1:${process.env.NEXT_PUBLIC_SCIENTRA_API_PORT || "8710"}` ||
  "http://127.0.0.1:8710";

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
    console.error("[api] network_error", { url, error: msg });
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
    console.error("[api] http_error", {
      url,
      status: res.status,
      statusText: res.statusText,
      body: body?.slice(0, 500),
    });
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

export async function getKnowledgeNetwork(
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
  return fetchJson<ResearchMapResponse>("/research-map").then((r) => r.data);
}

export async function getResearchMapTopic(topicId: string): Promise<{ topic: ResearchMapTopic }> {
  return fetchJson<{ topic: ResearchMapTopic }>(`/research-map/topic/${encodeURIComponent(topicId)}`).then((r) => r.data);
}

export function getPaperEvidence(paperId: string): Promise<PaperEvidence> {
  return fetchJson<PaperEvidence>(`/paper/${encodeURIComponent(paperId)}/evidence`).then((r) => r.data);
}

export function getPaperEvidenceChunks(paperId: string): Promise<EvidenceChunksResponse> {
  return fetchJson<EvidenceChunksResponse>(`/paper/${encodeURIComponent(paperId)}/evidence-chunks`).then((r) => r.data);
}

export async function queryEvidence(payload: { query: string; limit?: number; chunk_type?: string }): Promise<EvidenceQueryResponse> {
  return fetchJson<EvidenceQueryResponse>("/query/evidence", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then((r) => r.data);
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
