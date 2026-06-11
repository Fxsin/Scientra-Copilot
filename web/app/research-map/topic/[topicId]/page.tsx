"use client";

import { useEffect, useState, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Search, Hash, Calendar, ExternalLink, Copy, Check, TrendingUp, BarChart3, Layers } from "lucide-react";
import { getResearchMapTopic } from "@/lib/api";
import { ScientificText } from "@/components/scientific-text";
import { copyToClipboard } from "@/lib/citation";
import { buildEvidenceDrivenPhaseAnalysis, buildEvolutionSummary as buildEvSummary, type PhaseAnalysis, type EvidenceQuote, type MilestonePaper } from "@/lib/topic-evolution";
import type { ResearchMapTopic, RelatedPaper } from "@/lib/types";

/* ─── Helpers ─── */

function cleanName(s: string | undefined): string {
  if (!s) return "";
  return s.replace(/[{}"]/g, "").replace(/"?text"?/gi, "").trim();
}

function BarChart({ data }: { data: { year: number; count: number }[] }) {
  const maxC = Math.max(...data.map((d) => d.count), 1);
  const peaks = data.filter((d) => d.count === maxC).map((d) => d.year);
  return (
    <div>
      <div className="space-y-1">
        {data.map(({ year, count }) => (
          <div key={year} className="flex items-center gap-2 text-[10px] group" title={`${year}: ${count} paper${count > 1 ? "s" : ""}`}>
            <span className="w-10 text-right text-slate-400 shrink-0">{year}</span>
            <div className="flex-1 h-4 bg-slate-100 rounded-sm overflow-hidden">
              <div className="h-full bg-blue-300 rounded-sm transition-all group-hover:bg-blue-400" style={{ width: `${Math.max(3, Math.round((count / maxC) * 100))}%` }} />
            </div>
            <span className="w-5 text-slate-500 shrink-0 tabular-nums">{count}</span>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-slate-400 mt-2">
        Active period: {data[0].year}–{data[data.length - 1].year}
        {peaks.length > 0 && <> · Peak{peaks.length > 1 ? "s" : ""}: {peaks.join(", ")}</>}
      </p>
    </div>
  );
}

export default function TopicDetailPage() {
  const { topicId } = useParams<{ topicId: string }>();
  const router = useRouter();
  const [topic, setTopic] = useState<ResearchMapTopic | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [paperSearch, setPaperSearch] = useState("");
  const [paperSort, setPaperSort] = useState("year_desc");
  const [showAllPapers, setShowAllPapers] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!topicId) return;
    setLoading(true);
    getResearchMapTopic(topicId)
      .then((r) => setTopic(r.topic))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"))
      .finally(() => setLoading(false));
  }, [topicId]);

  const allPapers: RelatedPaper[] = topic?.papers || topic?.representative_papers || [];
  const filtered = useMemo(() => {
    let papers = [...allPapers];
    if (paperSearch.trim()) {
      const q = paperSearch.toLowerCase();
      papers = papers.filter((p) => (p.title || "").toLowerCase().includes(q) || (p.authors || []).some((a) => a.toLowerCase().includes(q)) || (p.journal || "").toLowerCase().includes(q) || (p.year ? String(p.year).includes(q) : false));
    }
    if (paperSort === "year_desc") papers.sort((a, b) => (b.year || 0) - (a.year || 0));
    if (paperSort === "year_asc") papers.sort((a, b) => (a.year || 0) - (b.year || 0));
    if (paperSort === "title") papers.sort((a, b) => (a.title || "").localeCompare(b.title || ""));
    return papers;
  }, [allPapers, paperSearch, paperSort]);

  const t = topic as any;
  const related: any[] = t?.related_topics || [];
  const evolutionRaw: any[] = t?.evolution_phases || [];
  const evolution = useMemo(() => buildEvidenceDrivenPhaseAnalysis(evolutionRaw), [evolutionRaw]);
  const evolutionSummary = useMemo(() => buildEvSummary(evolution), [evolution]);
  const yd: { year: number; count: number }[] = t?.year_distribution || [];
  const years = allPapers.map((p) => p.year).filter((y): y is number => y != null && y >= 1800);
  const firstY = years.length > 0 ? Math.min(...years) : null;
  const lastY = years.length > 0 ? Math.max(...years) : null;
  const span = firstY && lastY ? lastY - firstY : 0;

  const copyLink = async () => {
    const ok = await copyToClipboard(window.location.href);
    if (ok) { setCopied(true); setTimeout(() => setCopied(false), 2000); }
  };

  if (loading) return <Skeleton />;
  if (error || !topic) return (
    <div className="max-w-7xl mx-auto py-16 text-center">
      <p className="text-sm text-red-500">Unable to load topic detail.</p>
      <button onClick={() => router.push("/research-map")} className="mt-3 text-xs text-blue-600 hover:underline">Back to Research Map</button>
    </div>
  );

  const displayPapers = showAllPapers ? filtered : filtered.slice(0, 20);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      {/* ── Navigation ── */}
      <div className="flex items-center gap-3 text-xs text-slate-400">
        <button onClick={() => router.push("/research-map")} className="hover:text-slate-600 flex items-center gap-1"><ArrowLeft className="size-3" /> Research Map</button>
        <span>/</span>
        <span className="text-slate-600 font-medium">Topic Detail</span>
      </div>

      {/* ── Header ── */}
      <div>
        <h1 className="text-2xl font-bold text-slate-800"><ScientificText text={cleanName(topic.name)} /></h1>
        <div className="flex flex-wrap items-center gap-2 mt-2">
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 font-medium">{topic.type || "mature"}</span>
          {t.trend_label && <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-600">{t.trend_label}</span>}
          <span className="text-[11px] text-slate-400 ml-1">{topic.paper_count || 0} papers</span>
          {topic.year_range && <span className="text-[11px] text-slate-400">{topic.year_range[0]}–{topic.year_range[1]}</span>}
        </div>
        {topic.keywords && topic.keywords.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {topic.keywords.slice(0, 8).map((k: string) => <span key={k} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">{cleanName(k)}</span>)}
          </div>
        )}
      </div>

      {/* ── Evidence Overview ── */}
      <EvidenceOverview topic={topic} allPapers={allPapers} />

      {/* ── Topic Overview ── */}
      <div className="rounded-xl border border-slate-200/50 bg-white p-4">
        <p className="text-sm text-slate-600 leading-relaxed">
          <ScientificText text={
            firstY && lastY
              ? `This topic contains ${topic.paper_count || 0} papers spanning ${firstY}–${lastY}. Main signals include ${(topic.keywords || []).slice(0, 3).map((k: string) => cleanName(k)).join(", ")}. Recent activity indicates ${t.trend_label || "a stable"} trend.`
              : "This topic was generated from available paper metadata. More papers may improve trend analysis."
          } />
        </p>
      </div>

      {/* ── Body ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* ── LEFT ── */}
        <div className="lg:col-span-8 space-y-5">

          {/* All Papers */}
          <div className="rounded-xl border border-slate-200/50 bg-white p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-2"><Hash className="size-3.5 text-slate-400" />All Papers ({filtered.length})</h2>
              <select value={paperSort} onChange={(e) => setPaperSort(e.target.value)} className="text-[10px] border border-slate-200 rounded px-2 py-1 text-slate-500">
                <option value="year_desc">Newest</option><option value="year_asc">Oldest</option><option value="title">Title</option>
              </select>
            </div>
            <div className="relative mb-3">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3 text-slate-300" />
              <input type="text" value={paperSearch} onChange={(e) => setPaperSearch(e.target.value)} placeholder="Search papers in this topic…" className="w-full rounded-md border border-slate-200 bg-white pl-8 pr-3 py-1.5 text-[11px] outline-none focus:ring-1 focus:ring-blue-100" />
            </div>
            {filtered.length === 0 ? (
              <p className="text-[11px] text-slate-400 py-4 text-center">No papers match the current search.</p>
            ) : (
              <div className="space-y-1">
                {displayPapers.map((p) => (
                  <button key={p.paper_id} onClick={() => router.push(`/paper/${p.paper_id}`)} className="w-full text-left rounded-md hover:bg-slate-50 px-2 py-2 -mx-2 transition-colors group flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-[11px] font-medium text-slate-700 leading-snug line-clamp-2 group-hover:text-blue-600"><ScientificText text={p.title || ""} /></p>
                        {(p as any).evidence ? <span className="text-[8px] px-1 py-0.5 rounded bg-emerald-50 text-emerald-600 shrink-0 font-medium">Evidence</span> : (p as any).summary ? <span className="text-[8px] px-1 py-0.5 rounded bg-slate-100 text-slate-500 shrink-0">Summary</span> : null}
                      </div>
                      <p className="text-[10px] text-slate-400 mt-0.5">{p.authors?.[0] || "—"}{p.authors && p.authors.length > 1 ? " et al." : ""} {p.year ? `· ${p.year}` : ""}{p.journal ? ` · ${p.journal.slice(0, 40)}` : ""}</p>
                    </div>
                    {p.doi && <a href={`https://doi.org/${p.doi}`} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} className="text-[9px] text-blue-500 hover:underline shrink-0 mt-0.5 flex items-center gap-0.5"><ExternalLink className="size-2.5" />DOI</a>}
                  </button>
                ))}
                {filtered.length > 20 && (
                  <button onClick={() => setShowAllPapers(!showAllPapers)} className="w-full text-center text-[11px] text-blue-600 hover:text-blue-800 py-2">
                    {showAllPapers ? "Show less ▲" : `Show all ${filtered.length} papers ▼`}
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Publications by Year */}
          {yd.length > 0 && (
            <div className="rounded-xl border border-slate-200/50 bg-white p-4">
              <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-2 mb-3"><BarChart3 className="size-3.5 text-slate-400" />Publications by Year</h2>
              <BarChart data={yd} />
            </div>
          )}

          {/* Topic Evolution */}
          {evolution.length > 0 && (
            <div className="rounded-xl border border-slate-200/50 bg-white p-4">
              <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-2 mb-1"><Layers className="size-3.5 text-slate-400" />Topic Evolution</h2>
              <p className="text-[10px] text-slate-400 mb-4"><ScientificText text={evolutionSummary} /></p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {evolution.map((ph: PhaseAnalysis, i: number) => (
                  <div key={ph.phase} className={`rounded-lg border p-3.5 ${ph.paper_count > 0 ? "border-slate-200 bg-white" : "border-slate-100 bg-slate-50/50"}`}>
                    <div className="flex items-center gap-1.5 mb-1">
                      <div className={`size-2.5 rounded-full ${i === 0 ? "bg-amber-300" : i === 1 ? "bg-blue-300" : "bg-emerald-300"}`} />
                      <span className="text-[11px] font-bold text-slate-700">{ph.label}</span>
                      <span className={`ml-auto text-[8px] px-1.5 py-0.5 rounded-full ${ph.confidence === "high" ? "bg-emerald-50 text-emerald-600" : ph.confidence === "medium" ? "bg-amber-50 text-amber-600" : "bg-slate-100 text-slate-500"}`}>{ph.confidence}</span>
                    </div>
                    <p className="text-[9px] text-slate-400 mb-2">{ph.year_range[0]}–{ph.year_range[1]} · {ph.paper_count} papers</p>

                    {/* Focus */}
                    <div className="mb-2">
                      <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-400">Focus</p>
                      <p className="text-[10px] text-slate-600 leading-relaxed">{ph.focus || "Not enough structured evidence to infer a clear phase focus."}</p>
                    </div>

                    {/* Key conclusions */}
                    <div className="mb-2">
                      <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-400">Key conclusions</p>
                      {ph.key_conclusions.length > 0 ? ph.key_conclusions.map((kc: EvidenceQuote, ki: number) => (
                        <div key={ki} className="text-[10px] text-slate-600 mb-1 pl-2 border-l-2 border-blue-200">
                          <p className="leading-relaxed">{kc.excerpt.slice(0, 150)}</p>
                          <p className="text-[8px] text-slate-400 mt-0.5">{kc.title.slice(0, 50)} · {kc.year}</p>
                        </div>
                      )) : <p className="text-[10px] text-slate-400 italic">No explicit key conclusions detected from available summaries.</p>}
                    </div>

                    {/* Evidence from papers */}
                    <div className="mb-2">
                      <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-400">Evidence</p>
                      {ph.evidence_quotes.length > 0 ? ph.evidence_quotes.slice(0, 2).map((eq: EvidenceQuote, ei: number) => (
                        <div key={ei} className="text-[10px] text-slate-500 mb-1 bg-slate-50 rounded p-1.5 italic">
                          <p className="leading-relaxed">&ldquo;{eq.excerpt.slice(0, 140)}&rdquo;</p>
                          <p className="text-[8px] text-slate-400 mt-0.5 not-italic">{eq.title.slice(0, 50)}</p>
                        </div>
                      )) : <p className="text-[10px] text-slate-400 italic">No extractable evidence passages available for this phase.</p>}
                    </div>

                    {/* Method signals */}
                    <div className="mb-2">
                      <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-400">Method signals</p>
                      {ph.method_signals.length > 0 ? (
                        <div className="flex flex-wrap gap-1 mt-0.5">{ph.method_signals.map((m: string) => <span key={m} className="text-[8px] px-1 py-0.5 rounded bg-purple-50 text-purple-600">{m}</span>)}</div>
                      ) : <p className="text-[10px] text-slate-400 italic">No clear method signals detected from available paper summaries.</p>}
                    </div>

                    {/* What changed */}
                    {ph.change_from_previous && (
                      <div className="mb-2">
                        <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-400">What changed</p>
                        <p className="text-[10px] text-slate-500 leading-relaxed">{ph.change_from_previous}</p>
                      </div>
                    )}

                    {/* Open questions */}
                    <div className="mb-2">
                      <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-400">Open questions</p>
                      {ph.open_questions.length > 0 ? ph.open_questions.map((oq: EvidenceQuote, oi: number) => (
                        <p key={oi} className="text-[10px] text-slate-500 leading-relaxed">· {oq.excerpt.slice(0, 150)}</p>
                      )) : <p className="text-[10px] text-slate-400 italic">No explicit unresolved questions detected from available summaries.</p>}
                    </div>

                    {/* Milestone papers */}
                    <div>
                      <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-400 mb-1">Milestone papers</p>
                      {ph.milestone_papers.map((mp: MilestonePaper) => (
                        <button key={mp.paper_id} onClick={() => router.push(`/paper/${mp.paper_id}`)} className="w-full text-left mb-1">
                          <p className="text-[9px] text-blue-600 hover:underline line-clamp-1"><ScientificText text={mp.title} /></p>
                          <p className="text-[8px] text-slate-400">{mp.reason.slice(0, 80)}</p>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── RIGHT ── */}
        <div className="lg:col-span-4 space-y-4">
          {/* Growth Trend */}
          <div className="rounded-xl border border-slate-200/50 bg-white p-3.5 space-y-2">
            <h3 className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5"><TrendingUp className="size-3" />Growth Trend</h3>
            <div className="flex items-center gap-2">
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 font-medium">{t.trend_label || "unknown"}</span>
            </div>
            <div className="space-y-1 text-[10px] text-slate-500">
              <p>Last 5 years: {t.recent_count || 0} / {topic.paper_count || 0} papers</p>
              <p>Recent ratio: {Math.round((t.recent_ratio || 0) * 100)}%</p>
              {firstY && <p>First year: {firstY}</p>}
              {lastY && <p>Latest year: {lastY}</p>}
              {span > 0 && <p>Year span: {span} years</p>}
            </div>
            <p className="text-[10px] text-slate-400">{t.trend_reason || ""}</p>
          </div>

          {/* Topic Stats */}
          <div className="rounded-xl border border-slate-200/50 bg-white p-3.5 space-y-1.5">
            <h3 className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Topic Stats</h3>
            <div className="text-[10px] space-y-1">
              <Row label="Total papers" value={topic.paper_count || 0} />
              <Row label="First year" value={firstY || "—"} />
              <Row label="Latest year" value={lastY || "—"} />
              <Row label="Year span" value={span > 0 ? `${span} years` : "—"} />
              <Row label="Recent papers" value={t.recent_count || 0} />
              <Row label="Related topics" value={related.length} />
            </div>
          </div>

          {/* Related Topics */}
          <div className="rounded-xl border border-slate-200/50 bg-white p-3.5">
            <h3 className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-2">Related Topics</h3>
            {related.length > 0 ? (
              <div className="space-y-1">
                {related.map((r: any) => (
                  <button key={r.cluster_id} onClick={() => router.push(`/research-map/topic/${r.cluster_id}`)} className="w-full text-left flex justify-between rounded hover:bg-slate-50 px-1.5 py-1 text-[11px] text-slate-600">
                    <span className="truncate"><ScientificText text={cleanName(r.name)} /></span>
                    <span className="text-[10px] text-slate-400 ml-2">{Math.round((r.similarity || 0) * 100)}%</span>
                  </button>
                ))}
              </div>
            ) : <p className="text-[11px] text-slate-300 italic">No related topics.</p>}
          </div>

          {/* Quick Actions */}
          <div className="rounded-xl border border-slate-200/50 bg-white p-3.5 space-y-2">
            <h3 className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Quick Actions</h3>
            <button onClick={() => router.push("/research-map")} className="w-full text-left text-[11px] text-slate-600 hover:text-blue-600 flex items-center gap-1.5"><ArrowLeft className="size-3" />Back to Research Map</button>
            <button onClick={copyLink} className="w-full text-left text-[11px] text-slate-600 hover:text-blue-600 flex items-center gap-1.5">
              {copied ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}{copied ? "Copied" : "Copy topic link"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | number }) {
  return <div className="flex justify-between"><span className="text-slate-400">{label}</span><span className="font-medium text-slate-600">{value}</span></div>;
}

/* ─── Evidence Overview ─── */

function EvidenceOverview({ topic, allPapers }: { topic: ResearchMapTopic; allPapers: RelatedPaper[] }) {
  const papersWithEvidence = allPapers.filter((p: any) => p.evidence && p.evidence.status !== "failed").length;
  const papersWithSummary = allPapers.filter((p: any) => (p as any).summary && !(p as any).evidence).length;
  const total = allPapers.length || topic.paper_count || 0;

  if (papersWithEvidence === 0 && papersWithSummary === 0) return null;

  // Aggregate evidence composition
  const comp: Record<string, number> = {};
  for (const p of allPapers) {
    const ev = (p as any).evidence;
    if (!ev) continue;
    if (ev.key_results?.length > 0) comp["key_result"] = (comp["key_result"] || 0) + ev.key_results.length;
    if (ev.core_findings?.length > 0) comp["core_finding"] = (comp["core_finding"] || 0) + ev.core_findings.length;
    if (ev.discussion_points?.length > 0) comp["discussion_point"] = (comp["discussion_point"] || 0) + ev.discussion_points.length;
    if (ev.methods?.length > 0) comp["method"] = (comp["method"] || 0) + ev.methods.length;
    if (ev.limitations?.length > 0) comp["limitation"] = (comp["limitation"] || 0) + ev.limitations.length;
    if (ev.open_questions?.length > 0) comp["open_question"] = (comp["open_question"] || 0) + ev.open_questions.length;
  }
  const maxComp = Math.max(...Object.values(comp), 1);

  const coverageLabel = papersWithEvidence / Math.max(total, 1) >= 0.6 ? "High coverage: Most papers in this topic have structured evidence."
    : papersWithEvidence / Math.max(total, 1) >= 0.3 ? "Medium coverage: Some papers rely on summary fallback."
    : "Low coverage: Topic analysis is limited by incomplete structured evidence.";

  return (
    <div className="rounded-xl border border-slate-200/50 bg-white p-4 space-y-3">
      <h2 className="text-sm font-semibold text-slate-700">Evidence Coverage</h2>
      <div className="flex items-center gap-4 text-[11px]">
        <span className="font-medium text-emerald-600">{papersWithEvidence}/{total}</span> structured
        <span className="text-slate-400">{papersWithSummary} summary</span>
      </div>
      {Object.keys(comp).length > 0 && (
        <div className="space-y-1">
          {Object.entries(comp).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
            <div key={k} className="flex items-center gap-2 text-[10px]">
              <span className="w-24 text-right text-slate-400 capitalize">{k.replace(/_/g, " ")}</span>
              <div className="flex-1 h-3 bg-slate-100 rounded-sm overflow-hidden">
                <div className="h-full bg-emerald-200 rounded-sm" style={{ width: `${Math.round((v / maxComp) * 100)}%` }} />
              </div>
              <span className="w-5 text-slate-500">{v}</span>
            </div>
          ))}
        </div>
      )}
      <p className="text-[10px] text-slate-400">{coverageLabel}</p>
    </div>
  );
}

function Skeleton() {
  return <div className="space-y-6 animate-pulse max-w-7xl mx-auto"><div className="h-4 w-32 bg-slate-100 rounded" /><div className="h-8 w-64 bg-slate-100 rounded" /><div className="h-16 bg-slate-50 rounded-xl" /><div className="grid grid-cols-12 gap-6"><div className="col-span-8 space-y-3"><div className="h-96 bg-slate-50 rounded-xl" /><div className="h-32 bg-slate-50 rounded-xl" /></div><div className="col-span-4 space-y-3"><div className="h-32 bg-slate-50 rounded-xl" /><div className="h-48 bg-slate-50 rounded-xl" /></div></div></div>;
}
