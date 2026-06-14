"use client";

import { useState, useEffect } from "react";
import {
  Brain, Sparkles, AlertTriangle, ShieldCheck, ChevronDown, ChevronRight,
  Loader2, FlaskConical, Hash, Gauge, Info, Lightbulb, Search, Beaker,
} from "lucide-react";
import { getAISummaryV2, getEvidenceEnrichment, getAIGaps, getAIHypotheses, getGapHypothesisQuality } from "@/lib/api";
import type {
  AISummaryV2Response, EvidenceEnrichmentResponse, EnrichedChunk,
  AIGapsResponse, AIHypothesesResponse, ResearchGap, Hypothesis,
  GapHypothesisQualityResponse,
} from "@/lib/types";

const GAP_TYPE_LABELS: Record<string, string> = {
  mechanistic: "Mechanism",
  methodological: "Method",
  evidence: "Evidence",
  scope: "Scope",
  contradiction: "Contradiction",
  translation: "Translation",
  unknown: "Unknown",
};

const RISK_COLORS: Record<string, string> = {
  low: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  medium: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  high: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
};

interface Props {
  paperId: string;
}

export function AIEnrichmentPanel({ paperId }: Props) {
  const [summaryV2, setSummaryV2] = useState<AISummaryV2Response | null>(null);
  const [enrichment, setEnrichment] = useState<EvidenceEnrichmentResponse | null>(null);
  const [gaps, setGaps] = useState<AIGapsResponse | null>(null);
  const [hypotheses, setHypotheses] = useState<AIHypothesesResponse | null>(null);
  const [quality, setQuality] = useState<GapHypothesisQualityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!paperId) return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const [s, e, g, h, q] = await Promise.all([
          getAISummaryV2(paperId).catch(() => null),
          getEvidenceEnrichment(paperId).catch(() => null),
          getAIGaps(paperId).catch(() => null),
          getAIHypotheses(paperId).catch(() => null),
          getGapHypothesisQuality(paperId).catch(() => null),
        ]);
        if (cancelled) return;
        setSummaryV2(s);
        setEnrichment(e);
        setGaps(g);
        setHypotheses(h);
        setQuality(q);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [paperId]);

  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-4 flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        Loading AI enrichment…
      </div>
    );
  }

  const hasSummary = summaryV2?.available;
  const hasEnrichment = enrichment?.available;
  const hasGaps = gaps?.available;
  const hasHypotheses = hypotheses?.available;

  if (!hasSummary && !hasEnrichment && !hasGaps && !hasHypotheses) {
    return (
      <div className="rounded-xl border bg-card p-4">
        <div className="flex items-center gap-2 mb-2">
          <Brain className="size-4 text-muted-foreground" />
          <span className="text-sm font-semibold">AI Enrichment</span>
        </div>
        <p className="text-xs text-muted-foreground">
          AI enrichment not available. Enable AI enrichment in{" "}
          <strong>Settings → AI Provider</strong> and run the workflow with{" "}
          <code className="text-[11px] bg-muted px-1 rounded">
            ai_enrichment.enabled: true
          </code>
          .
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-card p-4 space-y-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full text-left"
      >
        <Brain className="size-4 text-primary" />
        <span className="text-sm font-semibold">AI Enrichment</span>
        {hasSummary && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
            V2
          </span>
        )}
        {/* Quality Badge (Phase 2.3.1) */}
        {quality?.available && quality.recommendation && (
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
            quality.recommendation === "accept"
              ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
              : quality.recommendation === "manual_review"
              ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
              : quality.recommendation === "reject"
              ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
              : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
          }`}>
            {quality.recommendation === "accept" ? "✓ Quality OK"
              : quality.recommendation === "manual_review" ? "⚠ Review"
              : quality.recommendation === "reject" ? "✗ Reject"
              : "? No Data"}
            {quality.overall_quality_score !== undefined &&
              ` (${(quality.overall_quality_score * 100).toFixed(0)}%)`}
          </span>
        )}
        <span className="flex-1" />
        {expanded ? (
          <ChevronDown className="size-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="size-4 text-muted-foreground" />
        )}
      </button>

      {expanded && (
        <div className="space-y-4 pt-1">
          {/* ── Summary V2 ── */}
          {hasSummary && summaryV2 && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold flex items-center gap-1.5 text-primary">
                <Sparkles className="size-3" />
                AI Summary V2
              </h4>

              {/* Confidence */}
              {summaryV2.confidence !== undefined && (
                <div className="flex items-center gap-2 text-xs">
                  <Gauge className="size-3 text-muted-foreground" />
                  <span className="text-muted-foreground">Confidence:</span>
                  <span className={`font-medium ${
                    summaryV2.confidence >= 0.8 ? "text-emerald-600" :
                    summaryV2.confidence >= 0.5 ? "text-amber-600" :
                    "text-red-600"
                  }`}>
                    {(summaryV2.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              )}

              {/* Core Finding */}
              {summaryV2.core_finding && (
                <div className="text-xs space-y-1">
                  <span className="font-medium text-muted-foreground">Core Finding</span>
                  <p className="leading-relaxed">{summaryV2.core_finding}</p>
                </div>
              )}

              {/* Research Question */}
              {summaryV2.research_question && (
                <div className="text-xs space-y-1">
                  <span className="font-medium text-muted-foreground">Research Question</span>
                  <p className="leading-relaxed italic">{summaryV2.research_question}</p>
                </div>
              )}

              {/* Key Evidence */}
              {summaryV2.key_evidence && summaryV2.key_evidence.length > 0 && (
                <div className="text-xs space-y-1">
                  <span className="font-medium text-muted-foreground">
                    Key Evidence ({summaryV2.key_evidence.length})
                  </span>
                  <ul className="space-y-1.5">
                    {summaryV2.key_evidence.map((ev, i) => (
                      <li key={i} className="pl-3 border-l-2 border-primary/30">
                        <span className="font-medium">{ev.claim}</span>
                        <span className="text-muted-foreground block mt-0.5">
                          {ev.evidence}
                        </span>
                        <span className="text-[10px] text-muted-foreground/70">
                          {ev.evidence_type}
                          {ev.source_hint && ` • ${ev.source_hint}`}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Methods */}
              {summaryV2.method_summary && summaryV2.method_summary.length > 0 && (
                <div className="text-xs space-y-1">
                  <span className="font-medium text-muted-foreground">
                    <FlaskConical className="size-3 inline mr-1" />
                    Methods
                  </span>
                  <ul className="list-disc list-inside space-y-0.5 text-muted-foreground">
                    {summaryV2.method_summary.map((m, i) => (
                      <li key={i}>{m}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Claims & Limitations */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {summaryV2.main_claims && summaryV2.main_claims.length > 0 && (
                  <div className="text-xs space-y-1">
                    <span className="font-medium text-muted-foreground">Main Claims</span>
                    <ul className="list-disc list-inside space-y-0.5">
                      {summaryV2.main_claims.slice(0, 5).map((c, i) => (
                        <li key={i} className="text-muted-foreground">{c}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {summaryV2.limitations && summaryV2.limitations.length > 0 && (
                  <div className="text-xs space-y-1">
                    <span className="font-medium text-muted-foreground flex items-center gap-1">
                      <AlertTriangle className="size-3 text-amber-500" />
                      Limitations
                    </span>
                    <ul className="list-disc list-inside space-y-0.5">
                      {summaryV2.limitations.map((l, i) => (
                        <li key={i} className="text-muted-foreground">{l}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Entities */}
              {summaryV2.important_entities && summaryV2.important_entities.length > 0 && (
                <div className="text-xs space-y-1">
                  <span className="font-medium text-muted-foreground">Key Entities</span>
                  <div className="flex flex-wrap gap-1">
                    {summaryV2.important_entities.map((ent, i) => (
                      <span
                        key={i}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-muted"
                      >
                        <Hash className="size-2.5" />
                        {ent.name}
                        <span className="text-muted-foreground">({ent.type})</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Warnings */}
              {summaryV2.warnings && summaryV2.warnings.length > 0 && (
                <div className="text-xs rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 p-2 space-y-0.5">
                  {summaryV2.warnings.map((w, i) => (
                    <div key={i} className="flex items-start gap-1 text-amber-700 dark:text-amber-400">
                      <AlertTriangle className="size-3 mt-0.5 shrink-0" />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Generation info */}
              <div className="text-[10px] text-muted-foreground/60 flex items-center gap-3">
                {summaryV2.model && <span>Model: {summaryV2.model}</span>}
                {summaryV2.usage && (
                  <span>
                    {summaryV2.usage.total_tokens} tokens • $
                    {summaryV2.usage.cost_estimate.toFixed(6)}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* ── Evidence Enrichment ── */}
          {hasEnrichment && enrichment && (
            <div className="space-y-2 border-t pt-3">
              <h4 className="text-xs font-semibold flex items-center gap-1.5 text-primary">
                <ShieldCheck className="size-3" />
                AI Evidence Claims
                {enrichment.enriched_chunks !== undefined && (
                  <span className="font-normal text-muted-foreground">
                    ({enrichment.enriched_chunks} chunks)
                  </span>
                )}
              </h4>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="rounded-lg bg-muted p-2 text-center">
                  <div className="font-semibold">{enrichment.enriched_chunks ?? 0}</div>
                  <div className="text-[10px] text-muted-foreground">Enriched</div>
                </div>
                <div className="rounded-lg bg-muted p-2 text-center">
                  <div className="font-semibold">{enrichment.batch_count ?? 0}</div>
                  <div className="text-[10px] text-muted-foreground">Batches</div>
                </div>
                <div className="rounded-lg bg-muted p-2 text-center">
                  <div className="font-semibold">
                    {enrichment.usage ? `$${enrichment.usage.cost_estimate.toFixed(4)}` : "--"}
                  </div>
                  <div className="text-[10px] text-muted-foreground">Cost</div>
                </div>
              </div>

              {/* Chunk cards */}
              {enrichment.chunks && enrichment.chunks.length > 0 && (
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {enrichment.chunks.slice(0, 10).map((chunk: EnrichedChunk, i: number) => (
                    <div
                      key={chunk.chunk_id || i}
                      className="rounded-lg border p-2 text-xs space-y-1"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] px-1 rounded bg-muted text-muted-foreground">
                          {chunk.evidence_type}
                        </span>
                        <span className={`text-[10px] px-1 rounded ${
                          chunk.evidence_strength === "strong"
                            ? "bg-emerald-100 text-emerald-700"
                            : chunk.evidence_strength === "moderate"
                            ? "bg-amber-100 text-amber-700"
                            : "bg-slate-100 text-slate-600"
                        }`}>
                          {chunk.evidence_strength}
                        </span>
                        {chunk.confidence > 0 && (
                          <span className="text-[10px] text-muted-foreground">
                            {(chunk.confidence * 100).toFixed(0)}%
                          </span>
                        )}
                      </div>
                      {chunk.ai_claim && (
                        <p className="font-medium">{chunk.ai_claim}</p>
                      )}
                      {chunk.ai_finding && (
                        <p className="text-muted-foreground">{chunk.ai_finding}</p>
                      )}
                      {chunk.entity_mentioned && chunk.entity_mentioned.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {chunk.entity_mentioned.map((e, j) => (
                            <span key={j} className="text-[10px] px-1.5 py-0.5 rounded bg-muted">
                              {e}
                            </span>
                          ))}
                        </div>
                      )}
                      {chunk.warnings && chunk.warnings.length > 0 && (
                        <div className="text-[10px] text-amber-600 flex items-start gap-1">
                          <AlertTriangle className="size-3 shrink-0" />
                          {chunk.warnings[0]}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Generation info */}
              <div className="text-[10px] text-muted-foreground/60 flex items-center gap-3">
                {enrichment.usage && (
                  <span>
                    {enrichment.usage.total_tokens} tokens • $
                    {enrichment.usage.cost_estimate.toFixed(6)}
                  </span>
                )}
                {enrichment.generated_at && (
                  <span>
                    Generated: {new Date(enrichment.generated_at).toLocaleString()}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* ── Research Gaps (Phase 2.3) ── */}
          {hasGaps && gaps && gaps.gaps && gaps.gaps.length > 0 && (
            <div className="space-y-2 border-t pt-3">
              <h4 className="text-xs font-semibold flex items-center gap-1.5 text-primary">
                <Search className="size-3" />
                Research Gaps
                <span className="font-normal text-muted-foreground">
                  ({gaps.gaps.length})
                </span>
              </h4>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {gaps.gaps.map((gap: ResearchGap, i: number) => (
                  <div key={gap.gap_id || i} className="rounded-lg border p-2.5 text-xs space-y-1.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400 font-medium">
                        {GAP_TYPE_LABELS[gap.gap_type] || gap.gap_type}
                      </span>
                      {gap.confidence > 0 && (
                        <span className={`text-[10px] ${
                          gap.confidence >= 0.8 ? "text-emerald-600" :
                          gap.confidence >= 0.5 ? "text-amber-600" : "text-red-600"
                        }`}>
                          {(gap.confidence * 100).toFixed(0)}% confidence
                        </span>
                      )}
                    </div>
                    <p className="font-medium leading-relaxed">{gap.gap_statement}</p>
                    {gap.missing_information && (
                      <p className="text-muted-foreground">
                        <span className="font-medium">Missing: </span>{gap.missing_information}
                      </p>
                    )}
                    {gap.why_it_matters && (
                      <p className="text-muted-foreground italic">
                        <Lightbulb className="size-3 inline mr-1" />
                        {gap.why_it_matters}
                      </p>
                    )}
                    {gap.based_on_evidence && gap.based_on_evidence.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {gap.based_on_evidence.slice(0, 3).map((ref, j) => (
                          <span key={j} className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                            {ref.slice(0, 40)}
                          </span>
                        ))}
                      </div>
                    )}
                    {gap.warnings && gap.warnings.length > 0 && (
                      <div className="text-[10px] text-amber-600 flex items-start gap-1">
                        <AlertTriangle className="size-3 shrink-0 mt-0.5" />
                        <span>{gap.warnings[0]}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
              {gaps.usage && (
                <div className="text-[10px] text-muted-foreground/60">
                  {gaps.usage.total_tokens} tokens • ${gaps.usage.cost_estimate.toFixed(6)}
                </div>
              )}
            </div>
          )}

          {/* ── Quality Check (Phase 2.3.1) ── */}
          {quality?.available && quality.status === "evaluated" && (
            <div className="space-y-2 border-t pt-3">
              <h4 className="text-xs font-semibold flex items-center gap-1.5 text-primary">
                <ShieldCheck className="size-3" />
                Quality Check
              </h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                <div className="rounded-lg bg-muted p-2 text-center">
                  <div className={`font-semibold ${
                    (quality.overall_quality_score ?? 0) >= 0.7 ? "text-emerald-600" :
                    (quality.overall_quality_score ?? 0) >= 0.5 ? "text-amber-600" : "text-red-600"
                  }`}>
                    {((quality.overall_quality_score ?? 0) * 100).toFixed(0)}%
                  </div>
                  <div className="text-[10px] text-muted-foreground">Overall</div>
                </div>
                <div className="rounded-lg bg-muted p-2 text-center">
                  <div className="font-semibold">
                    {quality.metrics?.invalid_linked_gap_count ?? 0}
                  </div>
                  <div className="text-[10px] text-muted-foreground">Bad Links</div>
                </div>
                <div className="rounded-lg bg-muted p-2 text-center">
                  <div className={`font-semibold ${
                    (quality.metrics?.high_overclaim_risk_count ?? 0) > 0 ? "text-red-600" : "text-emerald-600"
                  }`}>
                    {quality.metrics?.high_overclaim_risk_count ?? 0}
                  </div>
                  <div className="text-[10px] text-muted-foreground">Overclaims</div>
                </div>
                <div className="rounded-lg bg-muted p-2 text-center">
                  <div className={`font-semibold ${
                    (quality.metrics?.safety_ethics_warnings ?? 0) > 0 ? "text-red-600" : "text-emerald-600"
                  }`}>
                    {quality.metrics?.safety_ethics_warnings ?? 0}
                  </div>
                  <div className="text-[10px] text-muted-foreground">Safety</div>
                </div>
              </div>
              {/* Score details */}
              {quality.gap_scores && quality.gap_scores.length > 0 && (
                <details className="text-xs">
                  <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                    Gap scores ({quality.gap_scores.length})
                  </summary>
                  <div className="mt-1 space-y-1 max-h-40 overflow-y-auto">
                    {quality.gap_scores.map((gs, i) => (
                      <div key={gs.gap_id || i} className="flex items-center gap-2 text-[10px]">
                        <span className="w-24 truncate">{gs.gap_id.slice(-16)}</span>
                        <span className={gs.overclaim_risk !== "low" ? "text-red-600 font-medium" : "text-muted-foreground"}>
                          E:{gs.evidence_grounding_score.toFixed(2)} S:{gs.specificity_score.toFixed(2)} N:{gs.novelty_score.toFixed(2)}
                        </span>
                        {gs.overclaim_risk !== "low" && (
                          <span className="text-red-600">⚠{gs.overclaim_risk}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </details>
              )}
              {quality.hypothesis_scores && quality.hypothesis_scores.length > 0 && (
                <details className="text-xs">
                  <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                    Hypothesis scores ({quality.hypothesis_scores.length})
                  </summary>
                  <div className="mt-1 space-y-1 max-h-40 overflow-y-auto">
                    {quality.hypothesis_scores.map((hs, i) => (
                      <div key={hs.hypothesis_id || i} className="flex items-center gap-2 text-[10px]">
                        <span className="w-24 truncate">{hs.hypothesis_id.slice(-16)}</span>
                        <span className={!hs.linked_gap_valid ? "text-red-600 font-medium" : "text-muted-foreground"}>
                          {hs.linked_gap_valid ? "✓" : "✗Link"}
                        </span>
                        <span className="text-muted-foreground">
                          T:{hs.testability_score.toFixed(2)} R:{hs.rationale_grounding_score.toFixed(2)} F:{hs.experiment_feasibility_score.toFixed(2)}
                        </span>
                        {hs.safety_or_ethics_warning && hs.safety_or_ethics_warning.length > 0 && (
                          <span className="text-red-600">🛑</span>
                        )}
                      </div>
                    ))}
                  </div>
                </details>
              )}
              {quality.top_warnings && quality.top_warnings.length > 0 && (
                <div className="text-[10px] space-y-0.5 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-2">
                  {quality.top_warnings.slice(0, 3).map((w, i) => (
                    <div key={i} className="flex items-start gap-1 text-amber-700 dark:text-amber-400">
                      <AlertTriangle className="size-3 mt-0.5 shrink-0" />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Hypotheses (Phase 2.3) ── */}
          {hasHypotheses && hypotheses && hypotheses.hypotheses && hypotheses.hypotheses.length > 0 && (
            <div className="space-y-2 border-t pt-3">
              <h4 className="text-xs font-semibold flex items-center gap-1.5 text-primary">
                <Beaker className="size-3" />
                Hypotheses
                <span className="font-normal text-muted-foreground">
                  ({hypotheses.hypotheses.length})
                </span>
              </h4>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {hypotheses.hypotheses.map((hyp: Hypothesis, i: number) => (
                  <div key={hyp.hypothesis_id || i} className="rounded-lg border p-2.5 text-xs space-y-1.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                        RISK_COLORS[hyp.risk_level] || "bg-slate-100 text-slate-600"
                      }`}>
                        {hyp.risk_level?.toUpperCase() || "?"} risk
                      </span>
                      {hyp.confidence > 0 && (
                        <span className={`text-[10px] ${
                          hyp.confidence >= 0.8 ? "text-emerald-600" :
                          hyp.confidence >= 0.5 ? "text-amber-600" : "text-red-600"
                        }`}>
                          {(hyp.confidence * 100).toFixed(0)}% confidence
                        </span>
                      )}
                      {hyp.linked_gap_id && (
                        <span className="text-[10px] px-1 rounded bg-muted text-muted-foreground">
                          → {hyp.linked_gap_id.slice(-8)}
                        </span>
                      )}
                    </div>
                    <p className="font-medium leading-relaxed">{hyp.hypothesis_statement}</p>
                    {hyp.rationale && (
                      <p className="text-muted-foreground">
                        <span className="font-medium">Rationale: </span>{hyp.rationale}
                      </p>
                    )}
                    {hyp.testable_prediction && (
                      <p className="text-muted-foreground">
                        <span className="font-medium">Prediction: </span>{hyp.testable_prediction}
                      </p>
                    )}
                    {hyp.suggested_experiment && (
                      <p className="text-muted-foreground italic">
                        <FlaskConical className="size-3 inline mr-1" />
                        {hyp.suggested_experiment}
                      </p>
                    )}
                    {hyp.supporting_evidence && hyp.supporting_evidence.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {hyp.supporting_evidence.slice(0, 3).map((ref, j) => (
                          <span key={j} className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                            {ref.slice(0, 50)}
                          </span>
                        ))}
                      </div>
                    )}
                    {hyp.warnings && hyp.warnings.length > 0 && (
                      <div className="text-[10px] text-amber-600 flex items-start gap-1">
                        <AlertTriangle className="size-3 shrink-0 mt-0.5" />
                        <span>{hyp.warnings[0]}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
              {hypotheses.usage && (
                <div className="text-[10px] text-muted-foreground/60">
                  {hypotheses.usage.total_tokens} tokens • ${hypotheses.usage.cost_estimate.toFixed(6)}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
