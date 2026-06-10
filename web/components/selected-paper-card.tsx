import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { TagBadge } from "@/components/tag-badge";
import type { ContextPaper } from "@/lib/chat-api";

interface SelectedPaperCardProps {
  paper: ContextPaper;
}

export function SelectedPaperCard({ paper }: SelectedPaperCardProps) {
  return (
    <Link
      href={`/papers/${paper.paper_id}`}
      className="flex flex-col gap-1.5 rounded-lg border border-border bg-card p-3 shadow-sm transition-colors hover:border-accent/40 hover:bg-muted/20 group"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium text-foreground line-clamp-2 group-hover:text-primary transition-colors">
          {paper.title || (
            <span className="italic text-muted-foreground">Untitled</span>
          )}
        </span>
        <ExternalLink className="mt-0.5 size-3 shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
        {paper.year && <span>{paper.year}</span>}
        {paper.doi && (
          <span className="font-mono text-[10px] truncate max-w-[160px]">
            {paper.doi}
          </span>
        )}
        <span className="ml-auto font-mono font-medium text-foreground/70">
          score: {paper.score.toFixed(3)}
        </span>
      </div>

      {paper.matchedTags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-0.5">
          {paper.matchedTags.slice(0, 5).map((tag) => (
            <TagBadge key={tag} label={tag} />
          ))}
          {paper.matchedTags.length > 5 && (
            <span className="text-[10px] text-muted-foreground">
              +{paper.matchedTags.length - 5}
            </span>
          )}
        </div>
      )}
    </Link>
  );
}
