import { Layers } from "lucide-react";
import type { QueryResultItem } from "@/lib/types";

interface EvidencePanelProps {
  chunks: QueryResultItem[];
}

export function EvidencePanel({ chunks }: EvidencePanelProps) {
  if (chunks.length === 0) {
    return (
      <p className="text-xs text-muted-foreground italic">
        No evidence chunks in context.
      </p>
    );
  }

  // Group chunks by paper_id
  const grouped = new Map<string, QueryResultItem[]>();
  for (const chunk of chunks) {
    const list = grouped.get(chunk.paper_id) || [];
    list.push(chunk);
    grouped.set(chunk.paper_id, list);
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Layers className="size-4 text-muted-foreground" strokeWidth={1.5} />
        <span className="text-sm font-semibold text-foreground">
          Evidence Chunks ({chunks.length})
        </span>
      </div>

      {[...grouped.entries()].map(([paperId, items]) => (
        <div
          key={paperId}
          className="rounded-lg border border-border bg-card p-3 shadow-sm"
        >
          <div className="flex items-center gap-2 mb-2">
            <span className="font-mono text-[10px] text-muted-foreground">
              {paperId}
            </span>
            <span className="text-[10px] text-muted-foreground">
              {items.length} chunk{items.length > 1 ? "s" : ""}
            </span>
          </div>
          <div className="space-y-2">
            {items.slice(0, 5).map((item, i) => (
              <div key={i} className="text-xs text-foreground/80 leading-relaxed">
                <span className="font-mono text-[10px] text-muted-foreground mr-1.5">
                  [{item.citation_anchor ?? item.source_section ?? item.level}]
                </span>
                <span className="line-clamp-2">{item.text_preview}</span>
              </div>
            ))}
            {items.length > 5 && (
              <p className="text-[10px] text-muted-foreground">
                +{items.length - 5} more chunks
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
