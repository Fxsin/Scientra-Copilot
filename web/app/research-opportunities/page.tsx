"use client";

import { useState, useEffect } from "react";
import { Target, TrendingUp, ChevronDown, ChevronRight, Loader2, Search, Filter, Shield, AlertTriangle, CheckCircle, XCircle, HelpCircle, Zap } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_SCIENTRA_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8710";

interface Opportunity {
  opportunity_id: string;
  linked_gap_cluster_id: string;
  title: string;
  opportunity_statement: string;
  why_it_matters: string;
  supporting_paper_count: number;
  supporting_gap_count: number;
  supporting_hypothesis_count: number;
  evidence_support_level: string;
  testability: string;
  risk_level: string;
  novelty_score: number;
  feasibility_score: number;
  evidence_score: number;
  impact_score: number;
  opportunity_score: number;
  category: string;
  representative_gap: string;
  representative_hypothesis: string;
  suggested_next_steps: string[];
  member_papers: string[];
}

interface Review {
  opportunity_id: string;
  rank: number;
  title: string;
  opportunity_score: number;
  review_status: string;
  scientific_importance: string;
  evidence_strength_assessment: string;
  technical_feasibility: string;
  novelty_assessment: string;
  major_risks: string[];
  key_missing_evidence: string[];
  recommended_next_steps: string[];
  possible_experimental_routes: string[];
  expected_impact: string;
  review_confidence: number;
  review_warnings: string[];
  usage?: Record<string, unknown>;
}

interface OppData {
  available: boolean;
  message?: string;
  summary?: Record<string, unknown>;
  opportunities: Opportunity[];
  filtered_count?: number;
  total_opportunities?: number;
}

interface ReviewData {
  available: boolean;
  message?: string;
  summary?: Record<string, unknown>;
  reviews: Review[];
  filtered_count?: number;
  total_reviews?: number;
}

const RISK_COLORS: Record<string, string> = { low: "text-emerald-600", medium: "text-amber-600", high: "text-red-600" };
const CAT_COLORS: Record<string, string> = {
  high_confidence_next_step: "bg-emerald-100 text-emerald-700",
  high_impact_open_question: "bg-purple-100 text-purple-700",
  underexplored_mechanism: "bg-blue-100 text-blue-700",
  translation_gap: "bg-amber-100 text-amber-700",
  contradiction_to_resolve: "bg-red-100 text-red-700",
  method_gap: "bg-slate-100 text-slate-700",
  broad_scope_gap: "bg-cyan-100 text-cyan-700",
  speculative_hypothesis: "bg-pink-100 text-pink-700",
};

const REVIEW_STATUS_COLORS: Record<string, string> = {
  accept: "bg-emerald-100 text-emerald-700",
  revise: "bg-amber-100 text-amber-700",
  reject: "bg-red-100 text-red-700",
  insufficient_data: "bg-gray-100 text-gray-600",
  error: "bg-red-50 text-red-500",
};

const REVIEW_STATUS_ICONS: Record<string, React.ReactNode> = {
  accept: <CheckCircle className="size-3.5 text-emerald-600" />,
  revise: <AlertTriangle className="size-3.5 text-amber-600" />,
  reject: <XCircle className="size-3.5 text-red-600" />,
  insufficient_data: <HelpCircle className="size-3.5 text-gray-400" />,
};

