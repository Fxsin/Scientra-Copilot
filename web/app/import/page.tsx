"use client";

import { useState, useCallback, useEffect, useRef, type DragEvent } from "react";
import {
  Upload, FileText, AlertTriangle, Loader2, CheckCircle2,
  XCircle, FolderOpen, FileSpreadsheet, Archive, File, Copy,
  Trash2, Wand2, Send, RefreshCw, ChevronDown, ChevronRight,
  Eye, Download, ExternalLink, Info, Settings2, type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  UploadSession, ImportPlan, UploadedFile, MainPdfCandidate,
  SupplementaryFileEntry, ConfirmImportResult, ImportType,
} from "@/lib/import-types";
import {
  formatFileSize, formatTime, importTypeLabel,
  confidenceColor, fileTypeIcon,
} from "@/lib/import-types";
import {
  createUploadSession, getUploadSession,
  generateImportPlan, updateImportPlan, confirmImport,
  getImportStatus, dryRunProcess,
  API_BASE_URL,
} from "@/lib/api";
import type { ImportStatusResponse, DryRunResult } from "@/lib/api";

/* ── Allowed extensions for upload ── */
const ALLOWED_EXTENSIONS = [
  ".pdf", ".xlsx", ".xls", ".csv", ".tsv", ".docx", ".zip",
];
const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100 MB — matches backend MAX_FILE_SIZE

/* ── Helper: read file as base64 ── */
function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Strip data:...;base64, prefix
      const b64 = result.split(",")[1] || result;
      resolve(b64);
    };
    reader.onerror = () => reject(new Error(`Failed to read: ${file.name}`));
    reader.readAsDataURL(file);
  });
}

