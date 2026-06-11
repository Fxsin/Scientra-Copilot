"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { Search, ChevronRight, ExternalLink, Hash, Calendar, BookOpen, Users } from "lucide-react";
import { useApiWithFallback } from "@/lib/use-api";
import { getResearchMap } from "@/lib/api";
import { DemoBanner } from "@/components/demo-banner";
import type { ResearchMapResponse, ResearchMapTopic, TopicRelationship, RelatedPaper, YearCount, TopicEvolutionPhase } from "@/lib/types";

/* ═══════════════════════════════════════════════════════
   Helpers
   ═══════════════════════════════════════════════════════ */

function tid(topic: ResearchMapTopic): string {
  return topic.cluster_id || topic.id || "";
}

function tpapers(topic: ResearchMapTopic): RelatedPaper[] {
  return topic.papers || topic.representative_papers || [];
}

/* ═══════════════════════════════════════════════════════
   Keyword / data cleaners (generic, no domain logic)
   ═══════════════════════════════════════════════════════ */

const JUNK_TOKENS = new Set([
  "text", "citation", "citations", "abstract", "summary", "title",
  "paper", "papers", "study", "studies", "result", "results", "method", "methods", "data",
  "using", "based", "against", "not", "with", "from", "into",
  "this", "that", "these", "those", "found", "also", "used",
  "doi", "journal", "author", "authors", "et", "al",
  "approach", "role", "new", "two", "one", "key",
  "cite", "cited", "reference", "references", "content", "section",
  "source", "sources", "finding", "findings", "evidence", "conclusion", "conclusions",
  "note", "notes", "available", "unknown", "none", "null", "true", "false",
]);

function cleanKeywords(kw: string[] | undefined): string[] {
  if (!kw) return [];
  return kw
    .filter((k) => k && k.length >= 3 && !/^S\d{3,}$/i.test(k) && !JUNK_TOKENS.has(k.toLowerCase()) && !/^\d+$/.test(k))
    .slice(0, 6);
}

/* ─── Timeline / trend computation (frontend only, no API change) ─── */

function computeYearDistribution(papers: RelatedPaper[]): YearCount[] {
  const thisYear = new Date().getFullYear();
  const counts: Record<number, number> = {};
  for (const p of papers) {
    const y = p.year;
    if (y && y >= 1800 && y <= thisYear + 1) {
      counts[y] = (counts[y] || 0) + 1;
    }
  }
  return Object.entries(counts).map(([year, count]) => ({ year: parseInt(year), count })).sort((a, b) => a.year - b.year);
}

function computeTrend(topic: ResearchMapTopic): { label: string; recentCount: number; recentRatio: number; reason: string } {
  const papers = tpapers(topic);
  const thisYear = new Date().getFullYear();
  const years = papers.map((p) => p.year).filter((y): y is number => y != null && y >= 1800 && y <= thisYear + 1);
  const total = years.length || topic.paper_count || 0;
  const recentCount = years.filter((y) => y >= thisYear - 5).length;
  const recentRatio = total > 0 ? recentCount / total : 0;

  let label = "unknown";
  let reason = "Trend could not be determined from available data.";
  if (total < 3) { label = "sparse"; reason = "Sparse because there are too few papers to infer a stable trend."; }
  else if (total <= 5 && recentRatio >= 0.6) { label = "emerging"; reason = "Emerging because most papers were published recently."; }
  else if (recentRatio >= 0.4) { label = "active"; reason = "Active because recent papers make up a large share of this topic."; }
  else if (recentCount === 0) { label = "dormant"; reason = "Dormant because no papers were published in the recent window."; }
  else { label = "stable"; reason = "Stable because the topic spans multiple years and still has recent activity."; }

  return { label, recentCount, recentRatio, reason };
}

