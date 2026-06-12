"use client";

import { useState } from "react";
import { Copy, Check, FlaskConical } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentCitation } from "@/lib/types";

const CHUNK_TYPE_COLORS: Record<string, string> = {
  section: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  method: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  result: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  claim: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
  pdf_asset_chunks: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
  evidence_chunks: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300",
};

interface AgentCitationCardsProps {
  citations: AgentCitation[];
  highlightedRef: string | null;
  onRefClick: (refId: string) => void;
}

export function AgentCitationCards({ citations, highlightedRef, onRefClick }: AgentCitationCardsProps) {
  const [copiedAll, setCopiedAll] = useState(false);

  if (!citations || citations.length === 0) return null;

  const handleCopyAll = async () => {
    const text = citations.map(c =>
      `[${c.ref_id}] ${c.paper_title} (${c.paper_year ?? "?"}) — ${c.text_snippet}`
    ).join("\n");
    await navigator.clipboard.writeText(text);
    setCopiedAll(true);
    setTimeout(() => setCopiedAll(false), 2000);
  };

  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <FlaskConical className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">Citations ({citations.length})</h3>
        <button
          onClick={handleCopyAll}
          className="ml-auto flex items-center gap-1 rounded border px-2 py-0.5 text-xs hover:bg-muted transition-colors"
          aria-label="Copy all citations"
        >
          {copiedAll ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
          {copiedAll ? "Copied" : "Copy all"}
        </button>
      </div>
      <div className="grid gap-2">
        {citations.map((c, i) => (
          <button
            key={i}
            onClick={() => onRefClick(c.ref_id)}
            className={cn(
              "text-left rounded-lg border p-3 hover:bg-muted/50 transition-colors cursor-pointer",
              highlightedRef === c.ref_id && "ring-2 ring-primary border-primary/30"
            )}
          >
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs font-mono font-medium text-primary">
                {c.ref_id}
              </span>
              <span className={cn("rounded px-1.5 py-0.5 text-xs font-medium",
                CHUNK_TYPE_COLORS[c.source] || "bg-gray-100 text-gray-700")}>
                {c.source}
              </span>
              <span className="text-xs text-muted-foreground">{c.confidence}</span>
              {c.paper_year && (
                <span className="text-xs text-muted-foreground ml-auto">{c.paper_year}</span>
              )}
            </div>
            <p className="text-xs font-medium truncate">{c.paper_title}</p>
            <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{c.text_snippet}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