export default function ImportPage() {
  /* ── State ── */
  const [session, setSession] = useState<UploadSession | null>(null);
  const [plan, setPlan] = useState<ImportPlan | null>(null);
  const [confirmResult, setConfirmResult] = useState<ConfirmImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<"upload" | "plan" | "review" | "confirm" | "done">("upload");
  const [apiConnected, setApiConnected] = useState<boolean | null>(null); // null=checking, true/false

  /* Manual review state */
  const [selectedMainPdf, setSelectedMainPdf] = useState<string>("");
  const [selectedSuppl, setSelectedSuppl] = useState<Set<string>>(new Set());
  const [articleFolderName, setArticleFolderName] = useState("");
  const [importType, setImportType] = useState<ImportType>("article_bundle");

  /* Import Status Overview state */
  const [importStatus, setImportStatus] = useState<ImportStatusResponse | null>(null);
  const [showStatus, setShowStatus] = useState(true);
  const [dryRunResult, setDryRunResult] = useState<DryRunResult | null>(null);

  /* ── Fetch import status on mount ── */
  useEffect(() => {
    getImportStatus()
      .then((s) => { setImportStatus(s); setApiConnected(true); })
      .catch(() => { setApiConnected(false); });
  }, [confirmResult]); // refresh after import completes

  /* ── Create session on mount ── */
  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const s = await createUploadSession();
        if (!cancelled) { setSession(s as unknown as UploadSession); setApiConnected(true); }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to create session");
      }
    }
    init();
    return () => { cancelled = true; };
  }, []);

  /* ── Refresh session ── */
  const refreshSession = useCallback(async () => {
    if (!session?.upload_session_id) return;
    try {
      const s = await getUploadSession(session.upload_session_id);
      setSession(s);
    } catch {
      // ignore
    }
  }, [session?.upload_session_id]);

  /* ── File upload handler ── */
  const handleFiles = useCallback(async (fileList: FileList | File[]) => {
    if (!session?.upload_session_id) {
      setError("No active session. Please wait for session creation.");
      return;
    }

    const files = Array.from(fileList);
    const accepted: File[] = [];
    const rejected: string[] = [];

    for (const f of files) {
      // File size enforcement (100 MB, matches backend)
      if (f.size > MAX_FILE_SIZE) {
        rejected.push(`${f.name} (${formatFileSize(f.size)} exceeds 100 MB limit)`);
        continue;
      }
      const ext = "." + f.name.split(".").pop()?.toLowerCase();
      if (ALLOWED_EXTENSIONS.includes(ext)) {
        accepted.push(f);
      } else {
        rejected.push(f.name);
      }
    }

    if (rejected.length > 0) {
      setError(`Skipped: ${rejected.join(", ")}`);
    }

    if (accepted.length === 0) return;

    setLoading(true);
    setError(null);

    // Collect folder-relative paths (webkitRelativePath from folder uploads)
    const relativePaths = accepted.map(f => f.webkitRelativePath || f.name);

    try {
      // Try multipart first, fallback to base64 batch
      try {
        // Build multipart form with relative_paths metadata
        const form = new FormData();
        for (const f of accepted) {
          form.append("files", f);
        }
        form.append("relative_paths", JSON.stringify(relativePaths));

        const url = `${API_BASE_URL}/import/upload-session/${encodeURIComponent(session.upload_session_id)}/files`;
        const res = await fetch(url, { method: "POST", body: form });

        if (res.ok) {
          const result = await res.json();
          if (result.uploaded > 0) {
            await refreshSession();
            setStep("upload");
            return; // success — skip fallback
          }
        }
        // If multipart returned non-ok or uploaded=0, fall through to base64
        console.warn("Multipart upload returned partial success, falling back to base64");
      } catch (mpErr) {
        console.warn("Multipart upload failed, falling back to base64:", mpErr);
      }

      // Fallback: base64 batch upload (always works, preserves relative paths)
      const batch = await Promise.all(
        accepted.map(async (f, i) => ({
          filename: f.name,
          content_base64: await readFileAsBase64(f),
          relative_path: relativePaths[i] || f.name,
        }))
      );
      const { uploadFilesBatch } = await import("@/lib/api");
      const batchResult = await uploadFilesBatch(session.upload_session_id, batch);
      if (batchResult.uploaded > 0) {
        await refreshSession();
        setStep("upload");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }, [session?.upload_session_id, refreshSession]);

  /* ── Generate Plan ── */
  const handleGeneratePlan = useCallback(async () => {
    if (!session?.upload_session_id) return;
    setLoading(true);
    setError(null);
    try {
      const p = await generateImportPlan(session.upload_session_id);
      setPlan(p);
      // Pre-populate manual review
      setSelectedMainPdf(p.main_pdf?.relative_path || "");
      setArticleFolderName(p.proposed_article_folder || "");
      setImportType(p.detected_import_type);
      setSelectedSuppl(new Set(p.supplementary_files.map(s => s.relative_path)));
      setStep(p.requires_manual_review ? "review" : "confirm");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate plan");
    } finally {
      setLoading(false);
    }
  }, [session?.upload_session_id]);

  /* ── Confirm Import ── */
  const handleConfirm = useCallback(async () => {
    if (!session?.upload_session_id) return;
    setLoading(true);
    setError(null);
    try {
      const result = await confirmImport(session.upload_session_id);
      setConfirmResult(result);
      setStep("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setLoading(false);
    }
  }, [session?.upload_session_id]);

  /* ── Update Plan (manual review) ── */
  const handleUpdatePlan = useCallback(async () => {
    if (!session?.upload_session_id || !plan) return;
    setLoading(true);
    setError(null);
    try {
      const updated = await updateImportPlan(session.upload_session_id, {
        import_type: importType,
        article_folder_name: articleFolderName,
        main_pdf_relative_path: selectedMainPdf || undefined,
        supplementary_relative_paths: Array.from(selectedSuppl),
      });
      setPlan(updated);
      setStep("confirm");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update plan");
    } finally {
      setLoading(false);
    }
  }, [session?.upload_session_id, plan, importType, articleFolderName, selectedMainPdf, selectedSuppl]);

  /* ── Reset ── */
  const handleReset = useCallback(async () => {
    setPlan(null);
    setConfirmResult(null);
    setError(null);
    setStep("upload");
    try {
      const s = await createUploadSession();
      setSession(s as unknown as UploadSession);
    } catch {
      // keep old session
    }
  }, []);

  /* ── Dry-run processing ── */
  const handleDryRun = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await dryRunProcess();
      setDryRunResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Dry-run failed");
    } finally {
      setLoading(false);
    }
  }, []);

  /* ── Derive stats ── */
  const uploadedFiles = session?.files?.filter(f => f.status === "uploaded") || [];
  const unsupportedCount = session?.files?.filter(f => f.status === "unsupported").length || 0;

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Import Center</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Drag & drop papers, supplementary files, or article folders
          </p>
        </div>
        <div className="flex items-center gap-2">
          {session && (
            <span className="text-xs text-muted-foreground font-mono">
              Session: {session.upload_session_id.slice(0, 20)}…
            </span>
          )}
          <button
            onClick={handleReset}
            className="inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs hover:bg-muted"
          >
            <RefreshCw className="size-3" />
            New Session
          </button>
        </div>
      </div>

      {/* ── Step indicator ── */}
      <StepBar current={step} />

      {/* ── Quick Start / API not connected ── */}
      {apiConnected === false && (
        <div className="rounded-lg border-2 border-blue-200 bg-gradient-to-b from-blue-50/80 to-white p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex size-10 items-center justify-center rounded-full bg-blue-100">
              <Info className="size-5 text-blue-600" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-blue-900">Quick Start — First Time Setup</h2>
              <p className="text-sm text-blue-600">
                The API server needs to be running for import to work.
                Choose one of the options below.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* Option 1: Unified command */}
            <div className="rounded-lg border bg-white p-4 space-y-2">
              <div className="flex items-center gap-2">
                <span className="inline-flex size-6 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 text-xs font-bold">1</span>
                <h3 className="font-semibold text-sm">Start Both (Recommended)</h3>
              </div>
              <p className="text-xs text-muted-foreground">
                One command starts the API server + web frontend together.
                The API will be auto-detected once it&apos;s ready.
              </p>
              <CopyableCommand cmd="cd web && npm run dev" />
              <p className="text-[10px] text-muted-foreground">
                This runs <code className="bg-muted px-0.5 rounded">scripts/dev-launcher.js</code> —
                it starts Python API on :8710 first, then Next.js on :3000.
              </p>
            </div>

            {/* Option 2: Separate terminals */}
            <div className="rounded-lg border bg-white p-4 space-y-2">
              <div className="flex items-center gap-2">
                <span className="inline-flex size-6 items-center justify-center rounded-full bg-blue-100 text-blue-700 text-xs font-bold">2</span>
                <h3 className="font-semibold text-sm">Separate Terminals</h3>
              </div>
              <p className="text-xs text-muted-foreground">Terminal 1 — API server:</p>
              <CopyableCommand cmd="python Scripts/run_api_server.py --port 8710" />
              <p className="text-xs text-muted-foreground mt-1">Terminal 2 — Web frontend:</p>
              <CopyableCommand cmd="cd web && npm run next:dev" />
            </div>
          </div>

          <div className="mt-4 flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 p-3">
            <AlertTriangle className="size-4 text-amber-500 mt-0.5 shrink-0" />
            <div className="text-xs text-amber-700">
              <strong>Requirements:</strong> Python 3.11+, Node.js 20+, and dependencies installed.
              <br />
              Run <code className="bg-amber-100 px-0.5 rounded">pip install fastapi uvicorn pyyaml</code> and{" "}
              <code className="bg-amber-100 px-0.5 rounded">cd web && npm install</code> if not already done.
            </div>
          </div>
        </div>
      )}

      {/* ── Import Status Overview ── */}
      {importStatus && (
        <StatusOverview
          status={importStatus}
          show={showStatus}
          onToggle={() => setShowStatus(!showStatus)}
          onDryRun={handleDryRun}
          dryRunResult={dryRunResult}
          loading={loading}
        />
      )}

      {/* ── Error ── */}
      {error && (
        <div className="flex items-start gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
          <AlertTriangle className="size-4 mt-0.5 shrink-0" />
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-auto shrink-0">
            <XCircle className="size-4" />
          </button>
        </div>
      )}

      {/* ══════════════════════════════════════════════════
          1. DRAG-AND-DROP UPLOAD ZONE
          ══════════════════════════════════════════════════ */}
      {step === "upload" && (
        <DropZone
          onFiles={handleFiles}
          loading={loading}
          sessionExists={!!session}
        />
      )}

      {/* ══════════════════════════════════════════════════
          2. UPLOAD SESSION PANEL
          ══════════════════════════════════════════════════ */}
      {session && step !== "done" && (
        <SessionPanel
          session={session}
          onRefresh={refreshSession}
          onGeneratePlan={handleGeneratePlan}
          loading={loading}
          canGenerate={uploadedFiles.length > 0}
        />
      )}

      {/* ══════════════════════════════════════════════════
          3. IMPORT PLAN PREVIEW
          ══════════════════════════════════════════════════ */}
      {plan && (step === "confirm" || step === "review") && (
        <PlanPreview plan={plan} />
      )}

      {/* ══════════════════════════════════════════════════
          4. MANUAL REVIEW UI
          ══════════════════════════════════════════════════ */}
      {plan && step === "review" && (
        <ManualReview
          plan={plan}
          selectedMainPdf={selectedMainPdf}
          onSelectMainPdf={setSelectedMainPdf}
          selectedSuppl={selectedSuppl}
          onToggleSuppl={(p) => {
            const next = new Set(selectedSuppl);
            if (next.has(p)) next.delete(p); else next.add(p);
            setSelectedSuppl(next);
          }}
          articleFolderName={articleFolderName}
          onFolderNameChange={setArticleFolderName}
          importType={importType}
          onImportTypeChange={setImportType}
          onUpdatePlan={handleUpdatePlan}
          loading={loading}
        />
      )}

      {/* ══════════════════════════════════════════════════
          5. CONFIRM IMPORT
          ══════════════════════════════════════════════════ */}
      {plan && step === "confirm" && (
        <ConfirmPanel
          plan={plan}
          onConfirm={handleConfirm}
          onBackToReview={() => plan.requires_manual_review ? setStep("review") : setStep("upload")}
          loading={loading}
        />
      )}

      {/* ══════════════════════════════════════════════════
          6. DONE / RESULT
          ══════════════════════════════════════════════════ */}
      {step === "done" && confirmResult && (
        <DonePanel result={confirmResult} onNewImport={handleReset} />
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   SUB-COMPONENTS
   ═══════════════════════════════════════════════════════ */

/* ── Step Bar ── */
function StepBar({ current }: { current: string }) {
  const steps = [
    { key: "upload", label: "Upload" },
    { key: "plan", label: "Review Plan" },
    { key: "review", label: "Manual Fix" },
    { key: "confirm", label: "Confirm" },
    { key: "done", label: "Done" },
  ];
  const idx = steps.findIndex(s => s.key === current);

  return (
    <div className="flex items-center gap-1">
      {steps.map((s, i) => (
        <div key={s.key} className="flex items-center gap-1">
          <div className={cn(
            "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium",
            i <= idx ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground",
          )}>
            {i < idx ? <CheckCircle2 className="size-3" /> : <span className="size-3 text-center">{i + 1}</span>}
            {s.label}
          </div>
          {i < steps.length - 1 && <div className={cn("w-4 h-px", i < idx ? "bg-primary/40" : "bg-muted-foreground/20")} />}
        </div>
      ))}
    </div>
  );
}

/* ── Drop Zone ── */
function DropZone({ onFiles, loading, sessionExists }: {
  onFiles: (files: FileList | File[]) => void;
  loading: boolean;
  sessionExists: boolean;
}) {
  const [over, setOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    if (e.dataTransfer.files?.length) onFiles(e.dataTransfer.files);
  }, [onFiles]);

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={(e) => { e.preventDefault(); setOver(false); }}
      onDrop={handleDrop}
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed p-10 text-center transition-colors",
        over ? "border-primary bg-primary/5" :
        loading ? "border-primary/40 bg-primary/5" :
        "border-border hover:border-muted-foreground/30",
      )}
    >
      <div className={cn(
        "flex size-14 items-center justify-center rounded-full transition-colors",
        over ? "bg-primary/20 text-primary" :
        loading ? "bg-primary/10 text-primary" :
        "bg-muted text-muted-foreground",
      )}>
        {loading ? <Loader2 className="size-7 animate-spin" strokeWidth={1.5} /> :
         over ? <FileText className="size-7" strokeWidth={1.5} /> :
         <Upload className="size-7" strokeWidth={1.5} />}
      </div>

      <div>
        <p className="text-sm font-medium text-foreground">
          {loading ? "Uploading…" : over ? "Drop files here" :
           "Drag papers, supplementary files, or article folders here"}
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          Recommended: one folder per article
        </p>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={loading || !sessionExists}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
            loading || !sessionExists
              ? "border-muted bg-muted text-muted-foreground cursor-not-allowed"
              : "border-border bg-background hover:bg-muted",
          )}
        >
          <File className="size-3.5" />
          Select Files
        </button>
        <button
          onClick={() => folderInputRef.current?.click()}
          disabled={loading || !sessionExists}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
            loading || !sessionExists
              ? "border-muted bg-muted text-muted-foreground cursor-not-allowed"
              : "border-border bg-background hover:bg-muted",
          )}
        >
          <FolderOpen className="size-3.5" />
          Select Folder
        </button>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept={ALLOWED_EXTENSIONS.join(",")}
        multiple
        className="hidden"
        onChange={(e) => e.target.files && onFiles(e.target.files)}
      />
      <input
        ref={folderInputRef}
        type="file"
        // @ts-expect-error webkitdirectory is non-standard but widely supported
        webkitdirectory=""
        multiple
        className="hidden"
        onChange={(e) => e.target.files && onFiles(e.target.files)}
      />

      <p className="text-[10px] text-muted-foreground/60">
        PDF · Excel · CSV · TSV · DOCX · ZIP — Max 100 MB per file
      </p>
    </div>
  );
}

