"use client";

import { useState, useEffect } from "react";
import { Table2, Loader2, AlertTriangle, ChevronDown, ChevronRight, BarChart3 } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_SCIENTRA_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8710";

interface TableCard {
  table_id: string;
  paper_id: string;
  label: string;
  title: string;
  asset_path: string;
  caption: string;
  table_type: string;
  n_rows: number;
  n_columns: number;
  important_columns: string[];
  table_summary: string;
  key_finding: string;
  evidence_strength: string;
  linked_evidence_ids: string[];
  related_claims: string[];
  detected_entities: string[];
  statistical_fields: string[];
  warnings: string[];
  quality_score: number;
  overclaim_risk: string;
  confidence: number;
  mode: string;
}

const TABLE_TYPE_LABELS: Record<string, string> = {
  differential_expression: "Differential Expression",
  gene_expression: "Gene Expression",
  proteomics: "Proteomics",
  metabolomics: "Metabolomics",
  sample_metadata: "Sample Metadata",
  primer_table: "Primer Table",
  strain_table: "Strain Table",
  phenotype_table: "Phenotype Table",
  bioassay_table: "Bioassay Results",
  survival_table: "Survival Analysis",
  lc50_table: "LC50/EC50",
  statistical_result: "Statistical Results",
  pathway_enrichment: "Pathway Enrichment",
  taxonomy_table: "Taxonomy",
  method_parameter_table: "Method Parameters",
  supplementary_index: "Supplementary Index",
  unknown: "Unknown",
};

const STRENGTH_COLORS: Record<string, string> = {
  strong: "text-emerald-600 bg-emerald-50 dark:bg-emerald-950/20",
  moderate: "text-amber-600 bg-amber-50 dark:bg-amber-950/20",
  weak: "text-orange-600 bg-orange-50 dark:bg-orange-950/20",
  unclear: "text-gray-500 bg-gray-50 dark:bg-gray-800",
};


export function TableCardsPanel({ paperId }: { paperId: string }) {
  const [data, setData] = useState<{ available: boolean; message?: string; tables: TableCard[]; summary: any } | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const r = await fetch(`${API_BASE}/paper/${paperId}/table-cards`);
        setData(await r.json());
      } catch { setData(null); }
      finally { setLoading(false); }
    })();
  }, [paperId]);

  const toggle = (id: string) => setExpanded(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-4">
        <div className="flex items-center gap-2 mb-3"><Table2 className="size-4 text-muted-foreground" /><h3 className="text-sm font-semibold">Table Intelligence</h3></div>
        <Loader2 className="size-4 animate-spin text-muted-foreground mx-auto" />
      </div>
    );
  }

  if (!data?.available) {
    return (
      <div className="rounded-xl border bg-card p-4">
        <div className="flex items-center gap-2 mb-3"><Table2 className="size-4 text-muted-foreground" /><h3 className="text-sm font-semibold">Table Intelligence</h3></div>
        <p className="text-xs text-muted-foreground text-center py-2">Table intelligence not yet built.</p>
        <p className="text-[10px] text-muted-foreground/50 text-center">python Scripts/build_table_intelligence.py --paper-id {paperId} --mode auto</p>
      </div>
    );
  }

  const tables = data.tables || [];
  const hasWarnings = tables.some(t => t.warnings?.length > 0);

  return (
    <div className="rounded-xl border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2"><Table2 className="size-4 text-muted-foreground" /><h3 className="text-sm font-semibold">Table Intelligence</h3></div>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">{tables.length} tables</span>
      </div>

      {hasWarnings && <div className="flex items-center gap-1 text-[11px] text-amber-600"><AlertTriangle className="size-3" />Some tables have warnings</div>}

      <div className="space-y-1.5 max-h-96 overflow-y-auto">
        {tables.map(card => {
          const isExpanded = expanded.has(card.table_id);
          return (
            <div key={card.table_id} className="border rounded-lg overflow-hidden">
              <button onClick={() => toggle(card.table_id)} className="w-full flex items-center gap-2 p-2 text-left hover:bg-muted/30 transition-colors">
                {isExpanded ? <ChevronDown className="size-3 shrink-0" /> : <ChevronRight className="size-3 shrink-0" />}
                <Table2 className="size-3 shrink-0 text-emerald-500" />
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] font-medium truncate">{card.label}</p>
                  <p className="text-[10px] text-muted-foreground truncate">{TABLE_TYPE_LABELS[card.table_type] || card.table_type} · {card.n_rows}×{card.n_columns}</p>
                </div>
                <span className={`text-[9px] px-1 py-0.5 rounded ${STRENGTH_COLORS[card.evidence_strength] || STRENGTH_COLORS.unclear}`}>{card.evidence_strength}</span>
              </button>
              {isExpanded && (
                <div className="px-3 pb-3 space-y-2 border-t">
                  {card.title && <p className="text-[11px] font-medium pt-2">{card.title}</p>}
                  {card.table_summary && <p className="text-[10px] text-muted-foreground">{card.table_summary}</p>}
                  {card.key_finding && <div><p className="text-[9px] font-semibold uppercase text-muted-foreground">Key Finding</p><p className="text-[10px]">{card.key_finding}</p></div>}

                  <div className="grid grid-cols-2 gap-1 text-[10px]">
                    <span className="text-muted-foreground">Type: <b>{TABLE_TYPE_LABELS[card.table_type] || card.table_type}</b></span>
                    <span className="text-muted-foreground">Size: <b>{card.n_rows}×{card.n_columns}</b></span>
                    <span className="text-muted-foreground">Quality: <b>{Math.round(card.quality_score * 100)}%</b></span>
                    <span className="text-muted-foreground">Evidence: <b>{card.linked_evidence_ids?.length || 0} chunks</b></span>
                    <span className="text-muted-foreground">Mode: <b>{card.mode === "llm" ? "LLM" : "Rule"}</b></span>
                  </div>

                  {card.statistical_fields?.length > 0 && (
                    <div>
                      <p className="text-[9px] font-semibold uppercase text-muted-foreground">Statistical Fields</p>
                      <div className="flex flex-wrap gap-1">
                        {card.statistical_fields.map((f, i) => <span key={i} className="text-[9px] px-1 py-0.5 rounded bg-blue-50 dark:bg-blue-950/20 text-blue-700">{f}</span>)}
                      </div>
                    </div>
                  )}

                  {card.important_columns?.length > 0 && (
                    <div>
                      <p className="text-[9px] font-semibold uppercase text-muted-foreground">Important Columns</p>
                      <p className="text-[10px] text-muted-foreground">{card.important_columns.slice(0, 8).join(", ")}</p>
                    </div>
                  )}

                  {card.warnings?.length > 0 && (
                    <div className="rounded bg-amber-50 dark:bg-amber-950/20 p-1.5">
                      {card.warnings.slice(0, 3).map((w, i) => <p key={i} className="text-[9px] text-amber-700 flex gap-1"><AlertTriangle className="size-2.5 shrink-0 mt-0.5" />{w}</p>)}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
