"use client";

import { useState, useEffect } from "react";
import { Package, FileText, Table2, Image, Archive, Paperclip, HelpCircle, Upload, RefreshCw, Loader2, AlertTriangle } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_SCIENTRA_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8710";

interface Asset {
  asset_id: string;
  paper_id: string;
  asset_type: string;
  filename: string;
  original_filename: string;
  relative_path: string;
  sha256: string;
  size_bytes: number;
  mime_type: string;
  extension: string;
  source: string;
  status: string;
  created_at: string;
  warnings: string[];
  errors: string[];
}

interface AssetsData {
  available: boolean;
  message?: string;
  main_pdf?: Asset | null;
  assets: Asset[];
  asset_counts: Record<string, number>;
  paper_assets_dir?: string;
}

const TYPE_ICONS: Record<string, React.ReactNode> = {
  main_pdf: <FileText className="size-3.5 text-blue-500" />,
  supplementary_pdf: <FileText className="size-3.5 text-indigo-500" />,
  supplementary_table: <Table2 className="size-3.5 text-emerald-500" />,
  dataset: <Table2 className="size-3.5 text-cyan-500" />,
  figure_image: <Image className="size-3.5 text-purple-500" />,
  table_image: <Image className="size-3.5 text-teal-500" />,
  archive: <Archive className="size-3.5 text-amber-500" />,
  attachment: <Paperclip className="size-3.5 text-gray-500" />,
  unknown: <HelpCircle className="size-3.5 text-gray-400" />,
};

const TYPE_LABELS: Record<string, string> = {
  main_pdf: "Main PDF",
  supplementary_pdf: "Supplementary PDF",
  supplementary_table: "Table",
  dataset: "Dataset",
  figure_image: "Figure",
  table_image: "Table Image",
  archive: "Archive",
  attachment: "Attachment",
  unknown: "Unknown",
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

export function PaperAssetsPanel({ paperId }: { paperId: string }) {
  const [data, setData] = useState<AssetsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const fetchAssets = async () => {
    try {
      const r = await fetch(`${API_BASE}/paper/${paperId}/assets`);
      setData(await r.json());
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssets();
  }, [paperId]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setUploading(true);
    setError("");

    // For each file, we'd need a proper upload handler.
    // Currently showing a note since multipart upload requires backend temp storage.
    // In production, this would POST to /paper/{id}/assets/upload with FormData.
    setError("File upload requires a temp upload directory. Use CLI for now: python Scripts/add_paper_asset.py --paper-id " + paperId + " --file <path>");
    setUploading(false);
  };

  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-4">
        <div className="flex items-center gap-2 mb-3">
          <Package className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Assets</h3>
        </div>
        <Loader2 className="size-4 animate-spin text-muted-foreground mx-auto" />
      </div>
    );
  }

  if (!data?.available) {
    return (
      <div className="rounded-xl border bg-card p-4">
        <div className="flex items-center gap-2 mb-3">
          <Package className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Assets</h3>
        </div>
        <p className="text-xs text-muted-foreground text-center py-2">
        {data?.message || "No supplementary files linked yet. Add files to enrich figures, tables, and datasets."}
      </p>
      <p className="text-[10px] text-muted-foreground/50 text-center">
        Run: python Scripts/init_paper_assets.py
      </p>
      </div>
    );
  }

  const counts = data.asset_counts || {};
  const assets = data.assets || [];
  const mainPdf = data.main_pdf;

  return (
    <div className="rounded-xl border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Package className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Assets</h3>
        </div>
        <button
          onClick={fetchAssets}
          className="p-1 hover:bg-muted rounded text-muted-foreground"
          title="Refresh"
        >
          <RefreshCw className="size-3.5" />
        </button>
      </div>

      {/* Main PDF Status */}
      <div className="flex items-center gap-2 text-xs">
        <FileText className="size-3.5 text-blue-500" />
        <span className="text-muted-foreground">Main PDF:</span>
        <span className={mainPdf ? "text-emerald-600 font-medium" : "text-amber-600"}>
          {mainPdf ? "registered" : "missing"}
        </span>
      </div>

      {/* Asset counts */}
      <div className="grid grid-cols-2 gap-1.5">
        {Object.entries(counts).map(([type, count]) => {
          if (count === 0) return null;
          return (
            <div key={type} className="flex items-center gap-1.5 text-xs">
              {TYPE_ICONS[type] || TYPE_ICONS.unknown}
              <span className="text-muted-foreground">{TYPE_LABELS[type] || type}:</span>
              <span className="font-medium">{count as number}</span>
            </div>
          );
        })}
        {assets.length === 0 && (
          <p className="text-xs text-muted-foreground col-span-2 text-center py-1">
            No assets registered yet.
          </p>
        )}
      </div>

      {/* Asset list (compact) */}
      {assets.length > 0 && (
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {assets.slice(0, 10).map(a => (
            <div key={a.asset_id} className="flex items-center gap-1.5 text-xs py-0.5">
              {TYPE_ICONS[a.asset_type] || TYPE_ICONS.unknown}
              <span className="truncate flex-1" title={a.filename}>{a.filename}</span>
              <span className="text-muted-foreground shrink-0">{formatSize(a.size_bytes)}</span>
              {a.status === "registered" && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" title="Registered" />}
              {a.warnings.length > 0 && <AlertTriangle className="size-3 text-amber-400 shrink-0" />}
            </div>
          ))}
          {assets.length > 10 && (
            <p className="text-[10px] text-muted-foreground text-center">
              + {assets.length - 10} more assets
            </p>
          )}
        </div>
      )}

      {/* Upload area */}
      <label className="flex items-center justify-center gap-1.5 border border-dashed rounded-lg p-2 cursor-pointer hover:bg-muted/30 text-xs text-muted-foreground transition-colors">
        <Upload className="size-3.5" />
        Add Asset
        <input
          type="file"
          multiple
          className="hidden"
          onChange={handleFileChange}
          disabled={uploading}
        />
      </label>

      {uploading && <Loader2 className="size-4 animate-spin mx-auto" />}
      {error && <p className="text-[10px] text-amber-600">{error}</p>}
    </div>
  );
}