/* ── Session Panel ── */
function SessionPanel({ session, onRefresh, onGeneratePlan, loading, canGenerate }: {
  session: UploadSession;
  onRefresh: () => void;
  onGeneratePlan: () => void;
  loading: boolean;
  canGenerate: boolean;
}) {
  const files = session.files || [];
  const uploaded = files.filter(f => f.status === "uploaded");

  return (
    <section className="rounded-lg border bg-card">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h2 className="font-semibold text-sm">Upload Session</h2>
        <button onClick={onRefresh} className="text-xs text-muted-foreground hover:text-foreground">
          <RefreshCw className="size-3 inline mr-1" />Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 p-4 border-b">
        <Stat label="Files" value={uploaded.length} />
        <Stat label="Total Size" value={formatFileSize(session.total_size)} />
        <Stat label="PDFs" value={session.detected_pdfs} color="text-blue-600" />
        <Stat label="Tables" value={session.detected_tables} color="text-emerald-600" />
        <Stat label="Unsupported" value={session.unsupported_files}
              color={session.unsupported_files > 0 ? "text-amber-600" : "text-muted-foreground"} />
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="max-h-48 overflow-y-auto border-b">
          {files.map((f, i) => (
            <div key={i} className={cn(
              "flex items-center gap-3 px-4 py-2 text-xs border-b last:border-b-0",
              f.status === "unsupported" && "bg-amber-50/50",
            )}>
              <span>{fileTypeIcon(f.extension)}</span>
              <span className="flex-1 truncate font-mono" title={f.relative_path}>
                {f.relative_path}
              </span>
              <span className="text-muted-foreground">{formatFileSize(f.size)}</span>
              <span className={cn(
                "px-1.5 py-0.5 rounded text-[10px] font-medium",
                f.status === "uploaded" ? "bg-emerald-100 text-emerald-700" :
                f.status === "unsupported" ? "bg-amber-100 text-amber-700" :
                "bg-red-100 text-red-700",
              )}>
                {f.status}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Generate Plan */}
      <div className="flex items-center justify-between px-4 py-3">
        {files.length === 0 ? (
          <p className="text-xs text-muted-foreground">Upload files to begin.</p>
        ) : (
          <p className="text-xs text-muted-foreground">
            {uploaded.length} file{uploaded.length !== 1 ? "s" : ""} ready for import planning.
          </p>
        )}
        <button
          onClick={onGeneratePlan}
          disabled={!canGenerate || loading}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-colors",
            canGenerate && !loading
              ? "bg-primary text-primary-foreground hover:bg-primary/90"
              : "bg-muted text-muted-foreground cursor-not-allowed",
          )}
        >
          {loading ? <Loader2 className="size-4 animate-spin" /> : <Wand2 className="size-4" />}
          Generate Import Plan
        </button>
      </div>
    </section>
  );
}

