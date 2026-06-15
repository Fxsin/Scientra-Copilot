"use client";

import { useEffect, useState } from "react";
import {
  BarChart3,
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Zap,
  Database,
  GitBranch,
  FileSearch,
  Cpu,
  Shield,
} from "lucide-react";

interface BenchmarkStatus {
  available: boolean;
  message?: string;
  last_run?: string | null;
  run_id?: string;
  total_tasks?: number;
  total_passed?: number;
  total_warnings?: number;
  total_failed?: number;
}

interface MetricItem {
  label: string;
  duration_ms: number;
  success: boolean;
  error?: string | null;
  warnings?: string[];
  metadata?: Record<string, unknown>;
}

interface QueryItem {
  query: string;
  total_duration_ms: number;
  keyword_duration_ms: number;
  vector_duration_ms: number;
  graph_duration_ms: number;
  merge_duration_ms: number;
  hit_count: number;
  warnings?: string[];
}

interface BenchmarkData {
  available: boolean;
  category?: string;
  passed?: number;
  warning_count?: number;
  failed?: number;
  total_duration_ms?: number;
  metrics?: MetricItem[];
  queries?: QueryItem[];
  warnings?: { module: string; message: string; severity: string }[];
}

interface RecommendationsData {
  available: boolean;
  cache_recommendations?: { category: string; target: string; recommendation: string; priority: string; evidence?: Record<string, unknown> }[];
  incremental_update_recommendations?: { category: string; target: string; recommendation: string; priority: string; evidence?: Record<string, unknown> }[];
  p7_readiness_warnings?: string[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8710";

async function fetchBenchmark<T>(endpoint: string): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`);
  if (!res.ok) {
    return { available: false } as T;
  }
  return res.json();
}

function StatusBadge({ success, warning }: { success: boolean; warning?: boolean }) {
  if (!success) {
    return <span className="inline-flex items-center gap-1 rounded-full bg-red-500/10 px-2 py-0.5 text-xs font-medium text-red-500"><XCircle className="size-3" /> Failed</span>;
  }
  if (warning) {
    return <span className="inline-flex items-center gap-1 rounded-full bg-yellow-500/10 px-2 py-0.5 text-xs font-medium text-yellow-600"><AlertTriangle className="size-3" /> Warning</span>;
  }
  return <span className="inline-flex items-center gap-1 rounded-full bg-green-500/10 px-2 py-0.5 text-xs font-medium text-green-600"><CheckCircle2 className="size-3" /> Passed</span>;
}

function PriorityBadge({ priority }: { priority: string }) {
  const colors: Record<string, string> = {
    high: "bg-red-500/10 text-red-500",
    medium: "bg-yellow-500/10 text-yellow-600",
    low: "bg-blue-500/10 text-blue-500",
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${colors[priority] || colors.low}`}>
      {priority}
    </span>
  );
}

