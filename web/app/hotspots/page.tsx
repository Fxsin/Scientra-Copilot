"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Flame, TrendingUp, ExternalLink, BarChart3, Loader2, AlertCircle, Hash } from "lucide-react";
import { getHotspots } from "@/lib/api";
import type { HotspotsResponse, TrendingTopic, HotPaper, EmergingFacet } from "@/lib/types";

export default function HotspotsPage() {
  const router = useRouter();
  const [data, setData] = useState<HotspotsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHotspots()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load hotspots"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Skeleton />;
  if (error) return <ErrorState message={error} />;
  if (!data) return <ErrorState message="No data received." />;
  if (data.status === "cache_missing") return <CacheMissing message={data.message || ""} />;

  const hasTopics = data.trending_topics.length > 0;
  const hasPapers = data.hot_papers.length > 0;
  const hasFacets = data.emerging_facets.length > 0;

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-16">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Flame className="size-5 text-orange-500" />
          <h1 className="text-2xl font-bold tracking-tight text-slate-800">Hotspots</h1>
        </div>
        <p className="text-sm text-slate-400">
          Active, emerging, and evidence-rich research areas detected from your literature library.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard label="Papers Analyzed" value={data.paper_count} color="slate" />
        <StatCard label="Active Topics" value={data.trending_topics.filter((t) => t.trend_label !== "dormant").length} color="emerald" />
        <StatCard label="Hot Papers" value={data.hot_papers.length} color="blue" />
        <StatCard label="Evidence Chunks" value={Object.values(data.evidence_signals?.chunk_type_distribution || {}).reduce((a, b) => a + b, 0)} color="slate" />
      </div>

      {/* Insights */}
      {data.insights.length > 0 && (
        <div className="rounded-xl border border-slate-200/50 bg-white p-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-2">Insights</p>
          <div className="space-y-1">
            {data.insights.map((insight, i) => (
              <p key={i} className="text-[11px] text-slate-600">· {insight}</p>
            ))}
          </div>
        </div>
      )}

      {/* Trending Topics */}
      <Section title="Trending Topics" icon={<TrendingUp className="size-4 text-slate-400" />} count={data.trending_topics.length}>
        {!hasTopics ? (
          <EmptyInSection msg="No high-growth hotspots detected yet. Try importing more papers." />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {data.trending_topics.map((t) => <TrendingTopicCard key={t.id} topic={t} onClick={() => router.push(`/research-map/topic/${t.id}`)} />)}
          </div>
        )}
      </Section>

      {/* Hot Papers */}
      <Section title="Hot Papers" icon={<Hash className="size-4 text-slate-400" />} count={data.hot_papers.length}>
        {!hasPapers ? (
          <EmptyInSection msg="No hot papers identified." />
        ) : (
          <div className="space-y-2">
            {data.hot_papers.map((p) => <HotPaperRow key={p.paper_id} paper={p} onClick={() => router.push(`/paper/${p.paper_id}`)} />)}
          </div>
        )}
      </Section>

      {/* Emerging Facets */}
      <Section title="Emerging Facets" icon={<BarChart3 className="size-4 text-slate-400" />} count={data.emerging_facets.length}>
        {!hasFacets ? (
          <EmptyInSection msg="No emerging facets detected." />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {data.emerging_facets.map((f) => <EmergingFacetCard key={f.facet} facet={f} />)}
          </div>
        )}
      </Section>

      {/* Method Shifts */}
      <Section title="Method Shifts" icon={<TrendingUp className="size-4 text-slate-400" />} count={data.method_shifts?.length || 0}>
        {(data.method_shifts || []).length === 0 ? (
          <EmptyInSection msg="Method shift detection is limited by available method evidence." />
        ) : (
          <div className="space-y-2">
            {(data.method_shifts || []).map((ms: any, i: number) => (
              <div key={i} className="rounded-lg border border-slate-200 bg-white p-3">
                <p className="text-[11px] font-semibold text-slate-700">{ms.topic_name}</p>
                <p className="text-[10px] text-slate-400">{ms.facet_label} · {ms.confidence} confidence</p>
                {ms.new_methods?.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {ms.new_methods.map((m: string) => <span key={m} className="text-[8px] px-1.5 py-0.5 rounded bg-purple-50 text-purple-600">{m}</span>)}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Evidence Signals */}
      <Section title="Evidence Signals" icon={<BarChart3 className="size-4 text-slate-400" />}>
        <div className="flex flex-wrap gap-3">
          {Object.entries(data.evidence_signals?.chunk_type_distribution || {}).map(([k, v]) => (
            <div key={k} className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-center">
              <p className="text-lg font-bold text-slate-700">{v}</p>
              <p className="text-[10px] text-slate-400 capitalize">{k.replace(/_/g, " ")}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* Cache info */}
      {data.generated_at && (
        <p className="text-center text-[9px] text-slate-300">
          Generated from Research Map cache · {data.generated_at.slice(0, 19).replace("T", " ")}
        </p>
      )}
    </div>
  );
}

/* ─── Sub-components ─── */

function Section({ title, icon, count, children }: { title: string; icon: React.ReactNode; count?: number; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200/50 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-2 mb-3">
        {icon}{title}{count !== undefined ? ` (${count})` : ""}
      </h2>
      {children}
    </div>
  );
}

function EmptyInSection({ msg }: { msg: string }) {
  return <p className="text-[11px] text-slate-400 italic py-4 text-center">{msg}</p>;
}

function StatCard({ label, value, color }: { label: string; value: number; color?: string }) {
  const colors: Record<string, string> = { emerald: "bg-emerald-50 text-emerald-700 border-emerald-200", blue: "bg-blue-50 text-blue-700 border-blue-200", slate: "bg-slate-50 text-slate-600 border-slate-200" };
  return (
    <div className={`rounded-xl border px-3 py-2.5 ${colors[color || "slate"]}`}>
      <p className="text-[10px] uppercase tracking-wide opacity-70">{label}</p>
      <p className="text-lg font-bold mt-0.5">{value}</p>
    </div>
  );
}

function TrendingTopicCard({ topic, onClick }: { topic: TrendingTopic; onClick: () => void }) {
  const trendColors: Record<string, string> = { hot: "bg-orange-50 text-orange-600", active: "bg-emerald-50 text-emerald-600", stable: "bg-slate-100 text-slate-500", dormant: "bg-slate-50 text-slate-400" };
  return (
    <button onClick={onClick} className="text-left rounded-lg border border-slate-200 bg-white p-3.5 hover:shadow-md hover:border-blue-200 transition-all cursor-pointer group">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[13px] font-semibold text-slate-700 group-hover:text-blue-600 leading-snug line-clamp-2">{topic.name}</p>
        <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium shrink-0 ${trendColors[topic.trend_label] || trendColors.stable}`}>{topic.trend_label}</span>
      </div>
      <p className="text-[10px] text-slate-400 mt-0.5">{topic.facet_label}</p>
      <div className="flex items-center gap-2 mt-1.5 text-[10px] text-slate-400">
        <span>{topic.paper_count} papers</span><span className="text-slate-300">·</span>
        <span>Recent {Math.round(topic.recent_ratio * 100)}%</span><span className="text-slate-300">·</span>
        <span className="text-emerald-500">Ev {topic.evidence_coverage.structured}/{topic.evidence_coverage.total}</span>
      </div>
      <div className="mt-1.5 w-full bg-slate-100 rounded-full h-1.5">
        <div className="bg-blue-400 h-1.5 rounded-full" style={{ width: `${Math.round(topic.growth_score * 100)}%` }} />
      </div>
    </button>
  );
}

function HotPaperRow({ paper, onClick }: { paper: HotPaper; onClick: () => void }) {
  return (
    <button onClick={onClick} className="w-full text-left rounded-lg border border-slate-100 bg-white px-3 py-2.5 hover:bg-slate-50 transition-colors group flex items-start justify-between gap-2">
      <div className="flex-1 min-w-0">
        <p className="text-[12px] font-medium text-slate-700 leading-snug line-clamp-1 group-hover:text-blue-600">{paper.title}</p>
        <p className="text-[10px] text-slate-400 mt-0.5">{paper.year}{paper.journal ? ` · ${paper.journal.slice(0, 30)}` : ""}</p>
        <div className="flex items-center gap-1.5 mt-1">
          <span className="text-[8px] px-1 py-0.5 rounded bg-emerald-50 text-emerald-600">KR:{paper.evidence_counts.key_results}</span>
          <span className="text-[8px] px-1 py-0.5 rounded bg-blue-50 text-blue-600">CF:{paper.evidence_counts.core_findings}</span>
          <span className="text-[8px] px-1 py-0.5 rounded bg-purple-50 text-purple-600">MT:{paper.evidence_counts.methods}</span>
          <span className="text-[8px] px-1 py-0.5 rounded bg-amber-50 text-amber-600">DP:{paper.evidence_counts.discussion_points}</span>
        </div>
        <p className="text-[9px] text-slate-400 mt-1">{paper.reason}</p>
      </div>
      <span className="text-[10px] text-slate-400 shrink-0">{paper.score.toFixed(2)}</span>
    </button>
  );
}

function EmergingFacetCard({ facet }: { facet: EmergingFacet }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3.5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[12px] font-semibold text-slate-700">{facet.label}</p>
        <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${facet.trend_label === "active" ? "bg-emerald-50 text-emerald-600" : "bg-slate-100 text-slate-500"}`}>{facet.trend_label}</span>
      </div>
      <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-400">
        <span>{facet.paper_count} papers</span><span className="text-slate-300">·</span>
        <span>{Math.round(facet.recent_ratio * 100)}% recent</span><span className="text-slate-300">·</span>
        <span>{facet.subtopic_count} subtopics</span>
      </div>
      {facet.top_subtopics.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {facet.top_subtopics.map((s) => <span key={s} className="text-[9px] px-1.5 py-0.5 rounded bg-slate-50 text-slate-500">{s.slice(0, 40)}</span>)}
        </div>
      )}
    </div>
  );
}

/* ─── States ─── */

function Skeleton() {
  return (
    <div className="space-y-6 animate-pulse max-w-6xl mx-auto">
      <div className="h-7 bg-slate-100 rounded w-48" />
      <div className="grid grid-cols-4 gap-3">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-16 bg-slate-50 rounded-xl" />)}</div>
      <div className="h-48 bg-slate-50 rounded-xl" />
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="max-w-6xl mx-auto py-16 text-center">
      <AlertCircle className="size-8 text-red-300 mx-auto mb-2" />
      <p className="text-sm text-red-500">Unable to load hotspots.</p>
      <p className="text-xs text-slate-400 mt-1">{message}</p>
    </div>
  );
}

function CacheMissing({ message }: { message: string }) {
  return (
    <div className="max-w-6xl mx-auto py-16 text-center">
      <Flame className="size-8 text-slate-300 mx-auto mb-2" />
      <p className="text-sm text-slate-500">Research Map cache is not available.</p>
      <p className="text-xs text-slate-400 mt-1">Rebuild the Research Map to detect hotspots.</p>
    </div>
  );
}
