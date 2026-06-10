"use client";

import { useState, useEffect, useCallback } from "react";
import { Library, BookOpen, Users, Calendar, Search } from "lucide-react";
import { DemoBanner } from "@/components/demo-banner";
import { DebugPanel } from "@/components/debug-panel";
import { useApiWithFallback, updateGlobalDataSource } from "@/lib/use-api";
import { getStats, queryLiterature, ApiError } from "@/lib/api";
import type { StatsResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";

function buildMockStats(): StatsResponse {
  return {
    paper_count: 0,
    metadata_embedding_count: 0,
    summary_embedding_count: 0,
    chunk_embedding_count: 0,
    tag_distribution: {},
    year_distribution: {},
  };
}

interface SearchResult {
  paper_id: string;
  title?: string;
  journal?: string;
  year?: number;
  doi?: string;
  authors?: string[];
}

export default function LibraryPage() {
  const { data: stats, dataSource, error, lastUrl, lastStatus, refetch } =
    useApiWithFallback(getStats, buildMockStats());

  const [searchQuery, setSearchQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  useEffect(() => {
    updateGlobalDataSource(dataSource);
  }, [dataSource]);

  const doSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      setResults([]);
      return;
    }
    setSearching(true);
    setSearchError(null);
    try {
      const resp = await queryLiterature({
        query: searchQuery.trim(),
        mode: "keyword",
        top_k: 20,
        level: "all",
      });
      setResults(resp.results as unknown as SearchResult[]);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : String(err);
      setSearchError(msg);
    } finally {
      setSearching(false);
    }
  }, [searchQuery]);

  const isRealData = dataSource === "REAL_API";
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

      <DemoBanner
        dataSource={dataSource}
        error={error}
        lastUrl={lastUrl}
        lastStatus={lastStatus}
        onRetry={refetch}
      />

      <div className="grid grid-cols-3 gap-4">
        <StatBadge label="Papers" value={paperCount} />
        <StatBadge label="Topics" value={25} />
        <StatBadge label="Gaps" value={6} />
      </div>

      {/* Search */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") doSearch(); }}
            placeholder="Search by keyword — e.g. Vip3Aa, resistance, receptor…"
            className="w-full rounded-lg border bg-background pl-10 pr-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
        <Button size="sm" onClick={doSearch} disabled={searching || !searchQuery.trim()}>
          {searching ? "Searching…" : "Search"}
        </Button>
      </div>

      {searchError && (
        <div className="text-sm text-red-600 bg-red-50 rounded-lg p-3">{searchError}</div>
      )}

      {/* Results or default paper list */}
      <div className="space-y-3">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <BookOpen className="size-4" />
          {results.length > 0 ? `Results (${results.length})` : "Search for papers above"}
        </h2>
        {results.length > 0
          ? results.map((paper) => (
              <PaperCard key={paper.paper_id} paper={paper} />
            ))
          : !searching && searchQuery && (
              <p className="text-sm text-muted-foreground">No results. Try a different keyword.</p>
            )}
      </div>

      <DebugPanel
        stats={{
          paperCount,
          apiStatus: isRealData ? "ok" : error || "unknown",
          lastError: error,
          lastUrl,
          lastStatus,
        }}
      />
    </div>
  );
}

function StatBadge({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm">
      <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  );
}

function PaperCard({ paper }: { paper: SearchResult }) {
  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm hover:shadow-md transition-shadow">
      <h3 className="font-medium text-sm">{paper.title || "Untitled"}</h3>
      <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
        <span className="flex items-center gap-1"><Users className="size-3" /> {paper.authors?.[0] || "Unknown"}</span>
        {paper.year && <span className="flex items-center gap-1"><Calendar className="size-3" /> {paper.year}</span>}
        {paper.journal && <span className="truncate max-w-[200px]">{paper.journal}</span>}
      </div>
    </div>
  );
}