export default function ResearchOpportunitiesPage() {
  const [data, setData] = useState<OppData | null>(null);
  const [reviewData, setReviewData] = useState<ReviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [category, setCategory] = useState("");
  const [minScore, setMinScore] = useState(0);

  useEffect(() => {
    let c = false;
    async function load() {
      setLoading(true);
      try {
        const p = new URLSearchParams(); p.set("limit", "100");
        if (category) p.set("category", category);
        if (minScore > 0) p.set("min_score", String(minScore));
        const qs = p.toString();
        const [oppR, revR] = await Promise.all([
          fetch(`${API_BASE}/knowledge/research-opportunities${qs ? "?" + qs : ""}`),
          fetch(`${API_BASE}/knowledge/research-opportunity-reviews?limit=50`),
        ]);
        if (c) return;
        setData(await oppR.json());
        setReviewData(await revR.json());
      } catch { if (!c) { setData(null); setReviewData(null); } }
      finally { if (!c) setLoading(false); }
    }
    load(); return () => { c = true; };
  }, [category, minScore]);

  const toggle = (id: string) => setExpanded(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="size-6 animate-spin" /></div>;

  if (!data?.available) {
    return (
      <div className="max-w-4xl mx-auto py-12 px-4">
        <h1 className="text-2xl font-bold flex items-center gap-2 mb-4"><Target className="size-5" />Research Opportunities</h1>
        <div className="rounded-xl border bg-card p-8 text-center space-y-2">
          <Search className="size-8 mx-auto text-muted-foreground" />
          <p className="text-muted-foreground">{data?.message || "Not yet generated."}</p>
          <p className="text-xs text-muted-foreground/60">Run: python Scripts/rank_research_opportunities.py</p>
        </div>
      </div>
    );
  }

  const summary = data.summary || {};
  const opps = data.opportunities || [];
  const reviews = reviewData?.reviews || [];
  const reviewSummary = reviewData?.summary || {};
  const reviewMap = new Map(reviews.map(r => [r.opportunity_id, r]));

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2"><Target className="size-5" />Research Opportunities</h1>
        <p className="text-sm text-muted-foreground">{data.total_opportunities} opportunities ranked by evidence, feasibility, novelty, and impact</p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="rounded-xl border bg-card p-3 text-center"><div className="text-xl font-bold">{data.total_opportunities}</div><div className="text-[10px] text-muted-foreground">Total</div></div>
        <div className="rounded-xl border bg-card p-3 text-center"><div className="text-xl font-bold text-emerald-600">{summary.high_confidence_next_step as number || 0}</div><div className="text-[10px] text-muted-foreground">High Conf</div></div>
        <div className="rounded-xl border bg-card p-3 text-center"><div className="text-xl font-bold text-purple-600">{summary.high_impact_open_question as number || 0}</div><div className="text-[10px] text-muted-foreground">High Impact</div></div>
        <div className="rounded-xl border bg-card p-3 text-center"><div className="text-xl font-bold text-blue-600">{summary.underexplored_mechanism as number || 0}</div><div className="text-[10px] text-muted-foreground">Mechanism</div></div>
        <div className="rounded-xl border bg-card p-3 text-center"><div className="text-xl font-bold">{(summary.average_opportunity_score as number || 0).toFixed(2)}</div><div className="text-[10px] text-muted-foreground">Avg Score</div></div>
      </div>

      {/* ── Expert Review Section ── */}
      {reviewData?.available ? (
        <div className="rounded-xl border bg-emerald-50/30 p-4 space-y-2">
          <div className="flex items-center gap-2">
            <Shield className="size-4 text-emerald-600" />
            <span className="text-sm font-semibold text-emerald-800">AI Expert Review Available</span>
          </div>
          <div className="flex flex-wrap gap-3 text-xs">
            <span className="px-2 py-0.5 bg-white rounded-full border">
              <CheckCircle className="size-3 inline text-emerald-600 mr-1" />
              Accept: {reviewSummary.accept_count as number || 0}
            </span>
            <span className="px-2 py-0.5 bg-white rounded-full border">
              <AlertTriangle className="size-3 inline text-amber-600 mr-1" />
              Revise: {reviewSummary.revise_count as number || 0}
            </span>
            <span className="px-2 py-0.5 bg-white rounded-full border">
              <XCircle className="size-3 inline text-red-600 mr-1" />
              Reject: {reviewSummary.reject_count as number || 0}
            </span>
            <span className="px-2 py-0.5 bg-white rounded-full border">
              <HelpCircle className="size-3 inline text-gray-400 mr-1" />
              Insufficient: {reviewSummary.insufficient_data_count as number || 0}
            </span>
            <span className="px-2 py-0.5 bg-white rounded-full border text-gray-500">
              Cost: ${(reviewSummary.total_cost_usd as number || 0).toFixed(4)}
            </span>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border bg-amber-50/30 p-3 text-center text-xs text-amber-700">
          <Zap className="size-3.5 inline mr-1" />
          Expert review not generated yet. Run: python Scripts/review_research_opportunities.py
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap text-xs">
        <Filter className="size-3 text-muted-foreground" />
        <select value={category} onChange={e => setCategory(e.target.value)} className="rounded-lg border px-2 py-1 bg-background">
          <option value="">All categories</option>
          {summary.category_distribution && Object.keys(summary.category_distribution as Record<string, number>).map(c => (
            <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
          ))}
        </select>
        <select value={minScore} onChange={e => setMinScore(Number(e.target.value))} className="rounded-lg border px-2 py-1 bg-background">
          <option value={0}>Any score</option>
          <option value={0.5}>≥0.50</option><option value={0.6}>≥0.60</option><option value={0.7}>≥0.70</option><option value={0.8}>≥0.80</option>
        </select>
        <span className="text-muted-foreground">{opps.length} shown</span>
      </div>

      {/* Opportunities list */}
      <div className="space-y-3">
        {opps.map(o => {
          const review = reviewMap.get(o.opportunity_id);
          return (
          <div key={o.opportunity_id} className="rounded-xl border bg-card overflow-hidden">
            <button onClick={() => toggle(o.opportunity_id)} className="w-full text-left p-4 flex items-start gap-3 hover:bg-muted/30">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${CAT_COLORS[o.category] || "bg-slate-100"}`}>{o.category.replace(/_/g, " ")}</span>
                  <span className={`text-[10px] font-medium ${RISK_COLORS[o.risk_level] || ""}`}>{o.risk_level} risk</span>
                  <span className="text-[10px] text-muted-foreground">{o.supporting_paper_count}p • {o.evidence_support_level}</span>
                  <span className="text-[10px] text-muted-foreground">{o.testability} testability</span>
                  {review && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${REVIEW_STATUS_COLORS[review.review_status] || "bg-gray-100"}`}>
                      {REVIEW_STATUS_ICONS[review.review_status]} {review.review_status.replace(/_/g, " ")}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-bold text-primary">{o.opportunity_score.toFixed(3)}</span>
                  <span className="text-[10px] text-muted-foreground">
                    E:{o.evidence_score.toFixed(2)} F:{o.feasibility_score.toFixed(2)} N:{o.novelty_score.toFixed(2)} I:{o.impact_score.toFixed(2)}
                  </span>
                  {review && (
                    <span className="text-[10px] text-muted-foreground">| Review conf: {review.review_confidence.toFixed(2)}</span>
                  )}
                </div>
                <p className="text-sm">{o.title}</p>
              </div>
              {expanded.has(o.opportunity_id) ? <ChevronDown className="size-4 shrink-0 mt-0.5" /> : <ChevronRight className="size-4 shrink-0 mt-0.5" />}
            </button>
            {expanded.has(o.opportunity_id) && (
              <div className="px-4 pb-4 space-y-2 border-t pt-3 text-xs">
                {/* ── Expert Review Detail ── */}
                {review && (
                  <div className="rounded-lg bg-slate-50 p-3 space-y-2 border border-slate-200">
                    <div className="flex items-center gap-2">
                      <Shield className="size-3.5 text-indigo-600" />
                      <span className="font-semibold text-indigo-800">AI Expert Review</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${REVIEW_STATUS_COLORS[review.review_status] || ""}`}>
                        {review.review_status.replace(/_/g, " ").toUpperCase()}
                      </span>
                      <span className="text-[10px] text-muted-foreground">confidence: {review.review_confidence.toFixed(2)}</span>
                    </div>
                    {review.scientific_importance && (
                      <div><span className="font-medium text-indigo-700">Scientific Importance: </span><span className="text-muted-foreground">{review.scientific_importance}</span></div>
                    )}
                    {review.evidence_strength_assessment && (
                      <div><span className="font-medium text-indigo-700">Evidence Strength: </span><span className="text-muted-foreground">{review.evidence_strength_assessment}</span></div>
                    )}
                    {review.technical_feasibility && (
                      <div><span className="font-medium text-indigo-700">Technical Feasibility: </span><span className="text-muted-foreground">{review.technical_feasibility}</span></div>
                    )}
                    {review.novelty_assessment && (
                      <div><span className="font-medium text-indigo-700">Novelty: </span><span className="text-muted-foreground">{review.novelty_assessment}</span></div>
                    )}
                    {review.expected_impact && (
                      <div><span className="font-medium text-indigo-700">Expected Impact: </span><span className="text-muted-foreground">{review.expected_impact}</span></div>
                    )}
                    {review.major_risks.length > 0 && (
                      <div>
                        <span className="font-medium text-red-700">Major Risks:</span>
                        <ul className="list-disc list-inside text-muted-foreground ml-1">
                          {review.major_risks.map((r, i) => <li key={i}>{r}</li>)}
                        </ul>
                      </div>
                    )}
                    {review.key_missing_evidence.length > 0 && (
                      <div>
                        <span className="font-medium text-amber-700">Missing Evidence:</span>
                        <ul className="list-disc list-inside text-muted-foreground ml-1">
                          {review.key_missing_evidence.map((e, i) => <li key={i}>{e}</li>)}
                        </ul>
                      </div>
                    )}
                    {review.recommended_next_steps.length > 0 && (
                      <div>
                        <span className="font-medium text-emerald-700">Recommended Next Steps:</span>
                        <ul className="list-disc list-inside text-muted-foreground ml-1">
                          {review.recommended_next_steps.map((s, i) => <li key={i}>{s}</li>)}
                        </ul>
                      </div>
                    )}
                    {review.possible_experimental_routes.length > 0 && (
                      <div>
                        <span className="font-medium text-blue-700">Experimental Routes:</span>
                        <ul className="list-disc list-inside text-muted-foreground ml-1">
                          {review.possible_experimental_routes.map((r, i) => <li key={i}>{r}</li>)}
                        </ul>
                      </div>
                    )}
                    {review.review_warnings.length > 0 && (
                      <div className="text-amber-600 text-[10px]">
                        {review.review_warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
                      </div>
                    )}
                  </div>
                )}
                {o.why_it_matters && <div><span className="font-medium">Why it matters: </span><span className="text-muted-foreground">{o.why_it_matters}</span></div>}
                {o.representative_hypothesis && <div><span className="font-medium">Hypothesis: </span><span className="text-muted-foreground">{o.representative_hypothesis}</span></div>}
                {o.suggested_next_steps.length > 0 && <div><span className="font-medium">Next Steps:</span><ul className="list-disc list-inside text-muted-foreground">{o.suggested_next_steps.map((s,i)=><li key={i}>{s}</li>)}</ul></div>}
                <details><summary className="cursor-pointer text-muted-foreground">Papers ({o.supporting_paper_count})</summary><div className="mt-1 space-y-0.5 max-h-24 overflow-y-auto">{o.member_papers.map((p,i)=><div key={i} className="text-[10px] truncate">{p.slice(0,80)}</div>)}</div></details>
              </div>
            )}
          </div>
        )})}
      </div>
    </div>
  );
}
