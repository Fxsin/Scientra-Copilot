"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, Tag, ChevronLeft, ChevronRight, X, ArrowRight } from "lucide-react";
import { useApiWithFallback, updateGlobalDataSource } from "@/lib/use-api";
import { getStats, getPapers } from "@/lib/api";
import { cleanSummarySnippet } from "@/lib/summary-parser";
import { ScientificText } from "@/components/scientific-text";
import type { StatsResponse, PaperItem } from "@/lib/types";
import { DebugPanel } from "@/components/debug-panel";

function emptyStats(): StatsResponse {
  return { paper_count: 0, metadata_embedding_count: 0, summary_embedding_count: 0, chunk_embedding_count: 0, tag_distribution: {}, year_distribution: {} };
}

const PAGE_SIZE = 15;
const FILTER_FIELDS = [
  { key: "year", label: "Year", placeholder: "e.g. 2022" },
  { key: "toxin", label: "Toxin", placeholder: "Vip3Aa, Cry1Ac" },
  { key: "species", label: "Species", placeholder: "S. frugiperda" },
  { key: "method", label: "Method", placeholder: "BBMV, CRISPR" },
  { key: "tag", label: "Tag", placeholder: "resistance" },
];

export default function LibraryPage() {
  const router = useRouter();

  const { data: stats, dataSource, error: statsError, lastUrl, lastStatus, refetch: refetchStats } =
    useApiWithFallback(getStats, emptyStats());

  const [papers, setPapers] = useState<PaperItem[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [papersError, setPapersError] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [sort, setSort] = useState("");
  const isRealData = dataSource === "REAL_API";

  useEffect(() => { updateGlobalDataSource(dataSource); }, [dataSource]);

  const fetchPapers = useCallback(async (p: number, q: string, f: Record<string, string> = {}) => {
    setLoading(true);
    setPapersError(null);
    try {
      const resp = await getPapers({
        page: p, page_size: PAGE_SIZE,
        q: q || undefined,
        year: f.year ? parseInt(f.year) : undefined,
        toxin: f.toxin || undefined,
        species: f.species || undefined,
        method: f.method || undefined,
        tag: f.tag || undefined,
        sort: sort || undefined,
      });
      setPapers(resp.papers);
      setTotal(resp.total);
      setTotalPages(resp.total_pages);
    } catch (err) {
      setPapersError(err instanceof Error ? err.message : "Failed to load papers");
      setPapers([]); setTotal(0); setTotalPages(1);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchPapers(page, activeQuery, filters); }, [page, activeQuery, fetchPapers]);

  const handleSearch = () => { setPage(1); setActiveQuery(searchQuery); fetchPapers(1, searchQuery, filters); };
  const handleApplyFilters = () => { setPage(1); fetchPapers(1, activeQuery, filters); };
  const handleClearAll = () => { setFilters({}); setSearchQuery(""); setActiveQuery(""); setPage(1); fetchPapers(1, "", {}); };
  const updateFilter = (key: string, value: string) => {
    const next = { ...filters, [key]: value };
    if (!value) delete next[key];
    setFilters(next);
  };
  const activeFilterCount = Object.values(filters).filter(Boolean).length;

  /* page number helpers */
  const pageNumbers: number[] = [];
  const sp = Math.max(1, page - 2), ep = Math.min(totalPages, page + 2);
  for (let i = sp; i <= ep; i++) pageNumbers.push(i);

  return (
    <div className="space-y-5">
      {/* ── Header: light stat line ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-800">Library</h1>
          <p className="text-sm text-slate-400 mt-0.5">
            {isRealData ? `${stats.paper_count} papers` : "Loading collection…"}
          </p>
        </div>
        {loading && <span className="text-xs text-slate-300 animate-pulse">Loading…</span>}
      </div>

      {/* ── Error ── */}
      {(statsError || papersError) && (
        <div className="text-sm text-red-600 bg-red-50/70 rounded-lg px-4 py-2.5 border border-red-100">
          {statsError || papersError}
          <button onClick={() => { refetchStats(); fetchPapers(page, activeQuery, filters); }} className="ml-3 underline text-red-700 text-xs">Retry</button>
        </div>
      )}

      {/* ── Search bar ── */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-300" />
          <input
            type="text" value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleSearch(); }}
            placeholder="Search by keyword — e.g. Vip3Aa, resistance, receptor…"
            className="w-full rounded-lg border border-slate-200 bg-white pl-10 pr-4 py-2.5 text-sm text-slate-700 placeholder:text-slate-400 outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-300 transition-shadow"
          />
        </div>
        <select
          value={sort}
          onChange={(e) => { setSort(e.target.value); setPage(1); }}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-xs text-slate-600 outline-none focus:ring-2 focus:ring-blue-100 cursor-pointer"
        >
          <option value="">Relevance</option>
          <option value="year_desc">Newest first</option>
          <option value="year_asc">Oldest first</option>
          <option value="title">Title A–Z</option>
        </select>
        <button onClick={handleSearch} disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg bg-slate-700 px-3.5 py-2.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-40 transition-colors">
          <Search className="size-3.5" /> {loading ? "…" : "Search"}
        </button>
      </div>

      {/* ── Active filter chips ── */}
      {activeFilterCount > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-slate-400 mr-1">Filters:</span>
          {Object.entries(filters).filter(([, v]) => v).map(([k, v]) => (
            <span key={k} className="inline-flex items-center gap-0.5 rounded-full bg-blue-50 border border-blue-100 px-2.5 py-0.5 text-[11px] text-blue-600">
              {k}:{v}
              <button onClick={() => { updateFilter(k, ""); handleApplyFilters(); }} className="ml-0.5 hover:text-blue-800"><X className="size-3" /></button>
            </span>
          ))}
        </div>
      )}

      {/* ── Filters: ghost chip ── */}
      <div className="flex items-center gap-2">
        <button onClick={() => setFiltersOpen(!filtersOpen)}
          className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] text-slate-500 hover:border-slate-300 hover:text-slate-700 transition-colors">
          <ChevronRight className={`size-3 transition-transform ${filtersOpen ? "rotate-90" : ""}`} />
          Filters
          {activeFilterCount > 0 && (
            <span className="inline-flex items-center justify-center size-4 rounded-full bg-blue-100 text-[10px] font-medium text-blue-600">{activeFilterCount}</span>
          )}
        </button>
        {activeFilterCount > 0 && (
          <button onClick={handleClearAll} className="text-[11px] text-slate-400 hover:text-slate-600">Clear all</button>
        )}
      </div>
      {filtersOpen && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2 p-3 rounded-lg border border-slate-100 bg-slate-50/50">
          {FILTER_FIELDS.map((f) => (
            <div key={f.key}>
              <label className="text-[10px] font-medium text-slate-400 uppercase tracking-wide">{f.label}</label>
              <input type="text" value={filters[f.key] || ""}
                onChange={(e) => updateFilter(f.key, e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") handleApplyFilters(); }}
                placeholder={f.placeholder}
                className="w-full rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 placeholder:text-slate-300 outline-none focus:ring-1 focus:ring-blue-100 mt-0.5" />
            </div>
          ))}
          <div className="col-span-full flex gap-2 mt-1">
            <button onClick={handleApplyFilters} className="text-[11px] px-3 py-1 rounded-md bg-slate-800 text-white hover:bg-slate-700">Apply</button>
            {activeFilterCount > 0 && <button onClick={handleClearAll} className="text-[11px] px-3 py-1 rounded-md border border-slate-200 hover:bg-slate-100">Clear All</button>}
          </div>
        </div>
      )}

      {/* ── Results count ── */}
      {!loading && papers.length > 0 && (
        <p className="text-[11px] text-slate-400">
          Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total} papers
          {activeQuery && <> matching <span className="font-medium text-slate-600">"{activeQuery}"</span></>}
        </p>
      )}

      {/* ── Loading skeleton ── */}
      {loading && (
        <div className="space-y-2 animate-pulse">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="rounded-lg border border-slate-200/60 bg-white/90 px-4 py-3">
              <div className="h-4 bg-slate-100 rounded w-3/4" />
              <div className="h-3 bg-slate-50 rounded w-1/2 mt-2" />
              <div className="h-3 bg-slate-50 rounded w-2/3 mt-1.5" />
            </div>
          ))}
        </div>
      )}

      {/* ── Empty ── */}
      {!loading && !papersError && papers.length === 0 && (
        <div className="py-16 text-center">
          <Search className="size-8 text-slate-200 mx-auto mb-3" />
          <p className="text-sm text-slate-400">
            {activeQuery || activeFilterCount > 0 ? "No papers match the current filters." : "No papers found. Import PDFs and run the workflow first."}
          </p>
        </div>
      )}

      {/* ── Paper list ── */}
      {!loading && papers.length > 0 && (
        <div className="space-y-2">
          {papers.map((paper) => (
            <PaperCard key={paper.paper_id} paper={paper} onClick={() => router.push(`/paper/${paper.paper_id}`)} />
          ))}
        </div>
      )}

      {/* ── Pagination ── */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1 pt-2">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}
            className="inline-flex items-center gap-1 px-2 py-1.5 text-[11px] text-slate-400 rounded-md hover:bg-slate-50 disabled:opacity-25 transition-colors">
            <ChevronLeft className="size-3.5" /> Prev
          </button>
          {sp > 1 && <><button onClick={() => setPage(1)} className="w-7 h-7 text-[11px] text-slate-500 rounded-md hover:bg-slate-50">1</button>{sp > 2 && <span className="px-1 text-slate-300">…</span>}</>}
          {pageNumbers.map((n) => (
            <button key={n} onClick={() => setPage(n)}
              className={`w-7 h-7 text-[11px] rounded-md transition-colors ${n === page ? "bg-slate-100 text-slate-700 font-medium" : "text-slate-500 hover:bg-slate-50"}`}>{n}</button>
          ))}
          {ep < totalPages && <>{ep < totalPages - 1 && <span className="px-1 text-slate-300">…</span>}<button onClick={() => setPage(totalPages)} className="w-7 h-7 text-[11px] text-slate-500 rounded-md hover:bg-slate-50">{totalPages}</button></>}
          <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
            className="inline-flex items-center gap-1 px-2 py-1.5 text-[11px] text-slate-400 rounded-md hover:bg-slate-50 disabled:opacity-25 transition-colors">
            Next <ChevronRight className="size-3.5" />
          </button>
        </div>
      )}

      <DebugPanel stats={{ paperCount: stats.paper_count, apiStatus: isRealData ? "ok" : "error", lastError: statsError || papersError, lastUrl, lastStatus }} />
    </div>
  );
}

