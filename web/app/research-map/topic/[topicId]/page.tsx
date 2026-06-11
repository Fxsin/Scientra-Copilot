"use client";

import { useEffect, useState, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Search, Hash, Calendar, ExternalLink, Copy, Check, TrendingUp, BarChart3, Layers, ChevronDown, ChevronUp, Quote, FlaskConical, Lightbulb, AlertCircle } from "lucide-react";
import { EvidenceSearchCard } from "@/components/evidence/EvidenceSearchCard";
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

/* ─── Discussion type helpers ─── */

const DISCUSSION_TYPE_LABELS: Record<string, string> = {
  interpretation: "Interpretation",
  mechanism: "Mechanism",
  comparison: "Comparison",
  limitation: "Limitation",
  future_direction: "Future direction",
  implication: "Implication",
  uncertainty: "Uncertainty",
};

const DISCUSSION_TYPE_COLORS: Record<string, string> = {
  interpretation: "bg-blue-50 text-blue-600 border-blue-200",
  mechanism: "bg-purple-50 text-purple-600 border-purple-200",
  comparison: "bg-amber-50 text-amber-600 border-amber-200",
  limitation: "bg-red-50 text-red-600 border-red-200",
  future_direction: "bg-emerald-50 text-emerald-600 border-emerald-200",
  implication: "bg-cyan-50 text-cyan-600 border-cyan-200",
  uncertainty: "bg-slate-100 text-slate-500 border-slate-200",
};

function discussionTypeLabel(t: string | undefined | null): string {
  if (!t) return "Evidence";
  return DISCUSSION_TYPE_LABELS[t] || t.charAt(0).toUpperCase() + t.slice(1).replace(/_/g, " ");
}

function discussionTypeColor(t: string | undefined | null): string {
  if (!t || !DISCUSSION_TYPE_COLORS[t]) return "bg-slate-50 text-slate-500 border-slate-200";
  return DISCUSSION_TYPE_COLORS[t];
}

/* ─── Keyword highlighting (safe, no dangerouslySetInnerHTML) ─── */

const HIGHLIGHT_STOPWORDS = new Set([
  "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and", "or",
  "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
  "this", "that", "these", "those", "from", "into", "using", "based", "also",
  "study", "paper", "result", "results", "method", "methods", "data", "found",
  "show", "shown", "report", "reported", "used", "role", "effect", "effects",
  "not", "against", "without", "between", "among", "through", "during",
]);

function highlightKeywords(text: string, terms: string[]): React.ReactNode[] {
  if (!text || terms.length === 0) return [text];
  // Filter: only terms >= 4 chars, not stopwords
  const clean = terms
    .map((t) => t.toLowerCase().trim())
    .filter((t) => t.length >= 4 && !HIGHLIGHT_STOPWORDS.has(t))
    .slice(0, 10);
  if (clean.length === 0) return [text];

  // Build regex alternation, escape special chars, word boundary
  const escaped = clean.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`\\b(${escaped.join("|")})\\b`, "gi");

  const parts: React.ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    parts.push(<mark key={match.index} className="bg-amber-100 text-amber-900 rounded-sm px-0.5">{match[0]}</mark>);
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.length > 1 ? parts : [text];
}

/* ─── Evidence quality note ─── */