function computeEvolutionPhases(topic: ResearchMapTopic): any[] {
  const papers = tpapers(topic);
  const thisYear = new Date().getFullYear();
  const validYears = papers.map((p) => p.year).filter((y): y is number => y != null && y >= 1800 && y <= thisYear + 1);
  if (validYears.length === 0) return [];

  const minY = Math.min(...validYears);
  const maxY = Math.max(...validYears);
  if (maxY <= minY) return [];

  const span = maxY - minY;
  const third = Math.max(1, Math.ceil(span / 3));
  const phases: { phase: "early" | "middle" | "recent"; label: string; start: number; end: number }[] = [
    { phase: "early", label: "Early phase", start: minY, end: minY + third },
    { phase: "middle", label: "Middle phase", start: minY + third + 1, end: minY + third * 2 },
    { phase: "recent", label: "Recent phase", start: minY + third * 2 + 1, end: maxY },
  ];

  return phases.map((ph) => {
    const phasePapers = papers.filter((p) => p.year != null && p.year >= ph.start && p.year <= ph.end);
    // Extract keywords from phase paper titles
    const text = phasePapers.map((p) => p.title || "").join(" ");
    const words = text.toLowerCase().replace(/[.,:;()]/g, " ").split(/\s+/).filter((w) => w.length > 3 && !JUNK_TOKENS.has(w));
    const freq: Record<string, number> = {};
    for (const w of words) freq[w] = (freq[w] || 0) + 1;
    const kw = Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k]) => k);

    return {
      phase: ph.phase,
      label: ph.label,
      year_range: [ph.start, ph.end] as [number, number],
      paper_count: phasePapers.length,
      keywords: kw,
      representative_papers: phasePapers.slice(0, 2),
    };
  }).filter((ph) => ph.paper_count > 0);
}

/* ═══════════════════════════════════════════════════════
   Main page
   ═══════════════════════════════════════════════════════ */

