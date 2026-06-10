import { Layers, ArrowRight } from "lucide-react";
import Link from "next/link";
import type { KnowledgeCluster } from "@/lib/types";

interface ClusterSummaryCardProps {
  clusters: KnowledgeCluster[];
}

export function ClusterSummaryCard({ clusters }: ClusterSummaryCardProps) {
  const maxPapers = Math.max(...clusters.map((c) => c.paper_count), 1);
  const avgPapers = Math.round(
    clusters.reduce((s, c) => s + c.paper_count, 0) / clusters.length,
  );

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Layers className="size-4 text-muted-foreground" strokeWidth={1.5} />
          <h3 className="text-sm font-semibold text-foreground">Cluster Overview</h3>
        </div>
        <span className="font-mono text-xs text-muted-foreground">
          {clusters.length} clusters
        </span>
      </div>

      <div className="grid gap-2 sm:grid-cols-3 mb-4">
        <div className="rounded-lg bg-muted/50 p-3 text-center">
          <span className="block text-lg font-bold text-foreground">{clusters.length}</span>
          <span className="text-[10px] text-muted-foreground">Clusters</span>
        </div>
        <div className="rounded-lg bg-muted/50 p-3 text-center">
          <span className="block text-lg font-bold text-foreground">{maxPapers}</span>
          <span className="text-[10px] text-muted-foreground">Max Papers</span>
        </div>
        <div className="rounded-lg bg-muted/50 p-3 text-center">
          <span className="block text-lg font-bold text-foreground">{avgPapers}</span>
          <span className="text-[10px] text-muted-foreground">Avg Papers</span>
        </div>
      </div>

      {/* Top 3 cluster previews */}
      <div className="flex flex-col gap-2">
        {clusters.slice(0, 3).map((c) => (
          <Link
            key={c.cluster_id}
            href="/network?tab=clusters"
            className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-xs hover:bg-muted/30 transition-colors group"
          >
            <span className="font-medium text-foreground">{c.name}</span>
            <span className="flex items-center gap-1 text-muted-foreground group-hover:text-foreground">
              {c.paper_count} papers
              <ArrowRight className="size-3" />
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
