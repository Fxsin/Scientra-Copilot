"use client";

import { useState, useEffect } from "react";
import { Image, Loader2, AlertTriangle, ChevronDown, ChevronRight, Microscope, Shield, Zap, Cpu } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_SCIENTRA_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8710";

interface FigureCard {
  figure_id: string;
  paper_id: string;
  label: string;
  title: string;
  asset_path: string;
  caption: string;
  figure_summary: string;
  key_finding: string;
  evidence_type: string;
  evidence_type_confidence: number;
  evidence_strength: string;
  related_claims: string[];
  related_methods: string[];
  linked_evidence_ids: string[];
  limitations: string[];
  warnings: string[];
  quality_score: number;
  overclaim_risk: string;
  confidence: number;
  mode: string;
  grounding_sources: string[];
}

interface FiguresData {
  available: boolean;
  message?: string;
  figures: FigureCard[];
  summary: {
    figure_count: number;
    mode: string;
  };
}

const EVIDENCE_TYPE_LABELS: Record<string, string> = {
  microscopy: "Microscopy",
  western_blot: "Western Blot",
  gel_image: "Gel Electrophoresis",
  survival_curve: "Survival Curve",
  bioassay: "Bioassay",
  binding_assay: "Binding Assay",
  expression_analysis: "Expression Analysis",
  heatmap: "Heatmap",
  volcano_plot: "Volcano Plot",
  phylogeny: "Phylogeny",
  structure_model: "Structure Model",
  statistical_plot: "Statistical Plot",
  workflow_diagram: "Workflow Diagram",
  unknown: "Unknown",
};

const STRENGTH_COLORS: Record<string, string> = {
  strong: "text-emerald-600 bg-emerald-50 dark:bg-emerald-950/20",
  moderate: "text-amber-600 bg-amber-50 dark:bg-amber-950/20",
  weak: "text-orange-600 bg-orange-50 dark:bg-orange-950/20",
  unclear: "text-gray-500 bg-gray-50 dark:bg-gray-800",
};

const OVERCLAIM_COLORS: Record<string, string> = {
  low: "text-emerald-600",
  medium: "text-amber-600",
  high: "text-red-600",
};

