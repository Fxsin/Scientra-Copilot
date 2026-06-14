"use client";

import { useState, useEffect } from "react";
import {
  Brain, Layers, Hash, Gauge, AlertTriangle, Check,
  ChevronDown, ChevronRight, Loader2, Search,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_SCIENTRA_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8710";

interface GapCluster {
  cluster_id: string;
  unified_gap_statement: string;
  gap_type: string;
  paper_ids: string[];
  paper_count: number;
  support_level: string;
  representative_gap: string;
  keywords: string[];
  why_it_matters_merged: string;
  confidence_mean: number;
  confidence_min: number;
  confidence_max: number;
}

interface CrossPaperGapsData {
  available: boolean;
  message?: string;
  summary?: {
    total_gaps: number;
    total_papers: number;
    total_clusters: number;
    single_paper_clusters: number;
    multi_paper_clusters: number;
    strong_multi_paper_clusters: number;
    gap_type_distribution: Record<string, number>;
  };
  clusters: GapCluster[];
  filtered_count?: number;
  total_clusters?: number;
}

const SUPPORT_COLORS: Record<string, string> = {
  strong_multi_paper: "bg-emerald-100 text-emerald-700 border-emerald-200",
  multi_paper: "bg-blue-100 text-blue-700 border-blue-200",
  single_paper: "bg-slate-100 text-slate-600 border-slate-200",
};

export default function CrossPaperGapsPage() {
  const [data, setData] = useState<CrossPaperGapsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [minPapers, setMinPapers] = useState(1);
  const [gapTypeFilter, setGapTypeFilter] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        if (minPapers > 1) params.set("min_paper_count", String(minPapers));
        if (gapTypeFilter) params.set("gap_type", gapTypeFilter);
        params.set("limit", "200");
        const qs = params.toString();
        const res = await fetch(`${API_BASE}/knowledge/cross-paper-gaps${qs ? "?" + qs : ""}`);
        if (cancelled) return;
        const json = await res.json();
        setData(json);
      } catch {
        if (!cancelled) setData(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [minPapers, gapTypeFilter]);

  const toggle = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!data?.available) {
    return (
      <div className="max-w-4xl mx-auto py-12 px-4 space-y-6">
        <div className="flex items-center gap-2">
          <Brain className="size-5 text-slate-500" />
          <h1 className="text-2xl font-bold">Cross-Paper Research Gaps</h1>
        </div>
        <div className="rounded-xl border bg-card p-8 text-center space-y-2">
          <Search className="size-8 mx-auto text-muted-foreground" />
          <p className="text-muted-foreground">
            {data?.message || "Cross-paper gap fusion not yet generated."}
          </p>
          <p className="text-xs text-muted-foreground/60">
            Run: python Scripts/fuse_cross_paper_gaps.py
          </p>
        </div>
      </div>
    );
  }

  const summary = data.summary;
  const clusters = data.clusters || [];

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Layers className="size-5 text-slate-500" />
          <h1 className="text-2xl font-bold tracking-tight">Cross-Paper Research Gaps</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Unified research gaps fused across {summary?.total_papers || 0} papers
        </p>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-xl border bg-card p-4 text-center">
            <div className="text-2xl font-bold">{summary.total_gaps}</div>
            <div className="text-xs text-muted-foreground">Total Gaps</div>
          </div>
          <div className="rounded-xl border bg-card p-4 text-center">
            <div className="text-2xl font-bold">{summary.total_clusters}</div>
            <div className="text-xs text-muted-foreground">Clusters</div>
          </div>
          <div className="rounded-xl border bg-card p-4 text-center">
            <div className="text-2xl font-bold text-emerald-600">
              {summary.strong_multi_paper_clusters}
            </div>
            <div className="text-xs text-muted-foreground">Strong (3+ papers)</div>
          </div>
          <div className="rounded-xl border bg-card p-4 text-center">
            <div className="text-2xl font-bold text-blue-600">
              {summary.multi_paper_clusters}
            </div>
            <div className="text-xs text-muted-foreground">Multi-Paper</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={minPapers}
          onChange={e => setMinPapers(Number(e.target.value))}
          className="text-xs rounded-lg border px-3 py-1.5 bg-background"
        >
          <option value={1}>All papers</option>
          <option value={2}>2+ papers</option>
          <option value={3}>3+ papers</option>
          <option value={5}>5+ papers</option>
        </select>
        <select
          value={gapTypeFilter}
          onChange={e => setGapTypeFilter(e.target.value)}
          className="text-xs rounded-lg border px-3 py-1.5 bg-background"
        >
          <option value="">All types</option>
          {summary?.gap_type_distribution && Object.keys(summary.gap_type_distribution).map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <span className="text-xs text-muted-foreground">
          Showing {clusters.length} cluster{clusters.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Clusters */}
      <div className="space-y-3">
        {clusters.map(cluster => (
          <div key={cluster.cluster_id} className="rounded-xl border bg-card overflow-hidden">
            <button
              onClick={() => toggle(cluster.cluster_id)}
              className="w-full text-left p-4 flex items-start gap-3 hover:bg-muted/30 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${
                    SUPPORT_COLORS[cluster.support_level] || SUPPORT_COLORS.single_paper
                  }`}>
                    {cluster.support_level.replace(/_/g, " ")}
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                    {cluster.gap_type}
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    {cluster.paper_count} paper{cluster.paper_count !== 1 ? "s" : ""}
                  </span>
                  <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
                    <Gauge className="size-3" />
                    {cluster.confidence_mean.toFixed(2)}
                  </span>
                </div>
                <p className="text-sm leading-relaxed">{cluster.unified_gap_statement}</p>
              </div>
              {expanded.has(cluster.cluster_id) ? (
                <ChevronDown className="size-4 text-muted-foreground shrink-0 mt-0.5" />
              ) : (
                <ChevronRight className="size-4 text-muted-foreground shrink-0 mt-0.5" />
              )}
            </button>

            {expanded.has(cluster.cluster_id) && (
              <div className="px-4 pb-4 space-y-3 border-t pt-3">
                {/* Why it matters */}
                {cluster.why_it_matters_merged && (
                  <div className="text-xs text-muted-foreground">
                    <span className="font-medium">Why it matters: </span>
                    {cluster.why_it_matters_merged}
                  </div>
                )}

                {/* Keywords */}
                {cluster.keywords && cluster.keywords.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {cluster.keywords.slice(0, 12).map((kw, i) => (
                      <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                        {kw}
                      </span>
                    ))}
                  </div>
                )}

                {/* Confidence range */}
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>Confidence: {cluster.confidence_min.toFixed(2)} – {cluster.confidence_max.toFixed(2)}</span>
                  <span>Mean: {cluster.confidence_mean.toFixed(2)}</span>
                </div>

                {/* Paper IDs */}
                <details className="text-xs">
                  <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                    Papers ({cluster.paper_count})
                  </summary>
                  <div className="mt-1 space-y-0.5 max-h-32 overflow-y-auto">
                    {cluster.paper_ids.map((pid, i) => (
                      <div key={i} className="text-[10px] text-muted-foreground truncate">
                        {pid.slice(0, 80)}
                      </div>
                    ))}
                  </div>
                </details>
              </div>
            )}
          </div>
        ))}
      </div>

      {clusters.length === 0 && (
        <div className="text-center py-12 text-muted-foreground text-sm">
          No clusters match the current filters.
        </div>
      )}
    </div>
  );
}
