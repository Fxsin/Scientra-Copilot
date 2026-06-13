"use client";

import { useEffect, useState } from "react";

interface Bundle {
  bundle_id: string;
  bundle_name: string;
  detected_main_pdf: string | null;
  tabular_supplementary_count: number;
  supplementary_pdf_count: number;
  other_file_count: number;
  processing_status: string;
  binding_method: string;
  match_confidence: string;
  warnings: string[];
}

interface LooseFile {
  file_name: string;
  file_type: string;
  status: string;
  requires_manual_review: boolean;
  reason: string;
}

export default function ImportPage() {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [loose, setLoose] = useState<LooseFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Bundle | null>(null);
  const [detail, setDetail] = useState<any>(null);

  useEffect(() => {
    fetch("/api/import/bundles").then(r => r.json()).then(d => {
      setBundles(d.bundles || []);
      setLoading(false);
    }).catch(() => setLoading(false));
    fetch("/api/import/loose-supplementary").then(r => r.json()).then(d => {
      setLoose(d.files || []);
    }).catch(() => {});
  }, []);

  const viewDetail = (bid: string) => {
    fetch(`/api/import/bundles/${bid}`).then(r => r.json()).then(d => {
      setDetail(d);
    });
  };

  const processed = bundles.filter(b => b.processing_status === "processed").length;
  const failed = bundles.filter(b => b.processing_status.startsWith("failed")).length;
  const tabular = bundles.reduce((s, b) => s + b.tabular_supplementary_count, 0);

  if (loading) return <div className="p-8 text-muted-foreground">Loading...</div>;

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-8">
      <h1 className="text-2xl font-bold">Import Dashboard</h1>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card label="Total Bundles" value={bundles.length} />
        <Card label="Processed" value={processed} color="text-emerald-600" />
        <Card label="Failed" value={failed} color={failed > 0 ? "text-red-500" : "text-muted-foreground"} />
        <Card label="Tabular Files" value={tabular} />
        <Card label="Review Needed" value={loose.length} color={loose.length > 0 ? "text-amber-600" : "text-muted-foreground"} />
      </div>

      {/* Bundle table */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Article Bundles</h2>
        {bundles.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            No bundles imported yet. Place article folders in{" "}
            <code className="bg-muted px-1 rounded">00_Inbox/article_bundles/new/</code>{" "}
            and run{" "}
            <code className="bg-muted px-1 rounded">python Scripts/process_article_bundles.py --process</code>
          </p>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left p-3">Bundle</th>
                  <th className="text-left p-3">Main PDF</th>
                  <th className="text-left p-3">Files</th>
                  <th className="text-left p-3">Status</th>
                  <th className="text-left p-3">Confidence</th>
                  <th className="text-left p-3">Warnings</th>
                </tr>
              </thead>
              <tbody>
                {bundles.map(b => (
                  <tr key={b.bundle_id} className="border-t hover:bg-muted/30 cursor-pointer"
                      onClick={() => viewDetail(b.bundle_id)}>
                    <td className="p-3 font-mono text-xs max-w-[200px] truncate" title={b.bundle_name}>
                      {b.bundle_name}
                    </td>
                    <td className="p-3 text-xs max-w-[150px] truncate" title={b.detected_main_pdf || ""}>
                      {b.detected_main_pdf || "N/A"}
                    </td>
                    <td className="p-3 text-xs">
                      {b.tabular_supplementary_count > 0 && <span className="mr-2">📊{b.tabular_supplementary_count}</span>}
                      {b.supplementary_pdf_count > 0 && <span className="mr-2">📄{b.supplementary_pdf_count}</span>}
                      {b.other_file_count > 0 && <span>📎{b.other_file_count}</span>}
                    </td>
                    <td className="p-3">
                      <StatusBadge status={b.processing_status} />
                    </td>
                    <td className="p-3 text-xs">
                      <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-700">{b.match_confidence}</span>
                    </td>
                    <td className="p-3 text-xs text-amber-600">
                      {b.warnings?.length || 0}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Detail panel */}
      {detail && !detail.error && (
        <section className="border rounded-lg p-4 bg-muted/20">
          <h2 className="text-lg font-semibold mb-3">Bundle Detail: {detail.bundle_name}</h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div><span className="text-muted-foreground">Main PDF:</span> {detail.detected_main_pdf || "N/A"}</div>
            <div><span className="text-muted-foreground">Binding:</span> <Badge>{detail.binding_method}</Badge> <Badge color="emerald">{detail.match_confidence}</Badge></div>
            <div><span className="text-muted-foreground">Processing:</span> {detail.processing_status}</div>
            <div><span className="text-muted-foreground">Ingest:</span> {detail.paper_ingest_status}</div>
          </div>
          {detail.tabular_supplementary_files?.length > 0 && (
            <div className="mt-3">
              <span className="text-sm font-medium">Tabular Files:</span>
              <ul className="text-xs text-muted-foreground ml-4 mt-1">
                {detail.tabular_supplementary_files.map((f: string) => <li key={f}>📊 {f}</li>)}
              </ul>
            </div>
          )}
          {detail.supplementary_pdfs?.length > 0 && (
            <div className="mt-2">
              <span className="text-sm font-medium">Supplementary PDFs:</span>
              <ul className="text-xs text-muted-foreground ml-4 mt-1">
                {detail.supplementary_pdfs.map((f: string) => <li key={f}>📄 {f}</li>)}
              </ul>
            </div>
          )}
          {detail.warnings?.length > 0 && (
            <div className="mt-3 p-2 bg-amber-50 rounded text-xs text-amber-700">
              {detail.warnings.map((w: string, i: number) => <p key={i}>⚠ {w}</p>)}
            </div>
          )}
        </section>
      )}

      {/* Loose supplementary */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Loose Supplementary (Review Needed)</h2>
        {loose.length === 0 ? (
          <p className="text-muted-foreground text-sm">No loose supplementary files pending review.</p>
        ) : (
          <div className="border rounded-lg p-3 bg-amber-50/50">
            <p className="text-xs text-amber-700 mb-2">
              Loose supplementary files require manual binding and will not enter entity index automatically.
            </p>
            <ul className="text-sm space-y-1">
              {loose.map(f => (
                <li key={f.file_name} className="flex items-center gap-2 text-xs">
                  <span className="text-amber-600">⚠</span>
                  <span>{f.file_name}</span>
                  <span className="text-muted-foreground">({f.file_type})</span>
                  <span className="text-amber-700">— review needed</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}

function Card({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="border rounded-lg p-4 bg-background">
      <div className={`text-2xl font-bold ${color || ""}`}>{value}</div>
      <div className="text-xs text-muted-foreground mt-1">{label}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    processed: "bg-emerald-100 text-emerald-700",
    scanned: "bg-blue-100 text-blue-700",
    pending: "bg-slate-100 text-slate-600",
    failed_empty: "bg-red-100 text-red-600",
    failed_no_main_pdf: "bg-red-100 text-red-600",
  };
  return <span className={`px-2 py-0.5 rounded text-xs ${colors[status] || "bg-slate-100"}`}>{status}</span>;
}

function Badge({ children, color }: { children: string; color?: string }) {
  const c = color === "emerald" ? "bg-emerald-100 text-emerald-700" : "bg-blue-100 text-blue-700";
  return <span className={`px-2 py-0.5 rounded text-xs ${c}`}>{children}</span>;
}
