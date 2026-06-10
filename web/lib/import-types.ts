/* ── Import Status ── */

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

/* ── Import Item ── */

export interface ImportItem {
  id: string;
  filename: string;
  sizeBytes: number;
  status: ImportStatus;
  progress: number;          // 0–100
  currentStep: string;       // human-readable step name
  createdAt: string;         // ISO timestamp
  completedAt: string | null;
  error: string | null;
}

/* ── Format helpers ── */

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/* ── API response types ── */

/** Shape returned by POST /import/upload and GET /import/jobs */
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

/** Convert API job → ImportItem for the store */
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
