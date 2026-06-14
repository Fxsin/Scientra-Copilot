"use client";

import { useState, useEffect } from "react";
import { Clock, TrendingUp, TrendingDown, AlertCircle, Loader2, ChevronDown, ChevronRight } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_SCIENTRA_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8710";

interface Phase {
  phase_id: string;
  year_range: string;
  paper_count: number;
  representative_papers: { paper_id: string; title: string; year: number; journal: string; core_finding: string }[];
  dominant_topics: string[];
  dominant_methods: string[];
  dominant_entities: string[];
  core_findings: string[];
  emerging_gaps: { cluster_id: string; title: string; trend: string; paper_count: number }[];
  persistent_gaps: { cluster_id: string; title: string; trend: string; paper_count: number }[];
  emerging_hypotheses: { hypothesis_cluster_id: string; title: string; trend: string }[];
  resolved_or_declining_topics: string[];
  opportunity_signals: { opportunity_id: string; title: string; score: number; trend: string }[];
  phase_summary: string;
}

interface GapEvolution {
  cluster_id: string;
  unified_gap_statement: string;
  gap_type: string;
  paper_count: number;
  first_seen_year: number;
  last_seen_year: number;
  active_year_span: number;
  paper_count_by_phase: Record<string, number>;
  trend: string;
  persistence_score: number;
  closure_signal: string;
  related_opportunities: { opportunity_id: string; title: string; score: number }[];
}

interface HypothesisEvolution {
  hypothesis_cluster_id: string;
  unified_hypothesis_statement: string;
  first_seen_year: number;
  last_seen_year: number;
  trend: string;
  linked_gap_cluster_id: string;
  supporting_papers_by_phase: Record<string, number>;
  validation_status: string;
  risk_trend: string;
}

interface OpportunityEvolution {
  opportunity_id: string;
  title: string;
  opportunity_score: number;
  first_seen_year: number;
  latest_support_year: number;
  trend: string;
  priority_trajectory: string;
  category: string;
}

interface EvolutionData {
  available: boolean;
  message?: string;
  summary?: Record<string, unknown>;
  phases: Phase[];
  gap_evolution: GapEvolution[];
  hypothesis_evolution: HypothesisEvolution[];
  opportunity_evolution: OpportunityEvolution[];
  filtered_gaps?: number;
  filtered_hypotheses?: number;
  filtered_opportunities?: number;
  total_phases?: number;
}

const TREND_COLORS: Record<string, string> = {
  emerging: "bg-green-100 text-green-700",
  persistent: "bg-blue-100 text-blue-700",
  declining: "bg-red-100 text-red-700",
  single_period: "bg-gray-100 text-gray-700",
  growing: "bg-green-100 text-green-700",
  new: "bg-purple-100 text-purple-700",
  unknown: "bg-gray-50 text-gray-500",
};

const CLOSURE_COLORS: Record<string, string> = {
  open: "text-red-600",
  partially_addressed: "text-amber-600",
  possibly_resolved: "text-green-600",
  unknown: "text-gray-400",
};

const VALIDATION_COLORS: Record<string, string> = {
  proposed: "text-gray-500",
  partially_supported: "text-amber-600",
  repeatedly_supported: "text-green-600",
  contested: "text-red-600",
  unknown: "text-gray-400",
};

const PRIORITY_COLORS: Record<string, string> = {
  rising: "text-green-600",
  stable: "text-blue-600",
  falling: "text-red-600",
  unknown: "text-gray-400",
};

