"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, ExternalLink, Loader2, AlertCircle, ChevronDown, ChevronUp } from "lucide-react";
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
  { key: "key_result", label: "Results" },
  { key: "core_finding", label: "Findings" },
  { key: "method", label: "Methods" },
  { key: "discussion_point", label: "Discussion" },
  { key: "limitation", label: "Limits" },
  { key: "open_question", label: "Questions" },
];

export function EvidenceSearchCard() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<FilterType>("all");
  const [limit, setLimit] = useState(10);
  const [results, setResults] = useState<EvidenceSearchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<string | null>(null);

  const doSearch = useCallback(async () => {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError(null);
    setResults(null);
    setSource(null);
    try {
      const res = await queryEvidence({
        query: q,
        limit,
        chunk_type: filter === "all" ? undefined : (filter as EvidenceChunkType),
      });
      setResults(res.results || []);
      setSource(res.source);
      if ((res.results || []).length === 0) {
        // graceful: this is not an error
      }
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
    <div className="rounded-xl border border-slate-200/50 bg-white p-3.5 space-y-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        Evidence Search
      </p>
      <p className="text-[9px] text-slate-400 -mt-1.5">
        Search structured evidence chunks across the literature database.
      </p>

      {/* Input */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3 text-slate-300" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search evidence, results, methods..."
          className="w-full rounded-md border border-slate-200 bg-white pl-8 pr-3 py-1.5 text-[11px] outline-none focus:ring-1 focus:ring-blue-100"
        />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-1">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`text-[9px] px-2 py-0.5 rounded-full border transition-colors ${
              filter === f.key
                ? "bg-blue-50 text-blue-600 border-blue-200 font-medium"
                : "border-slate-200 text-slate-400 hover:text-slate-600 hover:border-slate-300"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Limit + Search */}
      <div className="flex items-center gap-2">
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="text-[9px] border border-slate-200 rounded px-1.5 py-1 text-slate-500 bg-white"
        >
          <option value={5}>5</option>
          <option value={10}>10</option>
          <option value={20}>20</option>
        </select>
        <button
          onClick={doSearch}
          disabled={!query.trim() || loading}
          className="flex-1 text-[10px] bg-blue-600 text-white rounded-md py-1.5 hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400 transition-colors font-medium"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-1">
              <Loader2 className="size-3 animate-spin" /> Searching...
            </span>
          ) : (
            "Search"
          )}
        </button>
      </div>

      {/* Results */}
      {error && (
        <div className="flex items-start gap-1.5 text-[10px] text-red-500 bg-red-50 rounded-md p-2">
          <AlertCircle className="size-3 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {results !== null && !error && (
        <div className="space-y-1.5">
          <p className="text-[9px] text-slate-400">
            {results.length > 0
              ? `${results.length} result${results.length !== 1 ? "s" : ""} (${source || "evidence_chunks"})`
              : "No evidence results found for this query."}
          </p>
          {results.length === 0 && source === "empty" && (
            <p className="text-[9px] text-slate-300 italic">No evidence chunks are available yet.</p>
          )}
          {results.map((r, i) => (
            <EvidenceResultCard key={r.chunk_id || `${r.paper_id}-${i}`} result={r} onOpenPaper={(pid) => router.push(`/paper/${pid}`)} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Result Card ─── */

function EvidenceResultCard({
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
    <div className="rounded-md border border-slate-100 bg-slate-50/50 p-2 space-y-1">
      {/* Badges row */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className={`text-[8px] px-1.5 py-0.5 rounded-full border ${typeColor}`}>
          {typeLabel}
        </span>
        {confidence !== "unknown" && (
          <span className={`text-[8px] px-1 py-0.5 rounded-full ${
            confidence === "high" ? "bg-emerald-50 text-emerald-600" :
            confidence === "medium" ? "bg-amber-50 text-amber-600" :
            "bg-slate-100 text-slate-500"
          }`}>
            {confidence}
          </span>
        )}
        {score && <span className="text-[8px] text-slate-400 ml-auto">sim {score}</span>}
      </div>

      {/* Paper info */}
      {result.title && (
        <button
          onClick={() => onOpenPaper(result.paper_id)}
          className="text-left w-full group"
        >
          <p className="text-[10px] font-medium text-slate-700 leading-snug line-clamp-1 group-hover:text-blue-600">
            {result.title}
          </p>
          <p className="text-[8px] text-slate-400">
            {result.year ? `${result.year}` : ""}
            {result.journal ? ` · ${result.journal.slice(0, 30)}` : ""}
          </p>
        </button>
      )}

      {/* Text */}
      <p className={`text-[10px] text-slate-600 leading-relaxed ${expanded ? "" : "line-clamp-3"}`}>
        {result.text}
      </p>

      {/* Quote */}
      {result.quote && result.quote !== result.text.slice(0, result.quote.length) && (
        <p className="text-[9px] text-slate-400 italic line-clamp-2">
          &ldquo;{result.quote.slice(0, 200)}&rdquo;
        </p>
      )}

      {/* Expand + Open */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[9px] text-slate-400 hover:text-slate-600 flex items-center gap-0.5"
        >
          {expanded ? <ChevronUp className="size-2.5" /> : <ChevronDown className="size-2.5" />}
          {expanded ? "Less" : "More"}
        </button>
        <button
          onClick={() => onOpenPaper(result.paper_id)}
          className="text-[9px] text-blue-600 hover:text-blue-800 flex items-center gap-0.5"
        >
          <ExternalLink className="size-2.5" /> Open paper
        </button>
      </div>
    </div>
  );
}