/* ─── Paper Card (low-fatigue academic style) ─── */

function PaperCard({ paper, onClick }: { paper: PaperItem; onClick: () => void }) {
  const snippet = cleanSummarySnippet(paper.summary_snippet ?? paper.abstract_snippet);
  const firstAuthor = paper.authors?.[0] || null;
  const authorCount = paper.authors?.length ?? 0;
  const authorLabel = firstAuthor
    ? authorCount > 2 ? `${firstAuthor} et al.` : paper.authors.slice(0, 2).join(", ")
    : null;
  const displayTags = (paper.tags ?? []).filter(t => t && t.length > 1).slice(0, 4);

  return (
    <div onClick={onClick}
      className="group rounded-lg border border-slate-200/60 bg-white/90 shadow-[0_1px_2px_rgba(15,23,42,0.03)] hover:border-blue-200 hover:shadow-[0_2px_8px_rgba(15,23,42,0.06)] hover:-translate-y-px transition-all cursor-pointer px-4 py-3">

      {/* Title */}
      <h3 className="text-sm font-semibold leading-snug text-slate-800 group-hover:text-blue-600 transition-colors line-clamp-2">
        <ScientificText text={paper.title} />
      </h3>

      {/* Meta row */}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-1 text-[11px] text-slate-400">
        {authorLabel && <span>{authorLabel}</span>}
        {paper.year && <><span className="text-slate-300">·</span><span>{paper.year}</span></>}
        {paper.journal && <><span className="text-slate-300">·</span><span className="truncate max-w-[180px]">{paper.journal}</span></>}
      </div>

      {/* Tags */}
      {displayTags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1.5">
          {displayTags.map((t) => (
            <span key={t} className="inline-flex items-center rounded border border-slate-200/70 bg-slate-50 px-1.5 py-0.5 text-[10px] text-slate-500">
              <ScientificText text={t} />
            </span>
          ))}
        </div>
      )}

      {/* AI snippet */}
      {snippet ? (
        <div className="mt-2 flex gap-2 min-w-0">
          <span className="text-[10px] text-slate-350 font-medium shrink-0 mt-0.5">AI insight</span>
          <p className="text-xs text-slate-500 leading-relaxed line-clamp-2 overflow-hidden" title={snippet}>
            <ScientificText text={snippet} />
          </p>
        </div>
      ) : (
        <p className="mt-2 text-[10px] text-slate-300 italic">AI insight not available yet</p>
      )}

      {/* View details — visible on hover */}
      <div className="flex justify-end mt-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
        <span className="inline-flex items-center gap-1 text-[11px] text-blue-500">
          View details <ArrowRight className="size-3" />
        </span>
      </div>
    </div>
  );
}
