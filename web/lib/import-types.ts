/* ── Web Import Types — Upload Session, Plan, Confirm ── */

/* ── Legacy Import Status (used by file-status-badge, import-history-table, import-store) ── */

export type ImportStatus =
  | "waiting"
  | "uploading"
  | "queued"
  | "parsing"
  | "metadata"
  | "tagging"
  | "summary"
  | "embedding"
  | "completed"
  | "failed";

export const STATUS_CONFIG: Record<
  ImportStatus,
  { label: string; color: string; step: number }
> = {
  waiting:    { label: "Waiting",    color: "bg-muted text-muted-foreground",            step: 0 },
  uploading:  { label: "Uploading",  color: "bg-sky-100 text-sky-800 border-sky-200",    step: 1 },
  queued:     { label: "Queued",     color: "bg-slate-100 text-slate-700 border-slate-200", step: 2 },
  parsing:    { label: "Parsing",    color: "bg-violet-100 text-violet-800 border-violet-200", step: 3 },
  metadata:   { label: "Metadata",   color: "bg-indigo-100 text-indigo-800 border-indigo-200", step: 4 },
  tagging:    { label: "Tagging",    color: "bg-blue-100 text-blue-800 border-blue-200",  step: 5 },
  summary:    { label: "Summary",    color: "bg-cyan-100 text-cyan-800 border-cyan-200",  step: 6 },
  embedding:  { label: "Embedding",  color: "bg-teal-100 text-teal-800 border-teal-200",  step: 7 },
  completed:  { label: "Completed",  color: "bg-secondary/15 text-secondary border-secondary/30", step: 8 },
  failed:     { label: "Failed",     color: "bg-destructive/10 text-destructive border-destructive/20", step: -1 },
};

export const WORKFLOW_STEPS = [
  { key: "uploading" as const, label: "Upload" },
  { key: "queued" as const,    label: "Queue" },
  { key: "parsing" as const,   label: "Parse PDF" },
  { key: "metadata" as const,  label: "Extract Metadata" },
  { key: "tagging" as const,   label: "Assign Tags" },
  { key: "summary" as const,   label: "Generate Summary" },
  { key: "embedding" as const, label: "Vector Embedding" },
  { key: "completed" as const, label: "Complete" },
];

export interface ImportItem {
  id: string;
  filename: string;
  sizeBytes: number;
  status: ImportStatus;
  progress: number;
  currentStep: string;
  createdAt: string;
  completedAt: string | null;
  error: string | null;
}

export interface ImportJobResponse {
  import_id: string;
  filename: string;
  size_bytes: number;
  status: ImportStatus;
  progress: number;
  current_step: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface UploadResponse {
  uploaded: number;
  jobs: ImportJobResponse[];
}

export interface ListJobsResponse {
  total: number;
  jobs: ImportJobResponse[];
}

export function jobToItem(job: ImportJobResponse): ImportItem {
  return {
    id: job.import_id,
    filename: job.filename,
    sizeBytes: job.size_bytes,
    status: job.status,
    progress: job.progress,
    currentStep: job.current_step,
    createdAt: job.created_at,
    completedAt: job.status === "completed" ? job.updated_at : null,
    error: job.error_message,
  };
}

/* ── New Web Import Center Types ── */

export type ImportSessionStatus =
  | "created"
  | "uploading"
  | "planned"
  | "confirmed"
  | "imported"
  | "failed";

export type ImportType =
  | "article_bundle"
  | "single_paper"
  | "loose_supplementary"
  | "unsupported";

export type ImportConfidence = "high" | "medium" | "low";

/* ── Session ── */

export interface UploadSession {
  upload_session_id: string;
  staging_path: string;
  status: ImportSessionStatus;
  created_at: string;
  file_count: number;
  total_size: number;
  detected_pdfs: number;
  detected_tables: number;
  detected_supplementary_pdfs: number;
  unsupported_files: number;
  files: UploadedFile[];
}

export interface UploadedFile {
  filename: string;
  relative_path: string;
  size: number;
  extension: string;
  sha256?: string;
  status: "uploaded" | "unsupported" | "rejected";
}

export interface SessionCreateResponse {
  upload_session_id: string;
  staging_path: string;
  created_at: string;
}

/* ── Upload ── */

export interface UploadResult {
  upload_session_id: string;
  uploaded: number;
  rejected: number;
  uploaded_files: UploadedFile[];
  rejected_files: { filename: string; relative_path: string; reason: string }[];
  total_files: number;
}

export interface BatchUploadRequest {
  files: {
    filename: string;
    content_base64: string;
    relative_path?: string;
  }[];
}

/* ── Import Plan ── */

export interface MainPdfDetection {
  filename: string;
  relative_path: string;
  detection_reason: string;
  confidence: ImportConfidence;
}

export interface SupplementaryFileEntry {
  filename: string;
  relative_path: string;
  file_type: "spreadsheet" | "supplementary_pdf" | "document" | "archive";
  binding_method: string;
  match_confidence: ImportConfidence;
  entity_index_eligible: boolean;
  note?: string;
}

export interface UnsupportedFileEntry {
  filename: string;
  relative_path: string;
  extension: string;
  reason: string;
}

export interface MainPdfCandidate {
  filename: string;
  relative_path: string;
  score: number;
  reason: string;
}

export interface ImportPlan {
  upload_session_id: string;
  detected_import_type: ImportType;
  proposed_article_folder: string | null;
  main_pdf: MainPdfDetection | null;
  supplementary_files: SupplementaryFileEntry[];
  unsupported_files: UnsupportedFileEntry[];
  warnings: string[];
  errors: string[];
  requires_manual_review: boolean;
  suggested_next_action: string;
  main_pdf_candidates?: MainPdfCandidate[];
  message?: string;
}

/* ── Plan Update ── */

export interface PlanUpdateRequest {
  import_type?: ImportType;
  article_folder_name?: string;
  main_pdf_relative_path?: string;
  supplementary_relative_paths?: string[];
}

/* ── Confirm Result ── */

export interface ConfirmImportResult {
  status: "imported" | "error";
  import_type?: ImportType;
  article_bundle_path?: string;
  target_path?: string;
  files_copied: number;
  failed_files: { filename: string; error: string }[];
  processing_started?: boolean;
  processing_result?: {
    main_pdf: string | null;
    supplementary_count: number;
    warnings: string[];
  };
  next_steps: string[];
  error?: string;
}

/* ── Dashboard summary ── */

export interface SessionSummary {
  upload_session_id: string;
  status: string;
  file_count: number;
  created_at: string;
}

export interface SessionListResponse {
  sessions: SessionSummary[];
  total: number;
}

/* ── Format helpers ── */

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "N/A";
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function importTypeLabel(t: ImportType): string {
  const labels: Record<ImportType, string> = {
    article_bundle: "Article Bundle",
    single_paper: "Single Paper",
    loose_supplementary: "Loose Supplementary",
    unsupported: "Unsupported",
  };
  return labels[t] || t;
}

export function confidenceColor(c: ImportConfidence): string {
  const colors: Record<ImportConfidence, string> = {
    high: "bg-emerald-100 text-emerald-700",
    medium: "bg-amber-100 text-amber-700",
    low: "bg-red-100 text-red-700",
  };
  return colors[c] || "bg-slate-100 text-slate-600";
}

export function fileTypeIcon(ext: string): string {
  const icons: Record<string, string> = {
    ".pdf": "📄",
    ".xlsx": "📊",
    ".xls": "📊",
    ".csv": "📊",
    ".tsv": "📊",
    ".docx": "📝",
    ".zip": "📦",
  };
  return icons[ext] || "📎";
}
