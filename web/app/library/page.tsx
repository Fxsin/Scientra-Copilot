"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Library, BookOpen, Users, Calendar, Search, Tag, ChevronLeft, ChevronRight } from "lucide-react";
import { DemoBanner } from "@/components/demo-banner";
import { DebugPanel } from "@/components/debug-panel";
import { useApiWithFallback, updateGlobalDataSource } from "@/lib/use-api";
import { getStats, getPapers } from "@/lib/api";
import type { StatsResponse, PaperItem } from "@/lib/types";

function buildMockStats(): StatsResponse {
  return { paper_count: 0, metadata_embedding_count: 0, summary_embedding_count: 0, chunk_embedding_count: 0, tag_distribution: {}, year_distribution: {} };
}

export default function LibraryPage() {
  const router = useRouter();

  // Stats from /stats
  const { data: stats, dataSource, error, lastUrl, lastStatus, refetch: refetchStats } =
    useApiWithFallback(getStats, buildMockStats());

  // Papers from /papers
  const [papers, setPapers] = useState<PaperItem[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [papersError, setPapersError] = useState<string | null>(null);
  const PAGE_SIZE = 15;
  const isRealData = dataSource === "REAL_API";

  useEffect(() => { updateGlobalDataSource(dataSource); }, [dataSource]);

  const fetchPapers = useCallback(async (p: number, q: string) => {
    setLoading(true);
    setPapersError(null);
    try {
      const resp = await getPapers({ page: p, page_size: PAGE_SIZE, q: q || undefined });
      setPapers(resp.papers);
      setTotal(resp.total);
      setTotalPages(resp.total_pages);
    } catch (err) {
      setPapersError(err instanceof Error ? err.message : "Failed to load papers");
      setPapers([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchPapers(page, activeQuery); }, [page, activeQuery, fetchPapers]);

  const handleSearch = () => {
    setPage(1);
    setActiveQuery(searchQuery);
  };

  const paperCount = isRealData ? stats.paper_count : 0;

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Library className="size-5 text-slate-500" />
          <h1 className="text-2xl font-bold tracking-tight">Library</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          {isRealData ? `${paperCount} papers in collection` : "Browse and manage your research paper collection."}
        </p>
      </div>

      <DemoBanner dataSource={dataSource} error={error || papersError || undefined} lastUrl={lastUrl} lastStatus={lastStatus} onRetry={() => { refetchStats(); fetchPapers(page, activeQuery); }} />

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <StatBadge label="Papers" value={paperCount} />
        <StatBadge label="Page" value={`${page}/${totalPages}`} />
        <StatBadge label="Results" value={total} />
      </div>

      {/* Search */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleSearch(); }}
            placeholder="Search by keyword — e.g. Vip3Aa, resistance, receptor…"
            className="w-full rounded-lg border bg-background pl-10 pr-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
        <button
          onClick={handleSearch}
          disabled={loading}
          className="inline-flex items-center gap-1 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <Search className="size-3.5" /> {loading ? "…" : "Search"}
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="text-sm text-muted-foreground animate-pulse">Loading papers…</div>
      )}

      {/* Error */}
      {papersError && !loading && (
        <div className="text-sm text-red-600 bg-red-50 rounded-lg p-4">{papersError}</div>
      )}

      {/* Empty */}
      {!loading && !papersError && papers.length === 0 && (
        <div className="text-sm text-muted-foreground py-8 text-center">
          {activeQuery ? `No papers matching "${activeQuery}".` : "No papers found. Import PDFs and run the workflow first."}
        </div>
      )}

      {/* Paper list */}
      {!loading && papers.length > 0 && (
        <>
          <div className="space-y-3">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <BookOpen className="size-4" />
              {activeQuery ? `Results for "${activeQuery}" (${total})` : `Papers ${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, total)} of ${total}`}
            </h2>
            {papers.map((paper) => (
              <div
                key={paper.paper_id}
                onClick={() => router.push(`/paper/${paper.paper_id}`)}
                className="rounded-lg border bg-card p-4 shadow-sm hover:shadow-md hover:border-primary/30 transition-all cursor-pointer"
              >
                <h3 className="font-medium text-sm leading-snug">{paper.title}</h3>
                <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-muted-foreground">
                  {paper.authors.length > 0 && (
                    <span className="flex items-center gap-1"><Users className="size-3" /> {paper.authors[0]}{paper.authors.length > 1 ? ` +${paper.authors.length - 1}` : ""}</span>
                  )}
                  {paper.year && <span className="flex items-center gap-1"><Calendar className="size-3" /> {paper.year}</span>}
                  {paper.journal && <span className="truncate max-w-[250px]">{paper.journal}</span>}
                </div>
                {paper.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {paper.tags.slice(0, 5).map((t) => (
                      <span key={t} className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                        <Tag className="size-2.5 mr-0.5" /> {t}
                      </span>
                    ))}
                  </div>
                )}
                {paper.summary_snippet && (
                  <p className="mt-2 text-xs text-muted-foreground leading-relaxed line-clamp-2">{paper.summary_snippet}</p>
                )}
              </div>
            ))}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-center gap-4">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="inline-flex items-center gap-1 text-sm disabled:opacity-30 hover:text-primary"
            >
              <ChevronLeft className="size-4" /> Prev
            </button>
            <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="inline-flex items-center gap-1 text-sm disabled:opacity-30 hover:text-primary"
            >
              Next <ChevronRight className="size-4" />
            </button>
          </div>
        </>
      )}

      <DebugPanel stats={{ paperCount, apiStatus: isRealData ? "ok" : "error", lastError: error || papersError, lastUrl, lastStatus }} />
    </div>
  );
}

function StatBadge({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border bg-card p-4 shadow-sm">
      <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  );
}
