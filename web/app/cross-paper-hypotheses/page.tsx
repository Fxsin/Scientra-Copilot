"use client";

import { useState, useEffect } from "react";
import {
  Beaker, Layers, FlaskConical, ChevronDown, ChevronRight,
  Loader2, AlertTriangle, Search,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_SCIENTRA_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8710";

interface HypCluster {
  hypothesis_cluster_id: string;
  linked_gap_cluster_id: string;
  unified_hypothesis_statement: string;
  representative_hypothesis_id: string;
  representative_paper_id: string;
  member_hypothesis_ids: string[];
  paper_ids: string[];
  paper_count: number;
  gap_count: number;
  supporting_gap_ids: string[];
  supporting_evidence: string[];
  testable_predictions: string[];
  suggested_experiments: string[];
  risk_level_distribution: Record<string, number>;
  confidence_mean: number;
  confidence_min: number;
  confidence_max: number;
  support_level: string;
  quality_score_mean: number;
  overclaim_risk_count: number;
  average_similarity: number;
  warnings: string[];
}

interface HypFusionData {
  available: boolean;
  message?: string;
  summary?: Record<string, unknown>;
  quality?: Record<string, unknown>;
  hypothesis_clusters: HypCluster[];
  filtered_count?: number;
  total_clusters?: number;
}

export default function CrossPaperHypothesesPage() {
  const [data, setData] = useState<HypFusionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [minPapers, setMinPapers] = useState(1);

  useEffect(() => {
    let c = false;
    async function load() {
      setLoading(true);
      try {
        const p = new URLSearchParams();
        if (minPapers > 1) p.set("min_paper_count", String(minPapers));
        p.set("limit", "200");
        const qs = p.toString();
        const r = await fetch(`${API_BASE}/knowledge/cross-paper-hypotheses${qs ? "?" + qs : ""}`);
        if (c) return;
        setData(await r.json());
      } catch { if (!c) setData(null); }
      finally { if (!c) setLoading(false); }
    }
    load(); return () => { c = true; };
  }, [minPapers]);

  const toggle = (id: string) => setExpanded(p => {
    const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n;
  });

  if (loading) return <div className="flex justify-center py-20"><Loader2 className="size-6 animate-spin text-muted-foreground" /></div>;

  if (!data?.available) {
    return (
      <div className="max-w-4xl mx-auto py-12 px-4">
        <h1 className="text-2xl font-bold flex items-center gap-2 mb-4"><Beaker className="size-5" />Cross-Paper Hypotheses</h1>
        <div className="rounded-xl border bg-card p-8 text-center space-y-2">
          <Search className="size-8 mx-auto text-muted-foreground" />
          <p className="text-muted-foreground">{data?.message || "Not yet generated."}</p>
          <p className="text-xs text-muted-foreground/60">Run: python Scripts/fuse_cross_paper_hypotheses.py</p>
        </div>
      </div>
    );
  }

  const clusters = data.hypothesis_clusters || [];
  const quality = data.quality || {};
  const summary = data.summary || {};

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2"><Beaker className="size-5" />Cross-Paper Hypotheses</h1>
        <p className="text-sm text-muted-foreground">
          {summary.total_hypothesis_clusters as number || 0} clusters from {summary.total_hypotheses as number || 0} hypotheses across 54 papers
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="rounded-xl border bg-card p-4 text-center"><div className="text-2xl font-bold">{summary.total_hypothesis_clusters as number || 0}</div><div className="text-xs text-muted-foreground">Clusters</div></div>
        <div className="rounded-xl border bg-card p-4 text-center"><div className="text-2xl font-bold text-emerald-600">{summary.strong_multi_paper_hypothesis_clusters as number || 0}</div><div className="text-xs text-muted-foreground">Strong (3+)</div></div>
        <div className="rounded-xl border bg-card p-4 text-center"><div className="text-2xl font-bold text-blue-600">{summary.multi_paper_hypothesis_clusters as number || 0}</div><div className="text-xs text-muted-foreground">Multi-Paper</div></div>
        <div className="rounded-xl border bg-card p-4 text-center">
          <div className={`text-2xl font-bold ${(quality.recommendation as string) === "accept" ? "text-emerald-600" : "text-amber-600"}`}>
            {(quality.recommendation as string || "?").toUpperCase()}
          </div>
          <div className="text-xs text-muted-foreground">Quality</div>
        </div>
      </div>

      <select value={minPapers} onChange={e => setMinPapers(Number(e.target.value))} className="text-xs rounded-lg border px-3 py-1.5 bg-background">
        <option value={1}>All</option><option value={2}>2+ papers</option><option value={3}>3+ papers</option><option value={5}>5+ papers</option>
      </select>

      <div className="space-y-3">
        {clusters.map(c => (
          <div key={c.hypothesis_cluster_id} className="rounded-xl border bg-card overflow-hidden">
            <button onClick={() => toggle(c.hypothesis_cluster_id)} className="w-full text-left p-4 flex items-start gap-3 hover:bg-muted/30">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${
                    c.support_level === "strong_multi_paper" ? "bg-emerald-100 text-emerald-700" :
                    c.support_level === "multi_paper" ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-600"
                  }`}>{c.support_level.replace(/_/g, " ")}</span>
                  <span className="text-[10px] text-muted-foreground">{c.paper_count}p • {c.gap_count} gaps</span>
                  <span className="text-[10px] px-1 rounded bg-muted">
                    L:{c.risk_level_distribution?.low||0} M:{c.risk_level_distribution?.medium||0} H:{c.risk_level_distribution?.high||0}
                  </span>
                  <span className="text-[10px] text-muted-foreground">c:{c.confidence_mean.toFixed(2)}</span>
                </div>
                <p className="text-sm">{c.unified_hypothesis_statement}</p>
              </div>
              {expanded.has(c.hypothesis_cluster_id) ? <ChevronDown className="size-4 shrink-0 mt-0.5" /> : <ChevronRight className="size-4 shrink-0 mt-0.5" />}
            </button>
            {expanded.has(c.hypothesis_cluster_id) && (
              <div className="px-4 pb-4 space-y-2 border-t pt-3 text-xs">
                {c.testable_predictions.length > 0 && <div><span className="font-medium">Predictions:</span><ul className="list-disc list-inside text-muted-foreground">{c.testable_predictions.slice(0,3).map((p,i)=><li key={i}>{p}</li>)}</ul></div>}
                {c.suggested_experiments.length > 0 && <div><span className="font-medium flex items-center gap-1"><FlaskConical className="size-3"/>Experiments:</span><ul className="list-disc list-inside text-muted-foreground">{c.suggested_experiments.slice(0,3).map((e,i)=><li key={i}>{e}</li>)}</ul></div>}
                <div className="flex gap-4 text-muted-foreground"><span>Quality: {c.quality_score_mean.toFixed(2)}</span><span>Sim: {(c.average_similarity||0).toFixed(3)}</span></div>
                <details><summary className="cursor-pointer text-muted-foreground">Papers ({c.paper_count})</summary><div className="mt-1 space-y-0.5 max-h-24 overflow-y-auto">{c.paper_ids.map((p,i)=><div key={i} className="text-[10px] truncate">{p.slice(0,80)}</div>)}</div></details>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