function Stat({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="text-center">
      <div className={cn("text-lg font-bold", color || "")}>{value}</div>
      <div className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</div>
    </div>
  );
}

/* ── Import Status Overview ── */
function StatusOverview({ status, show, onToggle, onDryRun, dryRunResult, loading }: {
  status: import("@/lib/api").ImportStatusResponse;
  show: boolean;
  onToggle: () => void;
  onDryRun: () => void;
  dryRunResult: import("@/lib/api").DryRunResult | null;
  loading: boolean;
}) {
  const s = status.summary;
  const totalPending = s.total_pending;
  const totalAttention = s.total_attention_needed;

  return (
    <section className="rounded-lg border bg-card">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between px-4 py-3 hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {show ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
          <h2 className="font-semibold text-sm">Import Status Overview</h2>
          {totalPending > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 text-xs font-medium">
              {totalPending} pending
            </span>
          )}
          {totalAttention > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-xs font-medium">
              {totalAttention} need attention
            </span>
          )}
          {totalPending === 0 && totalAttention === 0 && (
            <span className="text-xs text-emerald-600">✓ All clear</span>
          )}
        </div>
      </button>

      {show && (
        <div className="border-t px-4 py-3 space-y-3">
          {/* Summary grid */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
            <MiniStat label="New Bundles" value={s.article_bundles_new} color="text-blue-600" />
            <MiniStat label="Processed" value={s.article_bundles_processed} color="text-emerald-600" />
            <MiniStat label="Failed Bundles" value={s.article_bundles_failed}
                      color={s.article_bundles_failed > 0 ? "text-red-600" : "text-muted-foreground"} />
            <MiniStat label="New Papers" value={s.single_papers_new} />
            <MiniStat label="Loose Suppl" value={s.loose_supplementary_new}
                      color={s.loose_supplementary_new > 0 ? "text-amber-600" : "text-muted-foreground"} />
            <MiniStat label="Review Needed" value={s.loose_supplementary_review_needed}
                      color={s.loose_supplementary_review_needed > 0 ? "text-amber-600" : "text-muted-foreground"} />
            <MiniStat label="Web Staging" value={s.web_uploads_staging} color="text-blue-600" />
            <MiniStat label="Web Failed" value={s.web_uploads_failed}
                      color={s.web_uploads_failed > 0 ? "text-red-600" : "text-muted-foreground"} />
          </div>

          {/* Per-directory detail */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
            <DirGroup label="Article Bundles" dirs={status.article_bundles} />
            <DirGroup label="Single Papers" dirs={status.single_papers} />
            <DirGroup label="Loose Supplementary" dirs={status.loose_supplementary} />
            <DirGroup label="Web Uploads" dirs={status.web_uploads} />
          </div>

          {/* Dry-Run Button */}
          <div className="flex items-center justify-between border-t pt-3">
            <div className="text-xs text-muted-foreground">
              <span className="font-medium">Processing:</span>{" "}
              {dryRunResult
                ? `Dry-run complete: ${dryRunResult.processed} ready, ${dryRunResult.failed} skipped`
                : "Review bundles and run processing"}
            </div>
            <button
              onClick={onDryRun}
              disabled={loading}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                loading ? "bg-muted text-muted-foreground cursor-not-allowed" : "hover:bg-muted",
              )}
            >
              {loading ? <Loader2 className="size-3 animate-spin" /> : <Settings2 className="size-3" />}
              Dry-Run Scan
            </button>
          </div>

          {/* Dry-Run Result Details */}
          {dryRunResult && dryRunResult.results.length > 0 && (
            <div className="border-t pt-2 max-h-40 overflow-y-auto">
              <p className="text-xs font-medium mb-1">Planned Actions (no files modified):</p>
              {dryRunResult.results.map((r, i) => (
                <div key={i} className="flex items-center gap-2 text-xs py-0.5 border-b last:border-b-0">
                  <span className={cn(
                    "px-1 py-0 rounded text-[10px]",
                    r.status === "dry_run_planned" ? "bg-blue-100 text-blue-700" :
                    r.status.startsWith("skipped") ? "bg-amber-100 text-amber-700" :
                    "bg-slate-100 text-slate-600",
                  )}>
                    {r.status}
                  </span>
                  <span className="flex-1 truncate font-mono">{r.bundle_name}</span>
                  {r.would_copy_main && (
                    <span className="text-muted-foreground truncate max-w-[120px]">
                      → {r.would_copy_main.split("/").pop()}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function MiniStat({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="flex items-center justify-between rounded bg-muted/30 px-2 py-1">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-bold", color || "")}>{value}</span>
    </div>
  );
}

function DirGroup({ label, dirs }: { label: string; dirs: Record<string, { count: number; path_key: string }> }) {
  return (
    <div className="rounded bg-muted/20 px-2 py-1.5">
      <p className="font-medium text-muted-foreground mb-0.5">{label}</p>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5">
        {Object.entries(dirs).map(([key, val]) => (
          <span key={key} className="inline-flex items-center gap-1">
            <span className="text-muted-foreground">{key}:</span>
            <span className={cn("font-medium", val.count > 0 ? "text-foreground" : "text-muted-foreground/50")}>
              {val.count}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

/* ── Plan Preview ── */
function PlanPreview({ plan }: { plan: ImportPlan }) {
  const [showSuppl, setShowSuppl] = useState(true);
  const [showWarnings, setShowWarnings] = useState(true);

  const statusColor = plan.errors.length > 0 ? "border-red-300 bg-red-50/50" :
    plan.requires_manual_review ? "border-amber-300 bg-amber-50/50" :
    plan.detected_import_type === "unsupported" ? "border-slate-300 bg-slate-50/50" :
    "border-emerald-300 bg-emerald-50/50";

  const statusIcon = plan.errors.length > 0 ? <XCircle className="size-5 text-red-500" /> :
    plan.requires_manual_review ? <AlertTriangle className="size-5 text-amber-500" /> :
    plan.detected_import_type === "unsupported" ? <Info className="size-5 text-slate-500" /> :
    <CheckCircle2 className="size-5 text-emerald-500" />;

  return (
    <section className={cn("rounded-lg border-2 p-4", statusColor)}>
      <div className="flex items-center gap-3 mb-3">
        {statusIcon}
        <div>
          <h2 className="font-semibold">Import Plan</h2>
          <p className="text-xs text-muted-foreground">
            {importTypeLabel(plan.detected_import_type)}
            {plan.proposed_article_folder && ` → ${plan.proposed_article_folder}/`}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
        <Field label="Import Type" value={importTypeLabel(plan.detected_import_type)} />
        <Field label="Article Folder" value={plan.proposed_article_folder || "N/A"} mono />
        {plan.main_pdf ? (
          <>
            <Field label="Main PDF" value={plan.main_pdf.filename} mono />
            <Field label="Detection" value={plan.main_pdf.detection_reason.replace(/_/g, " ")} />
            <Field label="Confidence">
              <span className={cn("px-2 py-0.5 rounded text-xs font-medium", confidenceColor(plan.main_pdf.confidence))}>
                {plan.main_pdf.confidence}
              </span>
            </Field>
          </>
        ) : (
          <Field label="Main PDF" value="None detected" mono color="text-red-600" />
        )}
      </div>

      {/* Supplementary files */}
      {plan.supplementary_files.length > 0 && (
        <div className="mt-3">
          <button
            onClick={() => setShowSuppl(!showSuppl)}
            className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            {showSuppl ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
            Supplementary Files ({plan.supplementary_files.length})
          </button>
          {showSuppl && (
            <div className="mt-1 grid grid-cols-1 md:grid-cols-2 gap-1">
              {plan.supplementary_files.map((s, i) => (
                <div key={i} className="flex items-center gap-2 px-2 py-1 rounded text-xs bg-background">
                  <span>{s.file_type === "spreadsheet" ? "📊" : s.file_type === "supplementary_pdf" ? "📄" :
                         s.file_type === "document" ? "📝" : "📦"}</span>
                  <span className="flex-1 truncate font-mono">{s.filename}</span>
                  <span className={confidenceColor(s.match_confidence)}>{s.match_confidence}</span>
                  {s.entity_index_eligible && (
                    <span className="text-[10px] text-emerald-600 bg-emerald-50 px-1 rounded">entity</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Warnings */}
      {plan.warnings.length > 0 && (
        <div className="mt-3">
          <button
            onClick={() => setShowWarnings(!showWarnings)}
            className="flex items-center gap-1 text-xs font-medium text-amber-600 hover:text-amber-700"
          >
            {showWarnings ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
            Warnings ({plan.warnings.length})
          </button>
          {showWarnings && (
            <ul className="mt-1 space-y-1">
              {plan.warnings.map((w, i) => (
                <li key={i} className="flex items-start gap-1.5 text-xs text-amber-700">
                  <AlertTriangle className="size-3 mt-0.5 shrink-0" />
                  {w}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Errors */}
      {plan.errors.length > 0 && (
        <div className="mt-3 p-2 rounded bg-red-100/50">
          <p className="text-xs font-medium text-red-700">Errors:</p>
          <ul className="text-xs text-red-600">
            {plan.errors.map((e, i) => (
              <li key={i}>• {e}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Loose supplementary message */}
      {plan.detected_import_type === "loose_supplementary" && (
        <div className="mt-3 p-3 rounded-lg bg-amber-100/70 text-xs text-amber-800">
          <strong>⚠ This looks like loose supplementary data.</strong>
          <p className="mt-1">
            It cannot enter the entity index until manually bound to a parent paper.
            You can still import it for later binding.
          </p>
        </div>
      )}
    </section>
  );
}

function Field({ label, value, mono, color, children }: {
  label: string; value?: string; mono?: boolean; color?: string; children?: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase text-muted-foreground tracking-wider">{label}</div>
      {children || (
        <div className={cn("text-sm truncate", mono && "font-mono text-xs", color)}>
          {value || "—"}
        </div>
      )}
    </div>
  );
}

/* ── Manual Review UI ── */
function ManualReview({
  plan, selectedMainPdf, onSelectMainPdf, selectedSuppl, onToggleSuppl,
  articleFolderName, onFolderNameChange, importType, onImportTypeChange,
  onUpdatePlan, loading,
}: {
  plan: ImportPlan;
  selectedMainPdf: string;
  onSelectMainPdf: (v: string) => void;
  selectedSuppl: Set<string>;
  onToggleSuppl: (v: string) => void;
  articleFolderName: string;
  onFolderNameChange: (v: string) => void;
  importType: ImportType;
  onImportTypeChange: (v: ImportType) => void;
  onUpdatePlan: () => void;
  loading: boolean;
}) {
  return (
    <section className="rounded-lg border-2 border-amber-300 bg-amber-50/30 p-4 space-y-4">
      <div className="flex items-center gap-2">
        <AlertTriangle className="size-5 text-amber-600" />
        <h2 className="font-semibold">Manual Review Required</h2>
      </div>

      {/* Main PDF Selection */}
      {plan.main_pdf_candidates && plan.main_pdf_candidates.length > 0 && (
        <div>
          <label className="text-xs font-medium">Select Main PDF</label>
          <p className="text-xs text-muted-foreground mb-2">
            Multiple PDFs detected. Please choose which one is the main paper.
          </p>
          <div className="space-y-1">
            {plan.main_pdf_candidates.map((c) => (
              <label key={c.relative_path} className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg border text-sm cursor-pointer transition-colors",
                selectedMainPdf === c.relative_path
                  ? "border-primary bg-primary/10"
                  : "border-border hover:bg-muted/50",
              )}>
                <input
                  type="radio"
                  name="mainPdf"
                  value={c.relative_path}
                  checked={selectedMainPdf === c.relative_path}
                  onChange={() => onSelectMainPdf(c.relative_path)}
                  className="size-4"
                />
                <span className="flex-1 font-mono text-xs truncate">{c.filename}</span>
                <span className={cn("text-xs px-2 py-0.5 rounded", c.score > 0 ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700")}>
                  score: {c.score}
                </span>
                <span className="text-[10px] text-muted-foreground">{c.reason.replace(/_/g, " ")}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Supplementary File Selection */}
      {plan.supplementary_files.length > 0 && (
        <div>
          <label className="text-xs font-medium">Supplementary Files</label>
          <p className="text-xs text-muted-foreground mb-2">
            Check files to include as supplementary.
          </p>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {plan.supplementary_files.map((s) => (
              <label key={s.relative_path} className="flex items-center gap-3 px-3 py-1.5 rounded text-sm hover:bg-muted/50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedSuppl.has(s.relative_path)}
                  onChange={() => onToggleSuppl(s.relative_path)}
                  className="size-4 rounded"
                />
                <span>{s.file_type === "spreadsheet" ? "📊" : s.file_type === "supplementary_pdf" ? "📄" : "📝"}</span>
                <span className="flex-1 font-mono text-xs truncate">{s.filename}</span>
                <span className="text-xs text-muted-foreground">{s.file_type}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Article Folder Name */}
      <div>
        <label className="text-xs font-medium">Article Folder Name</label>
        <input
          type="text"
          value={articleFolderName}
          onChange={(e) => onFolderNameChange(e.target.value)}
          className="mt-1 w-full rounded-lg border px-3 py-2 text-sm font-mono"
          placeholder="e.g., Zhang_2024_Nature"
        />
      </div>

      {/* Import Type */}
      <div>
        <label className="text-xs font-medium">Import Method</label>
        <div className="flex gap-2 mt-1">
          {(["article_bundle", "single_paper", "loose_supplementary"] as ImportType[]).map((t) => (
            <label key={t} className={cn(
              "flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border text-xs font-medium cursor-pointer transition-colors",
              importType === t
                ? "border-primary bg-primary/10 text-primary"
                : "border-border hover:bg-muted/50",
            )}>
              <input
                type="radio"
                name="importType"
                value={t}
                checked={importType === t}
                onChange={() => onImportTypeChange(t)}
                className="hidden"
              />
              {importTypeLabel(t)}
            </label>
          ))}
        </div>
      </div>

      {/* Action */}
      <div className="flex justify-end">
        <button
          onClick={onUpdatePlan}
          disabled={loading || !selectedMainPdf}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold",
            !loading && selectedMainPdf
              ? "bg-primary text-primary-foreground hover:bg-primary/90"
              : "bg-muted text-muted-foreground cursor-not-allowed",
          )}
        >
          {loading ? <Loader2 className="size-4 animate-spin" /> : <Wand2 className="size-4" />}
          Apply & Continue
        </button>
      </div>
    </section>
  );
}

/* ── Confirm Panel ── */
function ConfirmPanel({ plan, onConfirm, onBackToReview, loading }: {
  plan: ImportPlan;
  onConfirm: () => void;
  onBackToReview: () => void;
  loading: boolean;
}) {
  return (
    <section className="rounded-lg border-2 border-emerald-300 bg-emerald-50/30 p-4 space-y-4">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="size-5 text-emerald-600" />
        <div>
          <h2 className="font-semibold">Ready to Import</h2>
          <p className="text-xs text-muted-foreground">
            Review the plan and confirm to copy files into the library.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 text-sm bg-background rounded-lg p-3">
        <div>
          <span className="text-xs text-muted-foreground">Action:</span>
          <span className="ml-1 font-medium">
            {plan.detected_import_type === "loose_supplementary"
              ? "Copy to loose supplementary inbox"
              : `Copy to article_bundles/new/${plan.proposed_article_folder}/`}
          </span>
        </div>
        <div>
          <span className="text-xs text-muted-foreground">Files:</span>
          <span className="ml-1 font-medium">
            {1 + plan.supplementary_files.length} file{(1 + plan.supplementary_files.length) !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        ℹ Files are copied (not moved). Original staging files remain intact.
        After import, run <code className="bg-muted px-1 rounded">python Scripts/process_article_bundles.py --process</code> to process.
      </p>

      <div className="flex items-center justify-between">
        <button
          onClick={onBackToReview}
          disabled={loading}
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Back
        </button>
        <button
          onClick={onConfirm}
          disabled={loading}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg px-6 py-2.5 text-sm font-bold transition-colors",
            loading
              ? "bg-muted text-muted-foreground cursor-not-allowed"
              : "bg-emerald-600 text-white hover:bg-emerald-700",
          )}
        >
          {loading ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
          Confirm Import
        </button>
      </div>
    </section>
  );
}

/* ── Done Panel ── */
function DonePanel({ result, onNewImport }: {
  result: ConfirmImportResult;
  onNewImport: () => void;
}) {
  return (
    <div className="space-y-6">
      {/* Success banner */}
      <div className="rounded-lg border-2 border-emerald-300 bg-emerald-50/50 p-6 text-center">
        <CheckCircle2 className="size-12 text-emerald-500 mx-auto mb-3" />
        <h2 className="text-xl font-bold text-emerald-700">Import Complete</h2>
        <p className="text-sm text-emerald-600 mt-1">
          {result.files_copied} file{result.files_copied !== 1 ? "s" : ""} imported successfully
        </p>
        {result.article_bundle_path && (
          <p className="text-xs font-mono text-emerald-600 mt-2 bg-emerald-100/50 rounded px-3 py-1 inline-block">
            {result.article_bundle_path}
          </p>
        )}
        {result.target_path && (
          <p className="text-xs font-mono text-emerald-600 mt-2 bg-emerald-100/50 rounded px-3 py-1 inline-block">
            {result.target_path}
          </p>
        )}
      </div>

      {/* Failed files */}
      {result.failed_files.length > 0 && (
        <div className="rounded-lg border border-red-200 bg-red-50/50 p-4">
          <h3 className="text-sm font-semibold text-red-700 mb-2">
            Failed Files ({result.failed_files.length})
          </h3>
          {result.failed_files.map((f, i) => (
            <div key={i} className="text-xs text-red-600 flex items-start gap-2">
              <XCircle className="size-3 mt-0.5" />
              <span className="font-mono">{f.filename}</span>
              <span>— {f.error}</span>
            </div>
          ))}
        </div>
      )}

      {/* Next Processing Panel */}
      {result.status === "imported" && result.import_type !== "loose_supplementary" && (
        <div className="rounded-lg border-2 border-blue-200 bg-blue-50/30 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Settings2 className="size-5 text-blue-600" />
            <h3 className="font-semibold text-blue-800">Next: Process Article Bundle</h3>
          </div>
          <p className="text-xs text-blue-700">
            Files are in the inbox. Run article bundle processing to parse, tag, and index them.
          </p>

          <div className="bg-background rounded-lg border p-3 space-y-2">
            <p className="text-xs font-medium text-muted-foreground">Recommended commands:</p>
            <CopyableCommand cmd="python Scripts/process_article_bundles.py --scan" />
            <CopyableCommand cmd="python Scripts/process_article_bundles.py --process --dry-run" />
            <CopyableCommand cmd="python Scripts/process_article_bundles.py --process --archive-mode copy" />
          </div>

          <div className="flex items-center gap-2 text-xs text-blue-600">
            <Info className="size-3" />
            <span>Processing uses <strong>copy mode only</strong>. Original files are never moved or deleted.</span>
          </div>
        </div>
      )}

      {/* Loose supplementary note */}
      {result.status === "imported" && result.import_type === "loose_supplementary" && (
        <div className="rounded-lg border-2 border-amber-200 bg-amber-50/30 p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="size-5 text-amber-600" />
            <h3 className="font-semibold text-amber-800">Manual Binding Required</h3>
          </div>
          <p className="text-xs text-amber-700 mt-1">
            This is loose supplementary data. It will not enter the entity index until
            manually bound to a parent paper. Check <code className="bg-amber-100 px-1 rounded">/library</code> and
            the <code className="bg-amber-100 px-1 rounded">/import</code> loose supplementary section for binding options.
          </p>
        </div>
      )}

      {/* Next steps */}
      {result.next_steps.length > 0 && (
        <div className="rounded-lg border bg-card p-4">
          <h3 className="text-sm font-semibold mb-2">Next Steps</h3>
          <ul className="space-y-1.5">
            {result.next_steps.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <span className="text-emerald-500 mt-0.5">→</span>
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Quick links */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <QuickLink href="/library" label="Library" icon="📚" />
        <QuickLink href="/assets" label="Assets" icon="📊" />
        <QuickLink href="/evidence" label="Evidence" icon="🔬" />
        <QuickLink href="/import" label="New Import" icon="📥" onClick={onNewImport} />
      </div>
    </div>
  );
}

function QuickLink({ href, label, icon, onClick }: {
  href: string; label: string; icon: string; onClick?: () => void;
}) {
  return (
    <a
      href={href}
      onClick={onClick}
      className="flex items-center gap-2 rounded-lg border px-4 py-3 text-sm font-medium hover:bg-muted transition-colors"
    >
      <span className="text-lg">{icon}</span>
      {label}
    </a>
  );
}

function CopyableCommand({ cmd }: { cmd: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(cmd).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <div className="flex items-center gap-2 bg-slate-900 text-slate-100 rounded px-3 py-1.5 font-mono text-xs group">
      <span className="flex-1 select-all">{cmd}</span>
      <button
        onClick={handleCopy}
        className="text-slate-400 hover:text-white transition-colors shrink-0"
        title="Copy to clipboard"
      >
        {copied ? <CheckCircle2 className="size-3 text-emerald-400" /> : <Copy className="size-3" />}
      </button>
    </div>
  );
}