export function FigureCardsPanel({ paperId }: { paperId: string }) {
  const [data, setData] = useState<FiguresData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());

  const fetchData = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/paper/${paperId}/figure-cards`);
      setData(await r.json());
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [paperId]);

  const toggleCard = (id: string) => {
    setExpandedCards(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-4">
        <div className="flex items-center gap-2 mb-3">
          <Microscope className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Figure Intelligence</h3>
        </div>
        <Loader2 className="size-4 animate-spin text-muted-foreground mx-auto" />
      </div>
    );
  }

  if (!data?.available) {
    return (
      <div className="rounded-xl border bg-card p-4">
        <div className="flex items-center gap-2 mb-3">
          <Microscope className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Figure Intelligence</h3>
        </div>
        <p className="text-xs text-muted-foreground text-center py-2">
          Figure intelligence not yet built. Run the analysis to interpret figures.
        </p>
        <p className="text-[10px] text-muted-foreground/50 text-center">
          python Scripts/build_figure_intelligence.py --paper-id {paperId} --mode auto
        </p>
      </div>
    );
  }

  const figures = data.figures || [];
  const hasWarnings = figures.some(f => f.warnings.length > 0);
  const modeLabel = data.summary?.mode === "llm" ? "LLM" : "Rule-based";

  return (
    <div className="rounded-xl border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Microscope className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Figure Intelligence</h3>
        </div>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
          {modeLabel}
        </span>
      </div>

      {/* Summary stats */}
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span>{figures.length} figure{figures.length !== 1 ? "s" : ""}</span>
        {hasWarnings && (
          <span className="flex items-center gap-1 text-amber-600">
            <AlertTriangle className="size-3" />
            Warnings
          </span>
        )}
      </div>

      {/* Figure card list */}
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {figures.map(card => {
          const isExpanded = expandedCards.has(card.figure_id);
          return (
            <div
              key={card.figure_id}
              className="border rounded-lg overflow-hidden"
            >
              {/* Card header — always visible */}
              <button
                onClick={() => toggleCard(card.figure_id)}
                className="w-full flex items-center gap-2 p-2 text-left hover:bg-muted/30 transition-colors"
              >
                {isExpanded ? (
                  <ChevronDown className="size-3 shrink-0 text-muted-foreground" />
                ) : (
                  <ChevronRight className="size-3 shrink-0 text-muted-foreground" />
                )}
                <Image className="size-3 shrink-0 text-purple-500" />
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] font-medium truncate">
                    {card.label}
                  </p>
                  <p className="text-[10px] text-muted-foreground truncate">
                    {EVIDENCE_TYPE_LABELS[card.evidence_type] || card.evidence_type}
                  </p>
                </div>
                <span
                  className={`text-[9px] px-1 py-0.5 rounded ${STRENGTH_COLORS[card.evidence_strength] || STRENGTH_COLORS.unclear}`}
                >
                  {card.evidence_strength}
                </span>
              </button>

              {/* Expanded details */}
              {isExpanded && (
                <div className="px-3 pb-3 space-y-2 border-t">
                  {/* Title */}
                  {card.title && (
                    <p className="text-[11px] font-medium pt-2">{card.title}</p>
                  )}

                  {/* Figure summary */}
                  {card.figure_summary && (
                    <p className="text-[10px] text-muted-foreground leading-relaxed">
                      {card.figure_summary}
                    </p>
                  )}

                  {/* Key finding */}
                  {card.key_finding && (
                    <div>
                      <p className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground mb-0.5">
                        Key Finding
                      </p>
                      <p className="text-[10px]">{card.key_finding}</p>
                    </div>
                  )}

                  {/* Meta grid */}
                  <div className="grid grid-cols-2 gap-1 text-[10px]">
                    <div className="flex items-center gap-1">
                      <span className="text-muted-foreground">Type:</span>
                      <span>{EVIDENCE_TYPE_LABELS[card.evidence_type] || card.evidence_type}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="text-muted-foreground">Quality:</span>
                      <span>{Math.round(card.quality_score * 100)}%</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="text-muted-foreground">Overclaim:</span>
                      <span className={OVERCLAIM_COLORS[card.overclaim_risk] || ""}>
                        {card.overclaim_risk}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="text-muted-foreground">Evidence:</span>
                      <span>{card.linked_evidence_ids.length} chunks</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="text-muted-foreground">Mode:</span>
                      <span className="flex items-center gap-0.5">
                        {card.mode === "llm" ? (
                          <Cpu className="size-2.5 text-blue-500" />
                        ) : (
                          <Zap className="size-2.5 text-amber-500" />
                        )}
                        {card.mode === "llm" ? "LLM" : "Rule"}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="text-muted-foreground">Grounding:</span>
                      <span>{card.grounding_sources?.length || 0} sources</span>
                    </div>
                  </div>

                  {/* Related claims */}
                  {card.related_claims.length > 0 && (
                    <div>
                      <p className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground mb-0.5">
                        Related Claims ({card.related_claims.length})
                      </p>
                      <ul className="text-[10px] text-muted-foreground space-y-0.5 list-disc list-inside">
                        {card.related_claims.slice(0, 3).map((c, i) => (
                          <li key={i} className="truncate">{c}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Warnings */}
                  {card.warnings.length > 0 && (
                    <div className="rounded bg-amber-50 dark:bg-amber-950/20 p-1.5">
                      {card.warnings.slice(0, 3).map((w, i) => (
                        <p key={i} className="text-[9px] text-amber-700 dark:text-amber-400 flex items-start gap-1">
                          <AlertTriangle className="size-2.5 shrink-0 mt-0.5" />
                          {w}
                        </p>
                      ))}
                    </div>
                  )}

                  {/* Limitations */}
                  {card.limitations.length > 0 && (
                    <div>
                      <p className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground mb-0.5">
                        Limitations
                      </p>
                      <ul className="text-[10px] text-muted-foreground space-y-0.5 list-disc list-inside">
                        {card.limitations.slice(0, 3).map((l, i) => (
                          <li key={i}>{l}</li>
                        ))}
                      </ul>
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
