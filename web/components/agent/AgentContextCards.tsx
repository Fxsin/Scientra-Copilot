"use client";

import { useState } from "react";
import { Search, ChevronDown, ChevronUp, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentContextItem } from "@/lib/types";

const CHUNK_TYPE_COLORS: Record<string, string> = {
  section: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  method: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  result: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  claim: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
  pdf_asset_chunks: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
  evidence_chunks: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300",
};

const SOURCE_LABELS: Record<string, string> = {
  pdf_asset_chunks: "Asset",
  evidence_chunks: "Evidence",
};

interface AgentContextCardsProps {
  chunks: AgentContextItem[];
  highlightedRef: string | null;
  defaultOpen?: boolean;
}

function ContextCard({
  chunk, index, highlightedRef,
}: {
  chunk: AgentContextItem;
  index: number;
  highlightedRef: string | null;
}) {
  const [expanded, setExpanded] = useState(false);
  const refId = `Ref:${index + 1}`;
  const anchorId = `ctx-${refId.replace(/[^a-zA-Z0-9]/g, "-")}`;
  const isHighlighted = highlightedRef === refId;
  const sourceLabel = SOURCE_LABELS[chunk.source] || chunk.source;
  const scorePct = chunk.score != null ? `${((1 - Math.min(chunk.score, 1)) * 100).toFixed(0)}%` : "—";
  const pidShort = chunk.paper_id.length > 30
    ? chunk.paper_id.slice(0, 16) + "..." + chunk.paper_id.slice(-12)
    : chunk.paper_id;
  const citationKey = `[A:...${chunk.paper_id.slice(-12)}:${(chunk.chunk_id || "").slice(-8)}]`;

  return (
    <div
      id={anchorId}
      className={cn(
        "rounded-lg border p-3 text-sm transition-colors",
        isHighlighted && "ring-2 ring-primary border-primary/30 bg-primary/5"
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
          {sourceLabel}
        </span>
        <span className="text-xs text-muted-foreground ml-auto tabular-nums">
          {scorePct}
        </span>
      </div>
      <p className="text-[10px] text-muted-foreground/60 mb-1 font-mono truncate">
        {pidShort}
      </p>
      <p className={cn("text-xs leading-relaxed", expanded ? "" : "line-clamp-3")}>
        {chunk.text}
      </p>
      {chunk.text.length > 200 && (
        <button
          onClick={(e) => { e.preventDefault(); setExpanded(!expanded); }}
          className="mt-1 text-[10px] text-primary/70 hover:text-primary transition-colors flex items-center gap-0.5"
        >
          {expanded ? "Show less" : "Show more"}
          <ChevronRight className={cn("h-3 w-3 transition-transform", expanded && "rotate-90")} />
        </button>
      )}
      <p className="text-[10px] text-muted-foreground/40 mt-1 font-mono truncate">
        {citationKey}
      </p>
    </div>
  );
}

export function AgentContextCards({ chunks, highlightedRef, defaultOpen = true }: AgentContextCardsProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [showAll, setShowAll] = useState(false);

  if (!chunks || chunks.length === 0) return null;

  const PAGE_SIZE = 5;
  const hasMore = chunks.length > PAGE_SIZE;
  const displayChunks = showAll || !hasMore ? chunks : chunks.slice(0, PAGE_SIZE);

  return (
    <div className="rounded-xl border bg-card/80 p-4 shadow-sm">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-sm font-semibold w-full text-left"
      >
        <Search className="h-4 w-4 text-primary" />
        Retrieved Context ({chunks.length} chunks)
        {open ? <ChevronUp className="h-4 w-4 ml-auto" /> : <ChevronDown className="h-4 w-4 ml-auto" />}
      </button>
      {open && (
        <div className="mt-3 grid gap-2">
          {displayChunks.map((chunk, i) => (
            <ContextCard
              key={chunk.chunk_id || i}
              chunk={chunk}
              index={showAll || !hasMore ? i : i}
              highlightedRef={highlightedRef}
            />
          ))}
          {hasMore && !showAll && (
            <button
              onClick={() => setShowAll(true)}
              className="text-xs text-primary/70 hover:text-primary transition-colors py-1 text-center"
            >
              Show all {chunks.length} retrieved chunks
            </button>
          )}
          {hasMore && showAll && (
            <button
              onClick={() => setShowAll(false)}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors py-1 text-center"
            >
              Show fewer
            </button>
          )}
        </div>
      )}
    </div>
  );
}