export default function ResearchEvolutionPage() {
  const [data, setData] = useState<EvolutionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedPhase, setExpandedPhase] = useState<string | null>(null);
  const [tab, setTab] = useState<"phases" | "gaps" | "hypotheses" | "opportunities">("phases");
  const [trendFilter, setTrendFilter] = useState("");
  const [gapTypeFilter, setGapTypeFilter] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        params.set("limit", "200");
        if (trendFilter) params.set("trend", trendFilter);
        if (gapTypeFilter) params.set("gap_type", gapTypeFilter);
        const qs = params.toString();
        const r = await fetch(`${API_BASE}/knowledge/research-evolution${qs ? "?" + qs : ""}`);
        if (cancelled) return;
        setData(await r.json());
      } catch {
        if (!cancelled) setData(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [trendFilter, gapTypeFilter]);

  const togglePhase = (id: string) => {
    setExpandedPhase(prev => prev === id ? null : id);
  };

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 className="size-6 animate-spin text-gray-400" />
      </div>
    );
  }

  if (!data || !data.available) {
    return (
      <div className="max-w-5xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-2">Research Evolution</h1>
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-6 text-center">
          <AlertCircle className="size-8 text-amber-500 mx-auto mb-2" />
          <p className="text-amber-700 font-medium">Not yet generated</p>
          <p className="text-amber-600 text-sm mt-1">
            {data?.message || "Run Scripts/build_research_evolution.py to generate the research evolution analysis."}
          </p>
        </div>
      </div>
    );
  }

  const summary = data.summary || {};

  return (
    <div className="max-w-6xl mx-auto p-4 sm:p-6">
      <h1 className="text-2xl font-bold mb-1">Research Evolution</h1>
      <p className="text-sm text-gray-500 mb-6">
        {String(summary.year_min || "?")}–{String(summary.year_max || "?")} ·{" "}
        {String(summary.total_papers || 0)} papers ·{" "}
        {String(summary.phase_count || 0)} phases
      </p>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b">
        {(["phases", "gaps", "hypotheses", "opportunities"] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
              tab === t
                ? "bg-white border border-b-white -mb-px text-blue-600"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {t === "phases" && "📅 Phases"}
            {t === "gaps" && "🔍 Gap Evolution"}
            {t === "hypotheses" && "💡 Hypothesis Evolution"}
            {t === "opportunities" && "🎯 Opportunity Evolution"}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <select
          value={trendFilter}
          onChange={e => setTrendFilter(e.target.value)}
          className="px-3 py-1.5 border rounded-lg text-sm bg-white"
        >
          <option value="">All Trends</option>
          <option value="emerging">Emerging</option>
          <option value="persistent">Persistent</option>
          <option value="declining">Declining</option>
          <option value="single_period">Single Period</option>
        </select>
        {tab === "gaps" && (
          <select
            value={gapTypeFilter}
            onChange={e => setGapTypeFilter(e.target.value)}
            className="px-3 py-1.5 border rounded-lg text-sm bg-white"
          >
            <option value="">All Gap Types</option>
            <option value="mechanistic">Mechanistic</option>
            <option value="evidence">Evidence</option>
            <option value="methodological">Methodological</option>
            <option value="contradiction">Contradiction</option>
            <option value="translation">Translation</option>
            <option value="scope">Scope</option>
          </select>
        )}
      </div>

      {/* ── Phases Tab ── */}
      {tab === "phases" && (
        <div className="space-y-4">
          {data.phases.map(ph => {
            const isExpanded = expandedPhase === ph.phase_id;
            return (
              <div key={ph.phase_id} className="border rounded-lg bg-white shadow-sm">
                <button
                  onClick={() => togglePhase(ph.phase_id)}
                  className="w-full text-left px-4 py-3 flex items-center justify-between hover:bg-gray-50 rounded-lg transition-colors"
                >
                  <div className="flex items-center gap-3">
                    {isExpanded ? <ChevronDown className="size-4 text-gray-400" /> : <ChevronRight className="size-4 text-gray-400" />}
                    <span className="font-mono text-sm font-semibold text-blue-700">{ph.phase_id}</span>
                    <span className="text-sm font-medium">{ph.year_range}</span>
                    <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
                      {ph.paper_count} papers
                    </span>
                  </div>
                  <div className="flex gap-2 flex-wrap max-w-md">
                    {ph.dominant_topics.slice(0, 3).map((t, i) => (
                      <span key={i} className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">{t}</span>
                    ))}
                  </div>
                </button>

                {isExpanded && (
                  <div className="px-4 pb-4 border-t pt-3 space-y-3">
                    <p className="text-sm text-gray-600 italic">{ph.phase_summary}</p>

                    {ph.representative_papers.length > 0 && (
                      <div>
                        <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Representative Papers</h4>
                        <div className="space-y-1.5">
                          {ph.representative_papers.map((rp, i) => (
                            <div key={i} className="text-sm">
                              <span className="font-medium">{rp.title}</span>
                              <span className="text-gray-400 ml-2">({rp.year})</span>
                              {rp.core_finding && (
                                <p className="text-xs text-gray-500 mt-0.5 ml-0">{rp.core_finding.slice(0, 150)}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {ph.dominant_topics.length > 0 && (
                        <div>
                          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">Dominant Topics</h4>
                          <div className="flex flex-wrap gap-1">
                            {ph.dominant_topics.map((t, i) => (
                              <span key={i} className="px-2 py-0.5 bg-indigo-50 text-indigo-700 rounded text-xs">{t}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {ph.dominant_methods.length > 0 && (
                        <div>
                          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">Dominant Methods</h4>
                          <div className="flex flex-wrap gap-1">
                            {ph.dominant_methods.slice(0, 5).map((m, i) => (
                              <span key={i} className="px-2 py-0.5 bg-teal-50 text-teal-700 rounded text-xs">{m}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {ph.dominant_entities.length > 0 && (
                        <div>
                          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">Key Entities</h4>
                          <div className="flex flex-wrap gap-1">
                            {ph.dominant_entities.slice(0, 5).map((e, i) => (
                              <span key={i} className="px-2 py-0.5 bg-amber-50 text-amber-700 rounded text-xs">{e}</span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {(ph.emerging_gaps.length > 0 || ph.persistent_gaps.length > 0) && (
                      <div>
                        <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Research Gaps</h4>
                        {ph.emerging_gaps.length > 0 && (
                          <div className="mb-2">
                            <span className="text-xs font-medium text-green-600">Emerging:</span>
                            {ph.emerging_gaps.map((g, i) => (
                              <div key={i} className="text-xs text-gray-600 ml-2 mt-0.5">• {g.title.slice(0, 120)}</div>
                            ))}
                          </div>
                        )}
                        {ph.persistent_gaps.length > 0 && (
                          <div>
                            <span className="text-xs font-medium text-blue-600">Persistent:</span>
                            {ph.persistent_gaps.map((g, i) => (
                              <div key={i} className="text-xs text-gray-600 ml-2 mt-0.5">• {g.title.slice(0, 120)}</div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Gap Evolution Tab ── */}
      {tab === "gaps" && (
        <div className="space-y-3">
          {data.gap_evolution.length === 0 && (
            <p className="text-gray-500 text-center py-8">No gap evolution data matching filters.</p>
          )}
          {data.gap_evolution.map(g => (
            <div key={g.cluster_id} className="border rounded-lg bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 line-clamp-2">{g.unified_gap_statement}</p>
                  <div className="flex flex-wrap gap-2 mt-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${TREND_COLORS[g.trend] || "bg-gray-100"}`}>
                      {g.trend}
                    </span>
                    <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">{g.gap_type}</span>
                    <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                      <Clock className="size-3 inline mr-1" />
                      {g.first_seen_year}–{g.last_seen_year} ({g.active_year_span}y)
                    </span>
                    <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                      {g.paper_count} papers
                    </span>
                    <span className={`text-xs font-medium ${CLOSURE_COLORS[g.closure_signal] || "text-gray-400"}`}>
                      {g.closure_signal?.replace(/_/g, " ")}
                    </span>
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className="text-xs text-gray-400">Persistence</div>
                  <div className="text-sm font-semibold text-gray-700">{g.persistence_score?.toFixed(2)}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Hypothesis Evolution Tab ── */}
      {tab === "hypotheses" && (
        <div className="space-y-3">
          {data.hypothesis_evolution.length === 0 && (
            <p className="text-gray-500 text-center py-8">No hypothesis evolution data matching filters.</p>
          )}
          {data.hypothesis_evolution.map(h => (
            <div key={h.hypothesis_cluster_id} className="border rounded-lg bg-white p-4 shadow-sm">
              <p className="text-sm font-medium text-gray-800 line-clamp-2">{h.unified_hypothesis_statement}</p>
              <div className="flex flex-wrap gap-2 mt-2">
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${TREND_COLORS[h.trend] || "bg-gray-100"}`}>
                  {h.trend}
                </span>
                <span className={`text-xs font-medium ${VALIDATION_COLORS[h.validation_status] || "text-gray-400"}`}>
                  {h.validation_status?.replace(/_/g, " ")}
                </span>
                <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                  <Clock className="size-3 inline mr-1" />
                  {h.first_seen_year}–{h.last_seen_year}
                </span>
                <span className={`text-xs font-medium ${PRIORITY_COLORS[h.risk_trend] || "text-gray-400"}`}>
                  Risk: {h.risk_trend}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Opportunity Evolution Tab ── */}
      {tab === "opportunities" && (
        <div className="space-y-3">
          {data.opportunity_evolution.length === 0 && (
            <p className="text-gray-500 text-center py-8">No opportunity evolution data matching filters.</p>
          )}
          {data.opportunity_evolution.map(o => (
            <div key={o.opportunity_id} className="border rounded-lg bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 line-clamp-2">{o.title}</p>
                  <div className="flex flex-wrap gap-2 mt-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${TREND_COLORS[o.trend] || "bg-gray-100"}`}>
                      {o.trend}
                    </span>
                    <span className={`text-xs font-medium ${PRIORITY_COLORS[o.priority_trajectory] || "text-gray-400"}`}>
                      Priority: {o.priority_trajectory}
                    </span>
                    <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                      <Clock className="size-3 inline mr-1" />
                      {o.first_seen_year}–{o.latest_support_year}
                    </span>
                    <span className="px-2 py-0.5 bg-purple-50 text-purple-700 rounded text-xs">
                      {o.category?.replace(/_/g, " ")}
                    </span>
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className="text-xs text-gray-400">Score</div>
                  <div className="text-sm font-semibold text-gray-700">{o.opportunity_score?.toFixed(3)}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Footer: counts */}
      <div className="mt-8 text-xs text-gray-400 text-center">
        {data.filtered_gaps != null && `${data.filtered_gaps} gaps · `}
        {data.filtered_hypotheses != null && `${data.filtered_hypotheses} hypotheses · `}
        {data.filtered_opportunities != null && `${data.filtered_opportunities} opportunities · `}
        {data.total_phases != null && `${data.total_phases} phases`}
      </div>
    </div>
  );
}
