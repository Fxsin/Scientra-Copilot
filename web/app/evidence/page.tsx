"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, ExternalLink, Loader2, AlertCircle, ChevronDown, ChevronUp, Beaker, Database } from "lucide-react";
import { queryEvidence } from "@/lib/api";
import {
  type EvidenceSearchResult,
  type EvidenceChunkType,
  CHUNK_TYPE_LABELS,
  CHUNK_TYPE_COLORS,
} from "@/lib/types";

type FilterType = EvidenceChunkType | "all";

const FILTERS: { key: FilterType; label: string }[] = [
  { key: "all", label: "All" },
  { key: "key_result", label: "Key results" },
  { key: "core_finding", label: "Core findings" },
  { key: "method", label: "Methods" },
  { key: "discussion_point", label: "Discussion" },
  { key: "limitation", label: "Limitations" },
  { key: "open_question", label: "Open questions" },
];

export default function EvidenceSearchPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<FilterType>("all");
  const [limit, setLimit] = useState(10);
  const [results, setResults] = useState<EvidenceSearchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const doSearch = useCallback(async () => {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError(null);
    setHasSearched(true);
    try {
      const res = await queryEvidence({
        query: q,
        limit,
        chunk_type: filter === "all" ? undefined : (filter as EvidenceChunkType),
      });
      setResults(res.results || []);
      setSource(res.source);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unable to search evidence right now.");
    } finally {
      setLoading(false);
    }
  }, [query, filter, limit]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") doSearch();
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-16">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-800 flex items-center gap-2">
          <Beaker className="size-5 text-slate-400" /> Evidence Search
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Search structured key results, core findings, methods, and discussion points extracted from papers.
        </p>
      </div>

      {/* Explanation */}
      <div className="rounded-xl border border-slate-200/50 bg-white p-4 flex items-start gap-3">
        <Database className="size-4 text-slate-300 mt-0.5 shrink-0" />
        <div className="text-[11px] text-slate-500 leading-relaxed">
          <p>Evidence search retrieves structured content extracted from research papers, including:</p>
          <ul className="list-disc list-inside mt-1 space-y-0.5 text-slate-400">
            <li><span className="text-emerald-600 font-medium">Key results</span> — experimental findings with direction and measured variables</li>
            <li><span className="text-blue-600 font-medium">Core findings</span> — author-level conclusions and summaries</li>
            <li><span className="text-purple-600 font-medium">Discussion points</span> — interpretations, comparisons, and implications</li>
            <li><span className="text-amber-600 font-medium">Methods</span> — experimental techniques and assays</li>
          </ul>
        </div>
      </div>

      {/* Search bar */}
      <div className="rounded-xl border border-slate-200/50 bg-white p-4 space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-300" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search evidence, results, methods, or discussion points..."
            className="w-full rounded-lg border border-slate-200 bg-white pl-10 pr-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-blue-100"
          />
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${
                filter === f.key
                  ? "bg-blue-50 text-blue-600 border-blue-200 font-medium"
                  : "border-slate-200 text-slate-400 hover:text-slate-600"
              }`}
            >
              {f.label}
            </button>
          ))}
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="text-[11px] border border-slate-200 rounded-lg px-2 py-1.5 text-slate-500 bg-white ml-auto"
          >
            <option value={5}>5 results</option>
            <option value={10}>10 results</option>
            <option value={20}>20 results</option>
          </select>
          <button
            onClick={doSearch}
            disabled={!query.trim() || loading}
            className="text-sm bg-blue-600 text-white rounded-lg px-5 py-2 hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400 transition-colors font-medium flex items-center gap-1.5"
          >
            {loading ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-3.5" />}
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
      </div>

      {/* Results */}
      {error && (
        <div className="flex items-start gap-2 text-sm text-red-500 bg-red-50 rounded-xl p-4">
          <AlertCircle className="size-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {hasSearched && !error && (
        <div className="space-y-3">
          <p className="text-xs text-slate-400">
            {results && results.length > 0
              ? `${results.length} result${results.length !== 1 ? "s" : ""} (source: ${source || "evidence_chunks"})`
              : "No evidence results found for this query."}
          </p>

          {results && results.length === 0 && (
            <div className="rounded-xl border border-slate-200/50 bg-white p-8 text-center">
              <p className="text-sm text-slate-400">No evidence chunks match your query.</p>
              <p className="text-xs text-slate-300 mt-1">Try different search terms or a broader filter.</p>
            </div>
          )}

          {results && results.map((r, i) => (
            <EvidenceResultCardWide
              key={r.chunk_id || `${r.paper_id}-${i}`}
              result={r}
              onOpenPaper={(pid) => router.push(`/paper/${pid}`)}
            />
          ))}
        </div>
      )}

      {!hasSearched && (
        <div className="rounded-xl border border-slate-200/50 bg-white p-8 text-center">
          <Search className="size-8 text-slate-200 mx-auto mb-2" />
          <p className="text-sm text-slate-400">Enter a query to search structured evidence.</p>
          <p className="text-xs text-slate-300 mt-1">Try: resistance mechanism, binding assay, or experimental results</p>
        </div>
      )}
    </div>
  );
}

/* ─── Wide Result Card for /evidence page ─── */

function EvidenceResultCardWide({
  result,
  onOpenPaper,
}: {
  result: EvidenceSearchResult;
  onOpenPaper: (pid: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const chunkType = result.chunk_type || "unknown";
  const typeLabel = CHUNK_TYPE_LABELS[chunkType] || chunkType.replace(/_/g, " ");
  const typeColor = CHUNK_TYPE_COLORS[chunkType] || "bg-slate-50 text-slate-500 border-slate-200";
  const confidence = result.confidence || "unknown";
  const score = typeof result.score === "number" ? result.score.toFixed(3) : null;

  return (
    <div className="rounded-xl border border-slate-200/50 bg-white p-4 space-y-2 hover:shadow-sm transition-shadow">
      {/* Header */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${typeColor}`}>
          {typeLabel}
        </span>
        <span className={`text-[10px] px-2 py-0.5 rounded-full ${
          confidence === "high" ? "bg-emerald-50 text-emerald-600" :
          confidence === "medium" ? "bg-amber-50 text-amber-600" :
          "bg-slate-100 text-slate-500"
        }`}>
          {confidence}
        </span>
        {result.source_section && (
          <span className="text-[10px] text-slate-400">{result.source_section}</span>
        )}
        {score && <span className="text-[10px] text-slate-400 ml-auto">similarity {score}</span>}
      </div>

      {/* Paper */}
      {result.title && (
        <button onClick={() => onOpenPaper(result.paper_id)} className="text-left w-full group">
          <p className="text-sm font-semibold text-slate-700 leading-snug group-hover:text-blue-600">
            {result.title}
          </p>
          <p className="text-[11px] text-slate-400">
            {result.year ? `${result.year}` : ""}
            {result.journal ? ` · ${result.journal}` : ""}
          </p>
        </button>
      )}

      {/* Text */}
      <div className={`text-sm text-slate-600 leading-relaxed ${expanded ? "" : "line-clamp-4"}`}>
        {result.text}
      </div>

      {/* Quote */}
      {result.quote && result.quote !== result.text.slice(0, Math.min(result.quote.length, 200)) && (
        <blockquote className="text-xs text-slate-400 italic border-l-2 border-slate-200 pl-3 line-clamp-3">
          &ldquo;{result.quote.slice(0, 300)}&rdquo;
        </blockquote>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between pt-1">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[11px] text-slate-400 hover:text-slate-600 flex items-center gap-1"
        >
          {expanded ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
          {expanded ? "Show less" : "Show full text"}
        </button>
        <button
          onClick={() => onOpenPaper(result.paper_id)}
          className="text-[11px] text-blue-600 hover:text-blue-800 flex items-center gap-1 font-medium"
        >
          <ExternalLink className="size-3" /> Open paper
        </button>
      </div>
    </div>
  );
}
