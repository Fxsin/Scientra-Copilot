"use client";

import { useState } from "react";
import { Settings2, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentAnswerMode } from "@/lib/types";

interface AgentAdvancedOptionsProps {
  answerMode: AgentAnswerMode;
  setAnswerMode: (v: AgentAnswerMode) => void;
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

const MODE_OPTIONS: { value: AgentAnswerMode; label: string; desc: string }[] = [
  { value: "auto", label: "Auto", desc: "LLM if configured; otherwise evidence fallback." },
  { value: "llm", label: "LLM synthesis", desc: "Use backend LLM API to synthesize a cited answer." },
  { value: "evidence_only", label: "Evidence-only", desc: "Show retrieved evidence summary only. No API call." },
];

export function AgentAdvancedOptions({
  answerMode, setAnswerMode,
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
        <div className="mt-3 p-3 rounded-lg bg-muted/50 space-y-3">
          {/* Answer Mode */}
          <div>
            <span className="text-xs font-medium">Answer Mode</span>
            <div className="mt-1.5 grid grid-cols-3 gap-1.5">
              {MODE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setAnswerMode(opt.value)}
                  className={cn(
                    "rounded-lg border px-2 py-1.5 text-left transition-colors",
                    answerMode === opt.value
                      ? "border-primary/40 bg-primary/5 text-primary"
                      : "border-transparent hover:bg-muted text-muted-foreground"
                  )}
                >
                  <div className="text-xs font-medium">{opt.label}</div>
                  <div className="text-[10px] leading-tight opacity-70 mt-0.5">{opt.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Other options */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <label className="flex items-center gap-1.5 text-xs">
              <input type="checkbox" checked={includeAssets} onChange={(e) => setIncludeAssets(e.target.checked)} className="rounded" />
              Assets
            </label>
            <label className="flex items-center gap-1.5 text-xs">
              <input type="checkbox" checked={includeEvidence} onChange={(e) => setIncludeEvidence(e.target.checked)} className="rounded" />
              Evidence
            </label>
            <label className="flex items-center gap-1.5 text-xs">
              <input type="checkbox" checked={returnContext} onChange={(e) => setReturnContext(e.target.checked)} className="rounded" />
              Context
            </label>
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-muted-foreground">top_k:</span>
              <input type="number" value={topK} onChange={(e) => setTopK(Math.max(1, Math.min(50, +e.target.value || 10)))} className="w-14 rounded border px-1.5 py-0.5 text-xs bg-background" min={1} max={50} />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-muted-foreground">Types:</span>
            {["section", "method", "result", "claim", "figure"].map((ct) => (
              <button key={ct} onClick={() => toggleChunkType(ct)} className={cn("rounded-full border px-2 py-0.5 transition-colors", chunkTypes.includes(ct) ? "bg-primary/10 border-primary/30 text-primary" : "text-muted-foreground hover:text-foreground")}>{ct}</button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
