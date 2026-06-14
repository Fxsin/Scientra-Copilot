"use client";

import { useState, useEffect } from "react";
import { FileText, Loader2, AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_SCIENTRA_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8710";

interface SuppCard {
  supplementary_id: string;
  paper_id: string;
  asset_id: string;
  label: string;
  title: string;
  file_type: string;
  parse_status: string;
  section_count: number;
  evidence_count: number;
  chunk_count: number;
  supplementary_summary: string;
  key_contents: string[];
  main_evidence_types: string[];
  linked_figure_ids: string[];
  linked_table_ids: string[];
  linked_evidence_ids: string[];
  warnings: string[];
  quality_score: number;
  overclaim_risk: string;
  confidence: number;
  mode: string;
}

const STATUS_COLORS: Record<string, string> = {
  parsed: "text-emerald-600",
  unsupported: "text-amber-600",
  failed: "text-red-600",
  empty: "text-gray-500",
};

export function SupplementaryCardsPanel({ paperId }: { paperId: string }) {
  const [data, setData] = useState<{ available: boolean; message?: string; supplementaries: SuppCard[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const r = await fetch(`${API_BASE}/paper/${paperId}/supplementary-cards`);
        setData(await r.json());
      } catch { setData(null); }
      finally { setLoading(false); }
    })();
  }, [paperId]);

  const toggle = (id: string) => setExpanded(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });

  if (loading) {
    return <div className="rounded-xl border bg-card p-4"><div className="flex items-center gap-2 mb-3"><FileText className="size-4 text-muted-foreground" /><h3 className="text-sm font-semibold">Supplementary Intelligence</h3></div><Loader2 className="size-4 animate-spin mx-auto" /></div>;
  }

  if (!data?.available) {
    return <div className="rounded-xl border bg-card p-4"><div className="flex items-center gap-2 mb-3"><FileText className="size-4 text-muted-foreground" /><h3 className="text-sm font-semibold">Supplementary Intelligence</h3></div><p className="text-xs text-muted-foreground text-center py-2">{data?.message || "Not yet built."}</p><p className="text-[10px] text-muted-foreground/50 text-center">python Scripts/build_supplementary_intelligence.py --paper-id {paperId}</p></div>;
  }

  const supps = data.supplementaries || [];

  return (
    <div className="rounded-xl border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2"><FileText className="size-4 text-muted-foreground" /><h3 className="text-sm font-semibold">Supplementary Intelligence</h3></div>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">{supps.length} files</span>
      </div>

      <div className="space-y-1.5 max-h-96 overflow-y-auto">
        {supps.map(card => {
          const isExpanded = expanded.has(card.supplementary_id);
          return (
            <div key={card.supplementary_id} className="border rounded-lg overflow-hidden">
              <button onClick={() => toggle(card.supplementary_id)} className="w-full flex items-center gap-2 p-2 text-left hover:bg-muted/30">
                {isExpanded ? <ChevronDown className="size-3 shrink-0" /> : <ChevronRight className="size-3 shrink-0" />}
                <FileText className="size-3 shrink-0 text-indigo-500" />
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] font-medium truncate">{card.label}</p>
                  <p className="text-[10px] text-muted-foreground truncate">{card.file_type} · {card.section_count}s · {card.evidence_count}e · {card.chunk_count}c</p>
                </div>
                <span className={`text-[9px] px-1 py-0.5 rounded ${card.parse_status === "parsed" ? "bg-emerald-50 text-emerald-600" : "bg-amber-50 text-amber-600"}`}>{card.parse_status}</span>
              </button>
              {isExpanded && (
                <div className="px-3 pb-3 space-y-2 border-t">
                  {card.title && <p className="text-[11px] font-medium pt-2">{card.title}</p>}
                  {card.supplementary_summary && <p className="text-[10px] text-muted-foreground">{card.supplementary_summary}</p>}
                  <div className="grid grid-cols-2 gap-1 text-[10px]">
                    <span className="text-muted-foreground">Parse: <span className={STATUS_COLORS[card.parse_status] || ""}>{card.parse_status}</span></span>
                    <span className="text-muted-foreground">Type: <b>{card.file_type}</b></span>
                    <span className="text-muted-foreground">Sections: <b>{card.section_count}</b></span>
                    <span className="text-muted-foreground">Evidence: <b>{card.evidence_count}</b></span>
                    <span className="text-muted-foreground">Chunks: <b>{card.chunk_count}</b></span>
                    <span className="text-muted-foreground">Quality: <b>{Math.round(card.quality_score * 100)}%</b></span>
                    <span className="text-muted-foreground">Linked: <b>{(card.linked_figure_ids?.length || 0) + (card.linked_table_ids?.length || 0)}</b></span>
                    <span className="text-muted-foreground">Mode: <b>{card.mode === "llm" ? "LLM" : "Rule"}</b></span>
                  </div>
                  {card.main_evidence_types?.length > 0 && <div><p className="text-[9px] font-semibold uppercase text-muted-foreground">Evidence Types</p><div className="flex flex-wrap gap-1">{card.main_evidence_types.map((t, i) => <span key={i} className="text-[9px] px-1 py-0.5 rounded bg-blue-50 dark:bg-blue-950/20 text-blue-700">{t}</span>)}</div></div>}
                  {card.warnings?.length > 0 && <div className="rounded bg-amber-50 dark:bg-amber-950/20 p-1.5">{card.warnings.slice(0, 3).map((w, i) => <p key={i} className="text-[9px] text-amber-700 flex gap-1"><AlertTriangle className="size-2.5 shrink-0 mt-0.5" />{w}</p>)}</div>}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
