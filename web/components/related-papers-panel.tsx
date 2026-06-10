"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { GitBranch } from "lucide-react";
import { TagBadge } from "@/components/tag-badge";
import { getRelatedPapers } from "@/lib/api";
import type { RelatedPaper } from "@/lib/types";

interface RelatedPapersPanelProps {
  paperId: string;
}

function RelatedCard({ paper }: { paper: RelatedPaper }) {
  return (
    <Link
      href={`/papers/${paper.paper_id}`}
      className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4 shadow-sm transition-colors hover:border-accent/30 hover:bg-muted/20 group"
    >
      {/* Title + score */}
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium text-foreground line-clamp-2 group-hover:text-primary transition-colors">
          {paper.title || (
            <span className="italic text-muted-foreground">Untitled</span>
          )}
        </span>
        <span className="shrink-0 font-mono text-xs font-medium text-accent-foreground">
          {paper.similarity_score.toFixed(3)}
        </span>
      </div>

      {/* Meta row */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
        {paper.year && <span>{paper.year}</span>}
        {paper.journal && (
          <span className="italic truncate max-w-[180px]">{paper.journal}</span>
        )}
      </div>

      {/* Shared tags */}
      {paper.shared_tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {paper.shared_tags.slice(0, 6).map((tag) => (
            <TagBadge key={tag} label={tag} />
          ))}
          {paper.shared_tags.length > 6 && (
            <span className="text-[10px] text-muted-foreground">
              +{paper.shared_tags.length - 6}
            </span>
          )}
        </div>
      )}

      {/* Reason */}
      <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
        {paper.reason}
      </p>
    </Link>
  );
}

export function RelatedPapersPanel({ paperId }: RelatedPapersPanelProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["related-papers", paperId],
    queryFn: () => getRelatedPapers(paperId, 5, "hybrid"),
    staleTime: 60_000,
  });

  const papers = data?.related_papers ?? [];

  if (isLoading) {
    return (
      <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <GitBranch className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">Related Papers</h3>
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="rounded-lg border border-border bg-card p-4 animate-pulse">
              <div className="h-4 w-3/4 rounded bg-muted mb-2" />
              <div className="h-3 w-1/2 rounded bg-muted" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (isError || papers.length === 0) return null;

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <div className="flex size-7 items-center justify-center rounded-md bg-accent/15 text-accent-foreground">
          <GitBranch className="size-3.5" strokeWidth={1.5} />
        </div>
        <h3 className="text-sm font-semibold text-foreground">
          Related Papers ({papers.length})
        </h3>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {papers.map((paper) => (
          <RelatedCard key={paper.paper_id} paper={paper} />
        ))}
      </div>
    </div>
  );
}
