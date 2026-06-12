"use client";

import { useState } from "react";
import { Copy, Check, FlaskConical, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentCitation } from "@/lib/types";

const SOURCE_COLORS: Record<string, string> = {
  pdf_asset_chunks: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
  evidence_chunks: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300",
};

const SOURCE_LABELS: Record<string, string> = {
  pdf_asset_chunks: "Asset",
  evidence_chunks: "Evidence",
};

interface AgentCitationCardsProps {
  citations: AgentCitation[];
  highlightedRef: string | null;
  onRefClick: (refId: string) => void;
  contextExists?: boolean;
}

export function AgentCitationCards({
  citations, highlightedRef, onRefClick, contextExists,
}: AgentCitationCardsProps) {
  const [copiedAll, setCopiedAll] = useState(false);

  // Empty state: context exists but no citations
  if ((!citations || citations.length === 0) && contextExists) {
    return (
      <div className="rounded-xl border bg-card/80 p-4 shadow-sm">
        <div className="flex items-start gap-2 text-sm text-muted-foreground">
          <Info className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <p className="font-medium text-foreground/80">No synthesized citations</p>
            <p className="text-xs mt-0.5">
              Retrieved evidence is available in the context panel below.
              Enable "Use LLM" for AI-generated citations.
            </p>
          </div>
        </div>
      </div>
    );
  }

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
    <div className="rounded-xl border bg-card/80 p-4 shadow-sm">
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
              "text-left rounded-lg border p-2.5 hover:bg-muted/50 transition-colors cursor-pointer",
              highlightedRef === c.ref_id && "ring-2 ring-primary border-primary/30"
            )}
          >
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs font-mono font-medium text-primary">
                {c.ref_id}
              </span>
              <span className={cn("rounded px-1.5 py-0.5 text-xs font-medium",
                SOURCE_COLORS[c.source] || "bg-gray-100 text-gray-700")}>
                {SOURCE_LABELS[c.source] || c.source}
              </span>
              <span className="text-[10px] text-muted-foreground">{c.confidence}</span>
              {c.paper_year && (
                <span className="text-[10px] text-muted-foreground ml-auto">{c.paper_year}</span>
              )}
            </div>
            <p className="text-xs font-medium leading-snug line-clamp-1">{c.paper_title}</p>
            <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed line-clamp-3">
              {c.text_snippet}
            </p>
          </button>
        ))}
      </div>
    </div>
  );
}