function formatMs(ms: number): string {
  if (ms < 1) return `${(ms * 1000).toFixed(0)} µs`;
  if (ms < 1000) return `${ms.toFixed(1)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export default function BenchmarkPage() {
  const [status, setStatus] = useState<BenchmarkStatus | null>(null);
  const [modules, setModules] = useState<BenchmarkData | null>(null);
  const [queries, setQueries] = useState<BenchmarkData | null>(null);
  const [graph, setGraph] = useState<BenchmarkData | null>(null);
  const [datasets, setDatasets] = useState<BenchmarkData | null>(null);
  const [agent, setAgent] = useState<BenchmarkData | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [s, m, q, g, d, a, r] = await Promise.all([
        fetchBenchmark<BenchmarkStatus>("/benchmark/status"),
        fetchBenchmark<BenchmarkData>("/benchmark/modules"),
        fetchBenchmark<BenchmarkData>("/benchmark/queries"),
        fetchBenchmark<BenchmarkData>("/benchmark/graph"),
        fetchBenchmark<BenchmarkData>("/benchmark/datasets"),
        fetchBenchmark<BenchmarkData>("/benchmark/agent"),
        fetchBenchmark<RecommendationsData>("/benchmark/recommendations"),
      ]);
      setStatus(s);
      setModules(m);
      setQueries(q);
      setGraph(g);
      setDatasets(d);
      setAgent(a);
      setRecommendations(r);
      setLoading(false);
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-muted-foreground">Loading benchmark data…</div>
      </div>
    );
  }

  // Empty state
  if (!status?.available) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Performance Benchmark</h1>
          <p className="text-sm text-muted-foreground mt-1">P6.5 Runtime Profiling &amp; Performance Analysis</p>
        </div>
        <div className="rounded-lg border border-dashed p-12 text-center">
          <BarChart3 className="mx-auto size-12 text-muted-foreground/40" />
          <h2 className="mt-4 text-lg font-semibold">No benchmark results found</h2>
          <p className="mt-2 text-sm text-muted-foreground max-w-md mx-auto">
            Run the benchmark script to generate performance data:
          </p>
          <code className="mt-4 inline-block rounded bg-muted px-4 py-2 text-sm">
            python Scripts/run_benchmark.py --all --verbose
          </code>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Performance Benchmark</h1>
        <p className="text-sm text-muted-foreground mt-1">
          P6.5 Runtime Profiling &amp; Performance Analysis
          {status.last_run && <span> · Last run: {new Date(status.last_run).toLocaleString()}</span>}
        </p>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <div className="rounded-lg border bg-card p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Zap className="size-4" /> Tasks
          </div>
          <div className="mt-2 text-2xl font-bold">{status.total_tasks || 0}</div>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <CheckCircle2 className="size-4 text-green-500" /> Passed
          </div>
          <div className="mt-2 text-2xl font-bold text-green-600">{status.total_passed || 0}</div>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <AlertTriangle className="size-4 text-yellow-500" /> Warnings
          </div>
          <div className="mt-2 text-2xl font-bold text-yellow-600">{status.total_warnings || 0}</div>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <XCircle className="size-4 text-red-500" /> Failed
          </div>
          <div className="mt-2 text-2xl font-bold text-red-600">{status.total_failed || 0}</div>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Clock className="size-4" /> Run ID
          </div>
          <div className="mt-2 text-xs font-mono">{status.run_id || "N/A"}</div>
        </div>
      </div>

      {/* Module Runtime Matrix */}
      {modules?.available && modules.metrics && (
        <section className="rounded-lg border bg-card">
          <div className="border-b px-5 py-3 flex items-center gap-2">
            <Cpu className="size-4 text-muted-foreground" />
            <h2 className="font-semibold">Module Runtime Matrix</h2>
            <span className="text-xs text-muted-foreground ml-2">
              {modules.passed} passed, {modules.warning_count} warnings, {modules.failed} failed
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50 text-left">
                  <th className="px-5 py-2 font-medium">Module</th>
                  <th className="px-5 py-2 font-medium text-right">Duration</th>
                  <th className="px-5 py-2 font-medium text-right">Input Count</th>
                  <th className="px-5 py-2 font-medium text-right">Warnings</th>
                  <th className="px-5 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {modules.metrics.map((m, i) => (
                  <tr key={i} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="px-5 py-2 font-mono text-xs">{m.label}</td>
                    <td className="px-5 py-2 text-right font-mono text-xs">{formatMs(m.duration_ms)}</td>
                    <td className="px-5 py-2 text-right text-xs text-muted-foreground">
                      {String(m.metadata?.input_count ?? m.metadata?.count ?? "-")}
                    </td>
                    <td className="px-5 py-2 text-right text-xs">{m.warnings?.length || 0}</td>
                    <td className="px-5 py-2"><StatusBadge success={m.success} warning={(m.warnings?.length || 0) > 0} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Query Latency Matrix */}
      {queries?.available && queries.queries && (
        <section className="rounded-lg border bg-card">
          <div className="border-b px-5 py-3 flex items-center gap-2">
            <FileSearch className="size-4 text-muted-foreground" />
            <h2 className="font-semibold">Query Latency Matrix</h2>
            <span className="text-xs text-muted-foreground ml-2">
              {queries.passed} passed, {queries.warning_count} warnings
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50 text-left">
                  <th className="px-5 py-2 font-medium">Query</th>
                  <th className="px-5 py-2 font-medium text-right">Total</th>
                  <th className="px-5 py-2 font-medium text-right">Keyword</th>
                  <th className="px-5 py-2 font-medium text-right">Vector</th>
                  <th className="px-5 py-2 font-medium text-right">Graph</th>
                  <th className="px-5 py-2 font-medium text-right">Merge</th>
                  <th className="px-5 py-2 font-medium text-right">Hits</th>
                </tr>
              </thead>
              <tbody>
                {queries.queries.map((q, i) => (
                  <tr key={i} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="px-5 py-2 font-mono text-xs">{q.query}</td>
                    <td className="px-5 py-2 text-right font-mono text-xs">{formatMs(q.total_duration_ms)}</td>
                    <td className="px-5 py-2 text-right font-mono text-xs">{formatMs(q.keyword_duration_ms)}</td>
                    <td className="px-5 py-2 text-right font-mono text-xs">{formatMs(q.vector_duration_ms)}</td>
                    <td className="px-5 py-2 text-right font-mono text-xs">{formatMs(q.graph_duration_ms)}</td>
                    <td className="px-5 py-2 text-right font-mono text-xs">{formatMs(q.merge_duration_ms)}</td>
                    <td className="px-5 py-2 text-right text-xs">{q.hit_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Graph Runtime */}
      {graph?.available && graph.metrics && (
        <section className="rounded-lg border bg-card">
          <div className="border-b px-5 py-3 flex items-center gap-2">
            <GitBranch className="size-4 text-muted-foreground" />
            <h2 className="font-semibold">Graph Runtime</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50 text-left">
                  <th className="px-5 py-2 font-medium">Operation</th>
                  <th className="px-5 py-2 font-medium text-right">Duration</th>
                  <th className="px-5 py-2 font-medium">Details</th>
                  <th className="px-5 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {graph.metrics.map((m, i) => (
                  <tr key={i} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="px-5 py-2 font-mono text-xs">{m.label}</td>
                    <td className="px-5 py-2 text-right font-mono text-xs">{formatMs(m.duration_ms)}</td>
                    <td className="px-5 py-2 text-xs text-muted-foreground">
                      {m.metadata ? Object.entries(m.metadata).map(([k, v]) => (
                        <span key={k} className="mr-3">{k}: {String(v)}</span>
                      )) : "-"}
                    </td>
                    <td className="px-5 py-2"><StatusBadge success={m.success} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Dataset Runtime */}
      {datasets?.available && datasets.metrics && (
        <section className="rounded-lg border bg-card">
          <div className="border-b px-5 py-3 flex items-center gap-2">
            <Database className="size-4 text-muted-foreground" />
            <h2 className="font-semibold">Dataset Runtime</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50 text-left">
                  <th className="px-5 py-2 font-medium">Operation</th>
                  <th className="px-5 py-2 font-medium text-right">Duration</th>
                  <th className="px-5 py-2 font-medium">Details</th>
                  <th className="px-5 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {datasets.metrics.map((m, i) => (
                  <tr key={i} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="px-5 py-2 font-mono text-xs">{m.label}</td>
                    <td className="px-5 py-2 text-right font-mono text-xs">{formatMs(m.duration_ms)}</td>
                    <td className="px-5 py-2 text-xs text-muted-foreground">
                      {m.metadata ? Object.entries(m.metadata).map(([k, v]) => (
                        <span key={k} className="mr-3">{k}: {String(v)}</span>
                      )) : "-"}
                    </td>
                    <td className="px-5 py-2"><StatusBadge success={m.success} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Agent Runtime */}
      {agent?.available && agent.metrics && (
        <section className="rounded-lg border bg-card">
          <div className="border-b px-5 py-3 flex items-center gap-2">
            <Cpu className="size-4 text-muted-foreground" />
            <h2 className="font-semibold">Agent Runtime</h2>
            <span className="text-xs text-muted-foreground ml-2">
              Mode: evidence_only
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50 text-left">
                  <th className="px-5 py-2 font-medium">Query</th>
                  <th className="px-5 py-2 font-medium text-right">Intent (ms)</th>
                  <th className="px-5 py-2 font-medium text-right">Planning (ms)</th>
                  <th className="px-5 py-2 font-medium text-right">Tool Exec (ms)</th>
                  <th className="px-5 py-2 font-medium text-right">Assembly (ms)</th>
                  <th className="px-5 py-2 font-medium text-right">Answer (ms)</th>
                  <th className="px-5 py-2 font-medium text-right">Total (ms)</th>
                  <th className="px-5 py-2 font-medium text-right">Hits</th>
                </tr>
              </thead>
              <tbody>
                {agent.metrics.map((m, i) => (
                  <tr key={i} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="px-5 py-2 font-mono text-xs max-w-[200px] truncate">{m.label.replace("agent:", "")}</td>
                    <td className="px-5 py-2 text-right font-mono text-xs">{formatMs(Number(m.metadata?.intent_ms) || 0)}</td>
                    <td className="px-5 py-2 text-right font-mono text-xs">{formatMs(Number(m.metadata?.planning_ms) || 0)}</td>
                    <td className="px-5 py-2 text-right font-mono text-xs">{formatMs(Number(m.metadata?.tool_execution_ms) || 0)}</td>
                    <td className="px-5 py-2 text-right font-mono text-xs">{formatMs(Number(m.metadata?.assembly_ms) || 0)}</td>
                    <td className="px-5 py-2 text-right font-mono text-xs">{formatMs(Number(m.metadata?.answer_build_ms) || 0)}</td>
                    <td className="px-5 py-2 text-right font-mono text-xs">{formatMs(Number(m.metadata?.total_ms) || 0)}</td>
                    <td className="px-5 py-2 text-right text-xs">{String(m.metadata?.hit_count || "-")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Recommendations */}
      {recommendations?.available && (
        <section className="rounded-lg border bg-card">
          <div className="border-b px-5 py-3 flex items-center gap-2">
            <Shield className="size-4 text-muted-foreground" />
            <h2 className="font-semibold">Recommendations</h2>
          </div>
          <div className="p-5 space-y-4">
            {recommendations.cache_recommendations && recommendations.cache_recommendations.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-2">Cache Recommendations</h3>
                <div className="space-y-2">
                  {recommendations.cache_recommendations.map((r, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm">
                      <PriorityBadge priority={r.priority} />
                      <div>
                        <span className="font-medium">{r.target}</span>
                        <p className="text-muted-foreground text-xs mt-0.5">{r.recommendation}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {recommendations.incremental_update_recommendations && recommendations.incremental_update_recommendations.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-2">Incremental Update Recommendations</h3>
                <div className="space-y-2">
                  {recommendations.incremental_update_recommendations.map((r, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm">
                      <PriorityBadge priority={r.priority} />
                      <div>
                        <span className="font-medium">{r.target}</span>
                        <p className="text-muted-foreground text-xs mt-0.5">{r.recommendation}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {recommendations.p7_readiness_warnings && recommendations.p7_readiness_warnings.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                  <AlertTriangle className="size-4 text-yellow-500" />
                  P7 Readiness Warnings
                </h3>
                <div className="space-y-1">
                  {recommendations.p7_readiness_warnings.map((w, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm text-yellow-600">
                      <span>⚠️</span>
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {(!recommendations.cache_recommendations?.length &&
              !recommendations.incremental_update_recommendations?.length &&
              !recommendations.p7_readiness_warnings?.length) && (
              <p className="text-sm text-muted-foreground">No recommendations. All modules running within expected thresholds.</p>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
