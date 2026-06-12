"use client";

import { useState } from "react";
import { Settings2, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";

interface AgentAdvancedOptionsProps {
  useLlm: boolean;
  setUseLlm: (v: boolean) => void;
  includeAssets: boolean;
  setIncludeAssets: (v: boolean) => void;
  includeEvidence: boolean;
  setIncludeEvidence: (v: boolean) => void;
  returnContext: boolean;
  setReturnContext: (v: boolean) => void;
  topK: number;
  setTopK: (v: number) => void;
  chunkTypes: string[];
  toggleChunkType: (ct: string) => void;
}

export function AgentAdvancedOptions({
  useLlm, setUseLlm,
  includeAssets, setIncludeAssets,
  includeEvidence, setIncludeEvidence,
  returnContext, setReturnContext,
  topK, setTopK,
  chunkTypes, toggleChunkType,
}: AgentAdvancedOptionsProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-3">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <Settings2 className="h-3 w-3" />
        Advanced Options
        {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>
      {open && (
        <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3 p-3 rounded-lg bg-muted/50">
          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} className="rounded" />
            Use LLM
          </label>
          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={includeAssets} onChange={(e) => setIncludeAssets(e.target.checked)} className="rounded" />
            Include Assets
          </label>
          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={includeEvidence} onChange={(e) => setIncludeEvidence(e.target.checked)} className="rounded" />
            Include Evidence
          </label>
          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={returnContext} onChange={(e) => setReturnContext(e.target.checked)} className="rounded" />
            Return Context
          </label>
          <div className="flex items-center gap-2 text-xs">
            <span className="text-muted-foreground">top_k:</span>
            <input
              type="number" value={topK}
              onChange={(e) => setTopK(Math.max(1, Math.min(50, +e.target.value || 10)))}
              className="w-14 rounded border px-1.5 py-0.5 text-xs bg-background" min={1} max={50}
            />
          </div>
          <div className="col-span-2 flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-muted-foreground">Types:</span>
            {["section", "method", "result", "claim"].map((ct) => (
              <button
                key={ct}
                onClick={() => toggleChunkType(ct)}
                className={cn(
                  "rounded-full border px-2 py-0.5 transition-colors",
                  chunkTypes.includes(ct)
                    ? "bg-primary/10 border-primary/30 text-primary"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {ct}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