export default function ResearchMapPage() {
  const router = useRouter();
  const { data, dataSource, error, lastUrl, lastStatus, refetch } = useApiWithFallback(
    getResearchMap,
    { mature_topics: [], growing_topics: [], gap_topics: [], topic_relationships: [], clusters: [], network_stats: { total_nodes: 0, total_edges: 0 }, cluster_stats: [] } as ResearchMapResponse,
  );

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<string>("paper_count");
  const [density, setDensity] = useState<string>("compact");

  // Merge all topics
  const allTopics: ResearchMapTopic[] = useMemo(() => {
    const seen = new Set<string>();
    const result: ResearchMapTopic[] = [];
    for (const t of [...(data.mature_topics || []), ...(data.growing_topics || []), ...(data.gap_topics || []), ...(data.clusters || [])]) {
      const id = tid(t);
      if (!id || seen.has(id)) continue;
      seen.add(id);
      result.push(t);
    }
    return result;
  }, [data]);

  const relationships = data.topic_relationships || [];

  // Filter + search
  const filtered = useMemo(() => {
    let topics = allTopics;
    if (filterType === "mature") topics = topics.filter((t) => t.type === "mature");
    if (filterType === "growing") topics = topics.filter((t) => t.type === "growing");
    if (filterType === "gap") topics = topics.filter((t) => t.type === "gap");
    if (search.trim()) {
      const q = search.toLowerCase();
      topics = topics.filter((t) => {
        const kw = cleanKeywords(t.keywords).join(" ").toLowerCase();
        const name = (t.name || "").toLowerCase();
        const papers = (t.papers || t.representative_papers || []).map((p) => (p.title || "").toLowerCase()).join(" ");
        return name.includes(q) || kw.includes(q) || papers.includes(q);
      });
    }
    // Sort
    if (sort === "paper_count") topics.sort((a, b) => (b.paper_count || 0) - (a.paper_count || 0));
    if (sort === "recent") topics.sort((a, b) => (b.avg_year || 0) - (a.avg_year || 0));
    if (sort === "name") topics.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    if (sort === "relationships") topics.sort((a, b) => {
      const ra = relationships.filter((r: TopicRelationship) => r.source_topic_id === tid(a) || r.target_topic_id === tid(a)).length;
      const rb = relationships.filter((r: TopicRelationship) => r.source_topic_id === tid(b) || r.target_topic_id === tid(b)).length;
      return rb - ra;
    });
    return topics;
  }, [allTopics, filterType, search, sort, relationships]);

  const selected = useMemo(() => filtered.find((t) => tid(t) === selectedId) || null, [filtered, selectedId]);
  const relatedToSelected = useMemo(() => {
    if (!selectedId) return [];
    return relationships.filter((r) => r.source_topic_id === selectedId || r.target_topic_id === selectedId);
  }, [relationships, selectedId]);

  const matureCount = allTopics.filter((t) => t.type === "mature").length;
  const growingCount = allTopics.filter((t) => t.type === "growing").length;
  const gapCount = allTopics.filter((t) => t.type === "gap").length;

  if (loading(dataSource)) return <ResearchMapSkeleton />;
  if (error) return <ErrorState msg={error} onRetry={refetch} />;
  if (allTopics.length === 0) return <EmptyState />;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      <DemoBanner dataSource={dataSource} error={error || undefined} lastUrl={lastUrl || undefined} lastStatus={lastStatus || undefined} onRetry={refetch} />

      {/* ── Header ── */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-800">Research Map</h1>
        <p className="text-sm text-slate-400 mt-1">Explore topic clusters, representative papers, and relationships in your literature library.</p>
      </div>

      {/* ── Stats ── */}
      <div className="grid grid-cols-5 gap-3">
        <StatCard label="All Topics" value={allTopics.length} active={filterType === "all"} onClick={() => setFilterType("all")} />
        <StatCard label="Mature" value={matureCount} color="emerald" active={filterType === "mature"} onClick={() => setFilterType("mature")} />
        <StatCard label="Growing" value={growingCount} color="blue" active={filterType === "growing"} onClick={() => setFilterType("growing")} />
        <StatCard label="Gaps" value={gapCount} color="amber" active={filterType === "gap"} onClick={() => setFilterType("gap")} />
        <StatCard label="Relationships" value={relationships.length} color="slate" />
      </div>

      {/* ── Body: two-column ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* ── LEFT: topic list ── */}
        <div className="lg:col-span-8 space-y-4">
          {/* Toolbar */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-slate-300" />
              <input
                type="text" value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search topics, keywords, papers…"
                className="w-full rounded-lg border border-slate-200 bg-white pl-9 pr-4 py-2 text-xs text-slate-600 placeholder:text-slate-350 outline-none focus:ring-2 focus:ring-blue-100"
              />
            </div>
            <FilterTabs current={filterType} onChange={setFilterType} />
            <select value={sort} onChange={(e) => setSort(e.target.value)}
              className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-[11px] text-slate-500 outline-none cursor-pointer">
              <option value="paper_count">Paper count</option>
              <option value="recent">Recent activity</option>
              <option value="name">Name</option>
              <option value="relationships">Relationships</option>
            </select>
            <button onClick={() => setDensity(density === "compact" ? "comfortable" : "compact")}
              className="text-[11px] text-slate-400 hover:text-slate-600 border border-slate-200 rounded-lg px-2 py-2 bg-white">
              {density === "compact" ? "Comfortable" : "Compact"}
            </button>
          </div>

          {/* Topic cards */}
          {filtered.length === 0 ? (
            <p className="text-sm text-slate-400 py-8 text-center">No topics match the current search.</p>
          ) : (
            <div className={`grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 ${density === "compact" ? "gap-2" : "gap-3.5"}`}>
              {filtered.map((topic) => (
                <TopicCard
                  key={tid(topic)}
                  topic={topic}
                  selected={selectedId === (tid(topic))}
                  onClick={() => setSelectedId(tid(topic) || null)}
                  onPaperClick={(pid) => router.push(`/paper/${pid}`)}
                />
              ))}
            </div>
          )}
        </div>

        {/* ── RIGHT: detail panel ── */}
        <div className="lg:col-span-4">
          <div className="lg:sticky lg:top-20 space-y-4">
            {selected ? (
              <TopicDetailPanel
                topic={selected}
                relatedTopics={relatedToSelected}
                allTopics={allTopics}
                onTopicClick={(id) => setSelectedId(id)}
                onPaperClick={(pid) => router.push(`/paper/${pid}`)}
                onViewFullTopic={(id) => router.push(`/research-map/topic/${id}`)}
              />
            ) : (
              <div className="rounded-xl border border-slate-200/50 bg-white/80 p-6 text-center">
                <p className="text-sm text-slate-400">Select a topic to inspect its papers, keywords, and relationships.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   Sub-components
   ═══════════════════════════════════════════════════════ */

function loading(ds: string) { return ds === "LOADING"; }

function StatCard({ label, value, color, active, onClick }: { label: string; value: number; color?: string; active?: boolean; onClick?: () => void }) {
  const colors: Record<string, string> = { emerald: "bg-emerald-50 text-emerald-700 border-emerald-200", blue: "bg-blue-50 text-blue-700 border-blue-200", amber: "bg-amber-50 text-amber-700 border-amber-200", slate: "bg-slate-50 text-slate-600 border-slate-200" };
  const cls = color ? colors[color] || colors.slate : colors.slate;
  const activeCls = active ? "ring-2 ring-slate-300" : "";
  return (
    <button onClick={onClick} className={`rounded-xl border px-3 py-2.5 text-left transition-all hover:shadow-sm ${cls} ${activeCls} ${onClick ? "cursor-pointer" : ""}`}>
      <p className="text-[10px] uppercase tracking-wide opacity-70">{label}</p>
      <p className="text-lg font-bold mt-0.5">{value}</p>
    </button>
  );
}

function FilterTabs({ current, onChange }: { current: string; onChange: (v: string) => void }) {
  const tabs = [
    { id: "all", label: "All" },
    { id: "mature", label: "Mature" },
    { id: "growing", label: "Growing" },
    { id: "gap", label: "Gaps" },
  ];
  return (
    <div className="flex rounded-lg border border-slate-200 bg-white p-0.5">
      {tabs.map((t) => (
        <button key={t.id} onClick={() => onChange(t.id)}
          className={`px-2.5 py-1 text-[11px] rounded-md transition-colors ${current === t.id ? "bg-slate-100 text-slate-700 font-medium" : "text-slate-400 hover:text-slate-600"}`}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

/* ─── Topic Card ─── */

function TopicCard({ topic, selected, onClick, onPaperClick }: { topic: ResearchMapTopic; selected: boolean; onClick: () => void; onPaperClick: (pid: string) => void }) {
  const id = tid(topic) || "";
  const kw = cleanKeywords(topic.keywords);
  const typeColors: Record<string, string> = { mature: "bg-emerald-50 text-emerald-600", growing: "bg-blue-50 text-blue-600", gap: "bg-amber-50 text-amber-600" };
  const papers = tpapers(topic);
  const trend = computeTrend(topic);

  return (
    <div onClick={onClick}
      className={`rounded-lg border bg-white transition-all cursor-pointer hover:shadow-md hover:-translate-y-0.5 ${selected ? "border-blue-300 shadow-md ring-1 ring-blue-100" : "border-slate-200/60 shadow-sm"}`}>
      <div className="p-3">
        {/* Header */}
        <div className="flex items-start justify-between gap-1.5">
          <h3 className="text-[13px] font-semibold text-slate-800 leading-snug line-clamp-2 flex-1">{topic.name || `Topic ${id.slice(-3)}`}</h3>
          <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium shrink-0 ${typeColors[topic.type || "mature"] || typeColors.mature}`}>
            {topic.type || "mature"}{trend.label !== "unknown" ? ` · ${trend.label}` : ""}
          </span>
        </div>

        {/* Meta */}
        <div className="flex items-center gap-2 mt-1.5 text-[10px] text-slate-400">
          <span>{topic.paper_count || 0} papers</span>
          <span className="text-slate-300">·</span>
          {topic.year_range && topic.year_range.length === 2 && <span>{topic.year_range[0]}–{topic.year_range[1]}</span>}
          {!topic.year_range && topic.avg_year && <span>~{Math.round(topic.avg_year)}</span>}
          {/* Evidence mini indicator */}
          {papers.length > 0 && (
            <>
              <span className="text-slate-300">·</span>
              <span className="text-emerald-500 font-medium">
                {(() => {
                  const evCount = papers.filter((p: any) => p.evidence && (
                    (p.evidence.core_findings?.length || 0) +
                    (p.evidence.key_results?.length || 0) +
                    (p.evidence.discussion_points?.length || 0) +
                    (p.evidence.methods?.length || 0) > 0
                  )).length;
                  return evCount > 0 ? `Ev ${evCount}/${papers.length}` : null;
                })()}
              </span>
            </>
          )}
        </div>

        {/* Keywords */}
        {kw.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {kw.slice(0, 4).map((k) => (
              <span key={k} className="inline-flex rounded border border-slate-200/60 bg-slate-50/70 px-1.5 py-0.5 text-[9px] text-slate-500">{k}</span>
            ))}
          </div>
        )}

        {/* Representative paper preview */}
        {papers.length > 0 && (
          <p className="mt-2 pt-2 border-t border-slate-100 text-[10px] text-slate-500 leading-snug line-clamp-2">
            <span className="text-slate-300 mr-1">Top:</span>{papers[0].title}
          </p>
        )}
        {papers.length === 0 && <p className="mt-2 text-[10px] text-slate-300 italic">No papers in cluster</p>}
      </div>
    </div>
  );
}

/* ─── Topic Detail Panel ─── */

function TopicDetailPanel({ topic, relatedTopics, allTopics, onTopicClick, onPaperClick, onViewFullTopic }: {
  topic: ResearchMapTopic;
  relatedTopics: any[];
  allTopics: ResearchMapTopic[];
  onTopicClick: (id: string) => void;
  onPaperClick: (pid: string) => void;
  onViewFullTopic?: (id: string) => void;
}) {
  const id = tid(topic) || "";
  const router = useRouter();
  const kw = cleanKeywords(topic.keywords);
  const papers = tpapers(topic);
  const typeColors: Record<string, string> = { mature: "bg-emerald-50 text-emerald-600", growing: "bg-blue-50 text-blue-600", gap: "bg-amber-50 text-amber-600" };

  return (
    <div className="rounded-xl border border-slate-200/50 bg-white/80 shadow-sm divide-y divide-slate-100">
      {/* Header */}
      <div className="p-4">
        <h3 className="text-sm font-bold text-slate-800">{topic.name || `Topic ${id.slice(-3)}`}</h3>
        <div className="flex items-center gap-2 mt-1.5">
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${typeColors[topic.type || "mature"]}`}>{topic.type}</span>
          {(topic as any).trend && <span className="text-[10px] text-slate-400">{(topic as any).trend}</span>}
        </div>
        <div className="flex items-center gap-3 mt-2 text-[11px] text-slate-500">
          <span><span className="font-medium">{topic.paper_count || 0}</span> papers</span>
          {topic.year_range && topic.year_range.length === 2 && <span>{topic.year_range[0]}–{topic.year_range[1]}</span>}
          {!topic.year_range && topic.avg_year && <span>~{Math.round(topic.avg_year)}</span>}
        </div>
        {/* Evidence coverage mini */}
        {papers.length > 0 && (
          <div className="mt-1.5 text-[10px]">
            {(() => {
              const evCount = papers.filter((p: any) => p.evidence && (
                (p.evidence.core_findings?.length || 0) +
                (p.evidence.key_results?.length || 0) +
                (p.evidence.discussion_points?.length || 0) +
                (p.evidence.methods?.length || 0) > 0
              )).length;
              if (evCount > 0) {
                return <span className="text-emerald-600 font-medium">Structured evidence: {evCount}/{papers.length}</span>;
              }
              const sumCount = papers.filter((p: any) => (p as any).summary && !p.evidence).length;
              if (sumCount > 0) {
                return <span className="text-amber-600">Summary fallback: {sumCount}/{papers.length}</span>;
              }
              return null;
            })()}
          </div>
        )}
      </div>

      {/* Keywords */}
      {kw.length > 0 && (
        <div className="p-4">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-2">Keywords</p>
          <div className="flex flex-wrap gap-1">
            {kw.map((k) => (
              <span key={k} className="inline-flex rounded-md border border-slate-200/70 bg-slate-50 px-1.5 py-0.5 text-[10px] text-slate-500">{k}</span>
            ))}
          </div>
        </div>
      )}

      {/* Summary */}
      {topic.summary && (
        <div className="p-4">
          <p className="text-xs text-slate-500 leading-relaxed">{topic.summary}</p>
        </div>
      )}

      {/* Representative papers */}
      <div className="p-4">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-2">Representative Papers</p>
        {papers.length > 0 ? (
          <div className="space-y-2">
            {papers.slice(0, 5).map((p) => (
              <button key={p.paper_id || (p as any).id} onClick={() => onPaperClick(p.paper_id || (p as any).id)}
                className="w-full text-left rounded-lg hover:bg-slate-50 px-2 py-1.5 -mx-2 transition-colors group">
                <p className="text-xs font-medium text-slate-700 leading-snug line-clamp-2 group-hover:text-blue-600">{p.title}</p>
                <p className="text-[10px] text-slate-400 mt-0.5">{p.authors?.[0] || "—"} {p.year ? `· ${p.year}` : ""}{p.journal ? ` · ${p.journal.slice(0, 30)}` : ""}</p>
              </button>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-300 italic">No representative papers available.</p>
        )}
      </div>

      {/* Related topics */}
      <div className="p-4">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-2">Related Topics</p>
        {relatedTopics.length > 0 ? (
          <div className="space-y-1.5">
            {relatedTopics.map((r) => {
              const otherId = r.source_topic_id === id ? r.target_topic_id : r.source_topic_id;
              const other = allTopics.find((t) => (t.cluster_id || (t as any).id) === otherId);
              return (
                <button key={otherId} onClick={() => onTopicClick(otherId)}
                  className="w-full text-left flex items-center justify-between rounded-lg hover:bg-slate-50 px-2 py-1.5 -mx-2 transition-colors text-xs">
                  <span className="text-slate-600 truncate flex-1">{other?.name || otherId}</span>
                  <span className="text-[10px] text-slate-400 ml-2 shrink-0">{Math.round((r.similarity || 0) * 100)}%</span>
                </button>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-slate-300 italic">No strong topic relationships detected yet.</p>
        )}
      </div>
      {onViewFullTopic && (
        <div className="p-3.5 pt-0">
          <button onClick={() => onViewFullTopic(id)} className="w-full text-center text-[11px] text-blue-600 hover:text-blue-800 border border-blue-200 rounded-lg py-2 hover:bg-blue-50 transition-colors">
            View full topic →
          </button>
        </div>
      )}
    </div>
  );
}

/* ─── States ─── */

function ResearchMapSkeleton() {
  return (
    <div className="space-y-6 animate-pulse max-w-7xl mx-auto pb-16">
      <div className="h-7 bg-slate-100 rounded w-48" />
      <div className="h-4 bg-slate-50 rounded w-96" />
      <div className="grid grid-cols-5 gap-3">
        {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-16 bg-slate-50 rounded-xl" />)}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-8 space-y-3">
          {Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-40 bg-slate-50 rounded-xl" />)}
        </div>
        <div className="lg:col-span-4"><div className="h-96 bg-slate-50 rounded-xl" /></div>
      </div>
    </div>
  );
}

function ErrorState({ msg, onRetry }: { msg: string; onRetry: () => void }) {
  return (
    <div className="max-w-7xl mx-auto py-16 text-center">
      <p className="text-sm text-red-500">Unable to load research map.</p>
      <p className="text-xs text-slate-400 mt-1">{msg}</p>
      <button onClick={onRetry} className="mt-3 text-xs text-blue-600 hover:underline">Retry</button>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="max-w-7xl mx-auto py-16 text-center">
      <p className="text-sm text-slate-400">No research topics generated yet.</p>
      <p className="text-xs text-slate-300 mt-1">Import papers or rebuild the research map.</p>
    </div>
  );
}
