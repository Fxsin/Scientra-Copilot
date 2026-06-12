"use client";

import { Search, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentContextItem } from "@/lib/types";
import { useState } from "react";

const CHUNK_TYPE_COLORS: Record<string, string> = {
  section: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  method: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  result: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  claim: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
  pdf_asset_chunks: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
  evidence_chunks: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300",
};

interface AgentContextCardsProps {
  chunks: AgentContextItem[];
  highlightedRef: string | null;
  defaultOpen?: boolean;
}

export function AgentContextCards({ chunks, highlightedRef, defaultOpen = true }: AgentContextCardsProps) {
  const [open, setOpen] = useState(defaultOpen);

  if (!chunks || chunks.length === 0) return null;

  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-sm font-semibold w-full text-left"
      >
        <Search className="h-4 w-4 text-primary" />
        Retrieved Context ({chunks.length} chunks)
        {open ? <ChevronUp className="h-4 w-4 ml-auto" /> : <ChevronDown className="h-4 w-4 ml-auto" />}
      </button>
      {open && (
        <div className="mt-3 grid gap-2 max-h-[60vh] overflow-y-auto">
          {chunks.map((chunk, i) => {
            const refId = `Ref:${i + 1}`;
            const anchorId = `ctx-${refId.replace(/[^a-zA-Z0-9]/g, "-")}`;
            return (
              <div
                key={chunk.chunk_id || i}
                id={anchorId}
                className={cn(
                  "rounded-lg border p-3 text-sm transition-colors",
                  highlightedRef === refId && "ring-2 ring-primary border-primary/30 bg-primary/5"
                )}
              >
                <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                  <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs font-mono font-medium text-primary">
                    {refId}
                  </span>
                  <span className={cn("rounded px-1.5 py-0.5 text-xs font-medium",
                    CHUNK_TYPE_COLORS[chunk.chunk_type] || "bg-gray-100 text-gray-700")}>
                    {chunk.chunk_type}
                  </span>
                  <span className={cn("rounded px-1.5 py-0.5 text-xs font-medium",
                    CHUNK_TYPE_COLORS[chunk.source] || "bg-gray-100 text-gray-700")}>
                    {chunk.source}
                  </span>
                  <span className="text-xs text-muted-foreground ml-auto">
                    score: {chunk.score?.toFixed(3)}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mb-1 truncate">{chunk.paper_id}</p>
                <p className="text-xs leading-relaxed line-clamp-4">{chunk.text}</p>
                <p className="text-[10px] text-muted-foreground/60 mt-1 font-mono">
                  [A:{chunk.paper_id}:{chunk.chunk_id}]
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