function buildQualityNote(phases: PhaseAnalysis[]): string | null {
  let totalKR = 0; let totalDP = 0; let totalMT = 0;
  for (const ph of phases) {
    totalKR += ph.key_conclusions.length;
    totalDP += ph.evidence_quotes.filter((q) => q.source_type === "discussion_point").length;
    totalMT += ph.method_signals.length;
  }
  if (totalDP > totalKR * 3 && totalKR < 3) {
    return "Most structured evidence in this topic comes from discussion-derived statements. Key experimental results may be under-extracted.";
  }
  if (totalKR >= 3) {
    return `This topic includes ${totalKR} key results and ${totalDP} discussion evidence items across phases.`;
  }
  if (totalMT === 0 && totalDP > 0) {
    return "Method signals are limited in the current extraction.";
  }
  return null;
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
  const evolution = useMemo(() => {
    if (!evolutionRaw || evolutionRaw.length === 0) return [];
    return buildEvidenceDrivenPhaseAnalysis(evolutionRaw);
  }, [evolutionRaw]);
  const evolutionSummary = useMemo(() => {
    if (evolution.length === 0) return "Topic evolution is based on limited structured evidence. More complete paper summaries may improve this analysis.";
    return buildEvSummary(evolution);
  }, [evolution]);
  const yd: { year: number; count: number }[] = t?.year_distribution || [];
  const years = allPapers.map((p) => p.year).filter((y): y is number => y != null && y >= 1800);
  const firstY = years.length > 0 ? Math.min(...years) : null;
  const lastY = years.length > 0 ? Math.max(...years) : null;
  const span = firstY && lastY ? lastY - firstY : 0;

  const copyLink = async () => {
    const ok = await copyToClipboard(window.location.href);
    if (ok) { setCopied(true); setTimeout(() => setCopied(false), 2000); }
  };

  const mergedInfo = (topic as any)?.merged_into || t?.merged_into;

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

      {/* ── Merged notice ── */}
      {mergedInfo && (
        <div className="rounded-xl border border-purple-200 bg-purple-50/50 p-3 flex items-start gap-2 text-sm">
          <AlertCircle className="size-4 text-purple-500 shrink-0 mt-0.5" />
          <div>
            <p className="text-purple-700 font-medium">
              This topic has been merged into a parent topic.
            </p>
            <p className="text-purple-500 text-xs mt-0.5">{mergedInfo.message}</p>
            <button
              onClick={() => router.push(`/research-map/topic/${mergedInfo.parent_cluster_id}`)}
              className="text-xs text-purple-600 hover:text-purple-800 underline mt-1"
            >
              Open merged topic →
            </button>
          </div>
        </div>
      )}

      {/* ── Facet breadcrumb ── */}
      {t?.facet && t?.facet_label && (
        <div className="flex items-center gap-1.5 text-[10px] text-indigo-500">
          <span className="bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-200 font-medium">
            {t.facet_label}
          </span>
        </div>
      )}

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

      {/* ── Research Facets ── */}
      {((topic as any).facet_distribution || []).length > 0 && (
        <div className="rounded-xl border border-slate-200/50 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-700 mb-3">Research Facets</h2>
          <div className="space-y-2">
            {((topic as any).facet_distribution || []).map((fd: any) => (
              <div key={fd.facet} className="flex items-center gap-2 text-[11px]">
                <span className="w-32 text-right text-slate-500 truncate shrink-0">{fd.label}</span>
                <div className="flex-1 h-5 bg-slate-100 rounded-sm overflow-hidden">
                  <div className="h-full bg-indigo-200 rounded-sm transition-all" style={{ width: `${Math.max(3, Math.round(fd.ratio * 100))}%` }} />
                </div>
                <span className="w-16 text-slate-400 shrink-0">{fd.paper_count}/{topic.paper_count || 1}</span>
              </div>
            ))}
          </div>
        </div>
      )}

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

          {/* Topic Evolution — Vertical Timeline */}
          {evolution.length > 0 && (
            <TopicEvolutionTimeline
              evolution={evolution}
              evolutionSummary={evolutionSummary}
              evolutionRaw={evolutionRaw}
              onPaperClick={(pid) => router.push(`/paper/${pid}`)}
            />
          )}
          {evolution.length === 0 && evolutionRaw.length > 0 && (
            <div className="rounded-xl border border-slate-200/50 bg-white p-4">
              <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-2 mb-3"><Layers className="size-3.5 text-slate-400" />Topic Evolution</h2>
              <p className="text-[11px] text-slate-400 italic">Not enough data to build phase analysis. More papers with evidence or summaries are needed.</p>
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

          {/* Evidence Search */}
          <EvidenceSearchCard />

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

/* ─── Topic Evolution Timeline ─── */

function TopicEvolutionTimeline({
  evolution, evolutionSummary, evolutionRaw, onPaperClick,
}: {
  evolution: PhaseAnalysis[];
  evolutionSummary: string;
  evolutionRaw: any[];
  onPaperClick: (pid: string) => void;
}) {
  // Compute overall evidence coverage for summary
  const totalPapers = evolution.reduce((s, ph) => s + ph.paper_count, 0);
  const totalEvidence = evolution.reduce((s, ph) => s + ph.evidence_count, 0);
  const coverageRatio = totalPapers > 0 ? totalEvidence / totalPapers : 0;

  // Build evidence-aware summary
  const buildSummary = (): string => {
    if (coverageRatio >= 0.7) {
      return `This topic has structured evidence for ${totalEvidence}/${totalPapers} papers. The evolution view is based mainly on extracted evidence.`;
    }
    if (coverageRatio > 0) {
      return `Structured evidence coverage is ${Math.round(coverageRatio * 100)}%. Some phase insights may rely on summary fallback.`;
    }
    return "Structured evidence coverage is limited. Phase insights rely on summary fallback.";
  };

  const qualityNote = buildQualityNote(evolution);

  // Collect topic keywords for highlighting
  const topicKeywords = evolutionRaw.flatMap((ph: any) => ph.keywords || []).slice(0, 15);

  return (
    <div className="rounded-xl border border-slate-200/50 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-700 flex items-center gap-2 mb-2">
        <Layers className="size-3.5 text-slate-400" />Topic Evolution
      </h2>
      <p className="text-[10px] text-slate-400 mb-1">
        <ScientificText text={buildSummary()} />
      </p>
      {qualityNote && (
        <p className="text-[10px] text-slate-400 mb-3 italic border-l-2 border-amber-200 pl-2.5">
          {qualityNote}
        </p>
      )}

      {/* Vertical timeline */}
      <div className="relative pl-6 space-y-0">
        {/* Timeline line */}
        <div className="absolute left-[11px] top-2 bottom-2 w-px bg-slate-200" />

        {evolution.map((ph, i) => (
          <PhaseWideCard
            key={ph.phase}
            phase={ph}
            index={i}
            isLast={i === evolution.length - 1}
            onPaperClick={onPaperClick}
            highlightTerms={topicKeywords}
          />
        ))}
      </div>

      {/* Phase Comparison */}
      {evolution.length >= 2 && (
        <PhaseComparison phases={evolution} />
      )}
    </div>
  );
}


/* ─── Phase Wide Card ─── */

function PhaseWideCard({
  phase, index, isLast, onPaperClick, highlightTerms,
}: {
  phase: PhaseAnalysis;
  index: number;
  isLast: boolean;
  onPaperClick: (pid: string) => void;
  highlightTerms: string[];
}) {
  const [expanded, setExpanded] = useState(false);
  const phaseColors = ["bg-amber-300", "bg-blue-300", "bg-emerald-300"];

  // Count evidence content types
  const hasKeyResults = phase.key_conclusions.length > 0;
  const hasDiscussionPoints = phase.evidence_quotes.filter((q) => q.source_type === "discussion_point").length > 0;
  const hasEvidenceQuotes = phase.evidence_quotes.length > 0;
  const hasMethodSignals = phase.method_signals.length > 0;
  const hasOpenQuestions = phase.open_questions.length > 0;
  const hasMilestones = phase.milestone_papers.length > 0;
  const hasChange = !!phase.change_from_previous;

  // Discussion-derived evidence fallback message
  const needsDiscussionFallback = !hasKeyResults && hasDiscussionPoints;
  const hasAnyContent = hasKeyResults || hasDiscussionPoints || hasEvidenceQuotes || hasMethodSignals || hasOpenQuestions || hasMilestones;

  return (
    <div className={`relative pb-5 ${isLast ? "" : "pb-4"}`}>
      {/* Timeline dot */}
      <div className={`absolute left-[-17px] top-1.5 size-3 rounded-full border-2 border-white ${phaseColors[index % 3]} ring-1 ring-slate-200 z-10`} />

      {/* Card */}
      <div className={`rounded-lg border ${phase.paper_count > 0 ? "border-slate-200 bg-white" : "border-slate-100 bg-slate-50/50"}`}>
        {/* ── Header ── */}
        <div className="px-4 py-3 border-b border-slate-100">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-slate-700">{phase.label}</span>
              <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                phase.confidence === "high" ? "bg-emerald-50 text-emerald-600" :
                phase.confidence === "medium" ? "bg-amber-50 text-amber-600" :
                "bg-slate-100 text-slate-500"
              }`}>{phase.confidence} confidence</span>
            </div>
            {/* Evidence coverage badge */}
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
              phase.evidence_count > 0 ? "bg-emerald-50 text-emerald-600" : "bg-slate-100 text-slate-400"
            }`}>
              {phase.evidence_count > 0
                ? `Evidence ${phase.evidence_count}/${phase.paper_count}`
                : `No structured evidence`}
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            {phase.year_range[0]}–{phase.year_range[1]} · {phase.paper_count} paper{phase.paper_count !== 1 ? "s" : ""}
          </p>
        </div>

        {/* ── Main summary row ── */}
        <div className="px-4 py-3 space-y-2.5">
          {/* Focus */}
          {phase.focus && (
            <p className="text-[11px] text-slate-600 leading-relaxed">
              <ScientificText text={phase.focus} />
            </p>
          )}

          {/* What changed */}
          {hasChange && (
            <p className="text-[11px] text-slate-500 leading-relaxed border-l-2 border-blue-200 pl-2.5">
              {phase.change_from_previous}
            </p>
          )}

          {/* Method signals */}
          {hasMethodSignals && (
            <div className="flex flex-wrap gap-1 items-center">
              <span className="text-[9px] text-slate-400 mr-1">Methods:</span>
              {phase.method_signals.map((m) => (
                <span key={m} className="text-[9px] px-1.5 py-0.5 rounded bg-purple-50 text-purple-600 font-medium">{m}</span>
              ))}
            </div>
          )}
        </div>

        {/* ── Evidence Preview ── */}
        <div className="px-4 pb-2 space-y-2">
          {/* Key Results / Core Findings — or discussion fallback */}
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-1">Key Findings</p>
            {hasKeyResults ? (
              <div className="space-y-1.5">
                {phase.key_conclusions.slice(0, 2).map((kc, ki) => (
                  <div key={ki} className="text-[11px] text-slate-600 pl-2.5 border-l-2 border-blue-200 bg-blue-50/30 rounded-r py-1.5 pr-2">
                    <p className="leading-relaxed">{highlightKeywords(kc.excerpt.slice(0, 250), highlightTerms)}</p>
                    <p className="text-[9px] text-slate-400 mt-0.5">{kc.title.slice(0, 60)} · {kc.year}</p>
                  </div>
                ))}
              </div>
            ) : needsDiscussionFallback ? (
              <>
                <p className="text-[10px] text-slate-400 italic mb-1">No explicit key results extracted. Showing discussion-derived evidence:</p>
                <div className="space-y-1.5">
                  {phase.evidence_quotes.filter((q) => q.source_type === "discussion_point").slice(0, 2).map((dp, di) => (
                    <div key={di} className="flex items-start gap-1.5 text-[11px] text-slate-600 bg-slate-50 rounded p-2">
                      <Lightbulb className="size-3 text-amber-400 shrink-0 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        {/* Discussion type badge */}
                        <div className="flex items-center gap-1.5 mb-1">
                          <span className={`text-[8px] px-1.5 py-0.5 rounded-full border ${discussionTypeColor((dp as any).source_type)}`}>
                            {discussionTypeLabel("interpretation")}
                          </span>
                          <span className="text-[9px] text-slate-400">{dp.title.slice(0, 50)} · {dp.year}</span>
                        </div>
                        <p className="leading-relaxed">{highlightKeywords(dp.excerpt.slice(0, 250), highlightTerms)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="text-[10px] text-slate-400 italic">No key findings or discussion points extracted for this phase.</p>
            )}
          </div>

          {/* Milestone papers preview */}
          {hasMilestones && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-1">Milestone Papers</p>
              <div className="space-y-1">
                {phase.milestone_papers.slice(0, 2).map((mp) => (
                  <button
                    key={mp.paper_id}
                    onClick={() => onPaperClick(mp.paper_id)}
                    className="w-full text-left flex items-center justify-between gap-2 rounded-md hover:bg-slate-50 px-2 py-1.5 -mx-2 transition-colors group"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-[11px] font-medium text-slate-700 line-clamp-1 group-hover:text-blue-600">
                        <ScientificText text={mp.title} />
                      </p>
                      <p className="text-[9px] text-slate-400">
                        {mp.year}{mp.journal ? ` · ${mp.journal.slice(0, 30)}` : ""}
                      </p>
                      <p className="text-[9px] text-slate-400 mt-0.5">{mp.reason.slice(0, 100)}</p>
                    </div>
                    {/* Evidence source indicator */}
                    <span className={`text-[8px] px-1.5 py-0.5 rounded-full shrink-0 ${
                      mp.reason.includes("core findings") || mp.reason.includes("discussion points") || mp.reason.includes("method-related") || mp.reason.includes("structured evidence")
                        ? "bg-emerald-50 text-emerald-600"
                        : "bg-slate-100 text-slate-400"
                    }`}>
                      {mp.reason.includes("title and keyword") ? "title" : "evidence"}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── Show/Hide Details ── */}
        {hasAnyContent && (
          <>
            <button
              onClick={() => setExpanded(!expanded)}
              className="w-full px-4 py-2 text-[11px] text-blue-600 hover:text-blue-800 border-t border-slate-100 flex items-center justify-center gap-1 hover:bg-slate-50 transition-colors rounded-b-lg"
            >
              {expanded ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
              {expanded ? "Hide evidence details" : "Show evidence details"}
            </button>

            {expanded && (
              <div className="px-4 pb-4 pt-2 space-y-3 border-t border-slate-100">
                {/* All Key Results */}
                {hasKeyResults && (
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-1">
                      All Key Results ({phase.key_conclusions.length})
                    </p>
                    <div className="space-y-1.5">
                      {phase.key_conclusions.map((kc, ki) => (
                        <div key={ki} className="text-[11px] text-slate-600 pl-2.5 border-l-2 border-blue-200 bg-blue-50/30 rounded-r py-1.5 pr-2">
                          <p className="leading-relaxed">{highlightKeywords(kc.excerpt.slice(0, 300), highlightTerms)}</p>
                          <p className="text-[9px] text-slate-400 mt-0.5">{kc.title.slice(0, 60)} · {kc.year}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Discussion Points */}
                {hasDiscussionPoints && (
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-1">
                      Discussion Points ({phase.evidence_quotes.filter((q) => q.source_type === "discussion_point").length})
                    </p>
                    <div className="space-y-1.5">
                      {phase.evidence_quotes.filter((q) => q.source_type === "discussion_point").map((dp, di) => (
                        <div key={di} className="text-[11px] text-slate-600 bg-slate-50 rounded p-2">
                          <div className="flex items-center gap-1.5 mb-1">
                            <Quote className="size-3 text-slate-300 shrink-0" />
                            <span className={`text-[8px] px-1.5 py-0.5 rounded-full border ${discussionTypeColor("interpretation")}`}>
                              {discussionTypeLabel("interpretation")}
                            </span>
                            <span className="text-[9px] text-slate-500">{dp.title.slice(0, 50)} · {dp.year}</span>
                          </div>
                          <p className="leading-relaxed">{highlightKeywords(dp.excerpt.slice(0, 300), highlightTerms)}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Evidence Chain: Result → Discussion Links */}
                <EvidenceChain phase={phase} />

                {/* All Evidence Quotes */}
                {hasEvidenceQuotes && phase.evidence_quotes.filter((q) => q.source_type !== "discussion_point").length > 0 && (
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-1">Evidence Quotes</p>
                    <div className="space-y-1.5">
                      {phase.evidence_quotes.filter((q) => q.source_type !== "discussion_point").map((eq, ei) => (
                        <div key={ei} className="text-[11px] text-slate-500 bg-slate-50 rounded p-2 italic">
                          <p className="leading-relaxed">&ldquo;{eq.excerpt.slice(0, 250)}&rdquo;</p>
                          <p className="text-[9px] text-slate-400 mt-0.5 not-italic">{eq.title.slice(0, 60)}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* All Milestone Papers */}
                {hasMilestones && (
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-1">
                      All Milestone Papers ({phase.milestone_papers.length})
                    </p>
                    <div className="space-y-1">
                      {phase.milestone_papers.map((mp) => (
                        <button
                          key={mp.paper_id}
                          onClick={() => onPaperClick(mp.paper_id)}
                          className="w-full text-left rounded-md hover:bg-slate-50 px-2 py-1.5 -mx-2 transition-colors group"
                        >
                          <p className="text-[11px] font-medium text-slate-700 line-clamp-1 group-hover:text-blue-600">
                            <ScientificText text={mp.title} />
                          </p>
                          <p className="text-[9px] text-slate-400">{mp.year}{mp.journal ? ` · ${mp.journal.slice(0, 30)}` : ""}</p>
                          <p className="text-[9px] text-slate-400 mt-0.5">{mp.reason.slice(0, 120)}</p>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Open Questions */}
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-1">Open Questions</p>
                  {hasOpenQuestions ? (
                    <div className="space-y-1">
                      {phase.open_questions.map((oq, oi) => (
                        <div key={oi} className="text-[11px] text-slate-500 flex items-start gap-1.5">
                          <AlertCircle className="size-3 text-amber-400 shrink-0 mt-0.5" />
                          <p className="leading-relaxed">{oq.excerpt.slice(0, 250)}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[10px] text-slate-400 italic">No explicit unresolved questions detected.</p>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}


/* ─── Evidence Chain (Result → Discussion Links) ─── */

function EvidenceChain({ phase }: { phase: PhaseAnalysis }) {
  const [showAllLinks, setShowAllLinks] = useState(false);

  // EvidenceChain data comes from the raw phase data stored in evolutionRaw
  // We detect links by checking if both key_results and discussion_points exist
  const hasKR = phase.key_conclusions.length > 0;
  const hasDP = phase.evidence_quotes.filter((q) => q.source_type === "discussion_point").length > 0;

  if (!hasKR && !hasDP) return null;

  // Build synthetic links from key_results → discussion_points proximity
  // Real result_discussion_links are passed through the raw phase data
  const syntheticLinks = hasKR && hasDP ? phase.key_conclusions.slice(0, 3).flatMap((kr, ri) =>
    phase.evidence_quotes.filter((q) => q.source_type === "discussion_point").slice(0, 2).map((dp, di) => ({
      result_index: ri,
      discussion_index: di,
      result_text: kr.excerpt.slice(0, 120),
      discussion_text: dp.excerpt.slice(0, 120),
      link_type: "potential",
      confidence: "low" as "high" | "medium" | "low",
      basis: "Co-occurrence in same phase.",
    }))
  ) : [];

  const displayLinks = syntheticLinks.slice(0, showAllLinks ? syntheticLinks.length : 3);

  if (syntheticLinks.length === 0) {
    // No real links and no synthetic links possible
    if (hasKR && hasDP) {
      return (
        <div className="mt-2">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-1">Evidence Chain</p>
          <p className="text-[10px] text-slate-400 italic">No direct result-discussion links detected yet.</p>
        </div>
      );
    }
    return null;
  }

  const linkTypeLabels: Record<string, string> = {
    interprets: "Interprets", extends: "Extends", questions: "Questions",
    limits: "Limits", unclear: "Unclear", potential: "Potential link",
  };
  const linkTypeColors: Record<string, string> = {
    interprets: "bg-blue-50 text-blue-600", extends: "bg-emerald-50 text-emerald-600",
    questions: "bg-amber-50 text-amber-600", limits: "bg-red-50 text-red-600",
    unclear: "bg-slate-100 text-slate-500", potential: "bg-purple-50 text-purple-500",
  };

  return (
    <div className="mt-2">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-1">
        Evidence Chain ({syntheticLinks.length})
      </p>
      <div className="space-y-1.5">
        {displayLinks.map((link, li) => (
          <div key={li} className="text-[10px] border border-slate-200 rounded-md p-2 space-y-1">
            <div className="flex items-center gap-1.5">
              <span className={`text-[8px] px-1.5 py-0.5 rounded-full ${linkTypeColors[link.link_type] || linkTypeColors.potential}`}>
                {linkTypeLabels[link.link_type] || link.link_type}
              </span>
              <span className={`text-[8px] px-1 py-0.5 rounded-full ${
                link.confidence === "high" ? "bg-emerald-50 text-emerald-600" :
                link.confidence === "medium" ? "bg-amber-50 text-amber-600" :
                "bg-slate-100 text-slate-400"
              }`}>{link.confidence}</span>
            </div>
            <div className="flex items-center gap-1 text-slate-500">
              <span className="text-[9px] bg-blue-50 px-1 rounded">R{link.result_index + 1}</span>
              <span className="text-slate-300">→</span>
              <span className="text-[9px] bg-purple-50 px-1 rounded">D{link.discussion_index + 1}</span>
            </div>
            <div className="space-y-0.5">
              <p className="text-slate-600 leading-snug"><span className="text-slate-400">Result:</span> {link.result_text}</p>
              <p className="text-slate-500 leading-snug"><span className="text-slate-400">Discussion:</span> {link.discussion_text}</p>
            </div>
          </div>
        ))}
      </div>
      {syntheticLinks.length > 3 && (
        <button onClick={() => setShowAllLinks(!showAllLinks)} className="text-[10px] text-blue-600 hover:text-blue-800 mt-1">
          {showAllLinks ? "Show fewer links ▲" : `Show all ${syntheticLinks.length} links ▼`}
        </button>
      )}
    </div>
  );
}


/* ─── Phase Comparison ─── */

function PhaseComparison({ phases }: { phases: PhaseAnalysis[] }) {
  return (
    <div className="mt-5 pt-4 border-t border-slate-100">
      <p className="text-[11px] font-semibold text-slate-700 mb-3">Phase Comparison</p>
      <div className="overflow-x-auto">
        <table className="w-full text-[10px]">
          <thead>
            <tr className="text-left text-slate-400 border-b border-slate-100">
              <th className="pb-2 pr-3 font-medium">Metric</th>
              {phases.map((ph) => (
                <th key={ph.phase} className="pb-2 pr-3 font-medium">{ph.label.split(" ")[0]}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            <tr>
              <td className="py-1.5 pr-3 text-slate-400">Evidence coverage</td>
              {phases.map((ph) => (
                <td key={ph.phase} className="py-1.5 pr-3">
                  <span className={ph.evidence_count > 0 ? "text-emerald-600 font-medium" : "text-slate-400"}>
                    {ph.evidence_count}/{ph.paper_count}
                  </span>
                </td>
              ))}
            </tr>
            <tr>
              <td className="py-1.5 pr-3 text-slate-400">Key results</td>
              {phases.map((ph) => (
                <td key={ph.phase} className="py-1.5 pr-3 text-slate-600">
                  {ph.key_conclusions.length > 0 ? ph.key_conclusions.length : "—"}
                </td>
              ))}
            </tr>
            <tr>
              <td className="py-1.5 pr-3 text-slate-400">Discussion points</td>
              {phases.map((ph) => (
                <td key={ph.phase} className="py-1.5 pr-3 text-slate-600">
                  {ph.evidence_quotes.filter((q) => q.source_type === "discussion_point").length || "—"}
                </td>
              ))}
            </tr>
            <tr>
              <td className="py-1.5 pr-3 text-slate-400">Open questions</td>
              {phases.map((ph) => (
                <td key={ph.phase} className="py-1.5 pr-3 text-slate-600">
                  {ph.open_questions.length > 0 ? ph.open_questions.length : "—"}
                </td>
              ))}
            </tr>
            <tr>
              <td className="py-1.5 pr-3 text-slate-400">Dominant evidence</td>
              {phases.map((ph) => {
                const dps = ph.evidence_quotes.filter((q) => q.source_type === "discussion_point").length;
                const krs = ph.key_conclusions.length;
                const mts = ph.method_signals.length;
                let label = "none";
                if (dps > krs && dps > mts) label = "discussion-heavy";
                else if (krs > dps || mts > dps) label = "results/methods";
                else if (dps + krs + mts === 0) label = "no evidence";
                return (
                  <td key={ph.phase} className="py-1.5 pr-3 text-slate-500">{label}</td>
                );
              })}
            </tr>
            <tr>
              <td className="py-1.5 pr-3 text-slate-400">Method signals</td>
              {phases.map((ph) => (
                <td key={ph.phase} className="py-1.5 pr-3 text-slate-500">
                  {ph.method_signals.length > 0 ? ph.method_signals.slice(0, 3).join(", ") : "—"}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}


function Row({ label, value }: { label: string; value: string | number }) {
  return <div className="flex justify-between"><span className="text-slate-400">{label}</span><span className="font-medium text-slate-600">{value}</span></div>;
}

/* ─── Evidence Overview ─── */

function EvidenceOverview({ topic, allPapers }: { topic: ResearchMapTopic; allPapers: RelatedPaper[] }) {
  const total = allPapers.length || topic.paper_count || 0;
  if (total === 0) return null;

  // Count papers with REAL evidence content (not just presence of evidence object)
  let structuredCount = 0;
  let summaryCount = 0;
  let titleCount = 0;

  // Aggregate evidence composition
  const comp: Record<string, number> = {};

  for (const p of allPapers) {
    const ev = (p as any).evidence;
    const hasStruct = ev && ev.status !== "failed" && (
      (ev.core_findings?.length || 0) > 0 ||
      (ev.key_results?.length || 0) > 0 ||
      (ev.discussion_points?.length || 0) > 0 ||
      (ev.methods?.length || 0) > 0 ||
      (ev.limitations?.length || 0) > 0 ||
      (ev.open_questions?.length || 0) > 0
    );

    if (hasStruct) {
      structuredCount++;
      if (ev.core_findings?.length > 0) comp["core_finding"] = (comp["core_finding"] || 0) + ev.core_findings.length;
      if (ev.key_results?.length > 0) comp["key_result"] = (comp["key_result"] || 0) + ev.key_results.length;
      if (ev.discussion_points?.length > 0) comp["discussion_point"] = (comp["discussion_point"] || 0) + ev.discussion_points.length;
      if (ev.methods?.length > 0) comp["method"] = (comp["method"] || 0) + ev.methods.length;
      if (ev.limitations?.length > 0) comp["limitation"] = (comp["limitation"] || 0) + ev.limitations.length;
      if (ev.open_questions?.length > 0) comp["open_question"] = (comp["open_question"] || 0) + ev.open_questions.length;
    } else if ((p as any).summary) {
      summaryCount++;
    } else {
      titleCount++;
    }
  }

  const maxComp = Math.max(...Object.values(comp), 1);
  const structuredRatio = total > 0 ? structuredCount / total : 0;

  let coverageLabel: string;
  if (structuredRatio >= 0.7) {
    coverageLabel = "Most papers in this topic have structured evidence.";
  } else if (structuredRatio >= 0.5) {
    coverageLabel = "Structured evidence coverage is moderate. Some papers rely on summaries.";
  } else if (structuredRatio > 0) {
    coverageLabel = "Structured evidence coverage is limited. Topic analysis may rely on summaries.";
  } else {
    coverageLabel = "No structured evidence available. All analysis relies on summaries and paper titles.";
  }

  return (
    <div className="rounded-xl border border-slate-200/50 bg-white p-4 space-y-3">
      <h2 className="text-sm font-semibold text-slate-700">Evidence Coverage</h2>
      <div className="flex items-center gap-4 text-[11px]">
        <span className="font-medium text-emerald-600">{structuredCount}/{total}</span> structured
        <span className="text-amber-600">{summaryCount}/{total}</span> summary
        {titleCount > 0 && <span className="text-slate-400">{titleCount} title</span>}
      </div>
      {Object.keys(comp).length > 0 && (
        <div className="space-y-1">
          {Object.entries(comp).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
            <div key={k} className="flex items-center gap-2 text-[10px]">
              <span className="w-28 text-right text-slate-400 capitalize">{k.replace(/_/g, " ")}</span>
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
