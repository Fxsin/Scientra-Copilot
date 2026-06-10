"use client";

import { Library, BookOpen, Users, Calendar } from "lucide-react";
import { DemoBanner } from "@/components/demo-banner";
import { DebugPanel } from "@/components/debug-panel";
import { useApiWithFallback, updateGlobalDataSource } from "@/lib/use-api";
import { getStats } from "@/lib/api";
import {
  mockResearchPapers,
  type ResearchPaper,
} from "@/lib/data/researchIntelligenceMock";
import type { StatsResponse } from "@/lib/types";
import { useEffect } from "react";

function buildMockStats(): StatsResponse {
  return {
    paper_count: mockResearchPapers.length,
    metadata_embedding_count: 5,
    summary_embedding_count: 5,
    chunk_embedding_count: 12,
    tag_distribution: { Cry1Ac: 3, Vip3Aa: 2, "Receptor binding": 4 },
    year_distribution: { "2024": 2, "2025": 1, "2007": 1, "2022": 1 },
  };
}

export default function LibraryPage() {
  const { data: stats, dataSource, error, lastUrl, lastStatus, refetch } =
    useApiWithFallback(getStats, buildMockStats());

  // Sync global data source for DebugPanel
  useEffect(() => {
    updateGlobalDataSource(dataSource);
  }, [dataSource]);

  const isRealData = dataSource === "REAL_API";
  const paperCount = isRealData ? stats.paper_count : mockResearchPapers.length;

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Library className="size-5 text-slate-500" />
          <h1 className="text-2xl font-bold tracking-tight">Library</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Browse and manage your research paper collection.
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

      {/* Paper list */}
      <div className="space-y-3">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <BookOpen className="size-4" /> Recent Papers
        </h2>
        {mockResearchPapers.slice(0, 5).map((paper) => (
          <PaperCard key={paper.id} paper={paper} />
        ))}
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

function PaperCard({ paper }: { paper: ResearchPaper }) {
  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm hover:shadow-md transition-shadow">
      <h3 className="font-medium text-sm">{paper.title}</h3>
      <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
        <span className="flex items-center gap-1"><Users className="size-3" /> {paper.authors?.[0] || "Unknown"}</span>
        <span className="flex items-center gap-1"><Calendar className="size-3" /> {paper.year}</span>
      </div>
    </div>
  );
}
