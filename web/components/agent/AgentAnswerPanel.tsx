"use client";

import { useRef, useState, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import { Copy, Check, Sparkles, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { TokenUsageBadge, TokenDetailPanel } from "./TokenUsageBadge";
import type { TokenUsage } from "./TokenUsageBadge";

interface AgentAnswerPanelProps {
  answer: string;
  intent: string;
  model: string;
  elapsedMs: number;
  contextUsed: number;
  papersCited: number;
  highlightedRef: string | null;
  onRefClick: (refId: string) => void;
  answerMode?: string;
  tokenUsage?: Record<string, unknown> | null;
}

const CHUNK_TYPE_COLORS: Record<string, string> = {
  section: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  method: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  result: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  claim: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
};

function isLlmUnavailable(answer: string): boolean {
  const lower = answer.toLowerCase();
  return (
    lower.includes("anthropic_api_key not set") ||
    lower.includes("llm synthesis is unavailable") ||
    lower.includes("context was retrieved successfully but llm") ||
    lower.includes("agent error")
  );
}

const FALLBACK_MESSAGE = `Scientra retrieved relevant evidence from your literature library, but LLM synthesis is currently unavailable.

**You can still inspect the retrieved context below**, or disable "Use LLM" in Advanced Options to switch to extractive mode (no API key required).

---

*Retrieved evidence is shown in the context panel below.*`;

export function AgentAnswerPanel({
  answer, intent, model, elapsedMs, contextUsed, papersCited,
  highlightedRef, onRefClick, answerMode, tokenUsage,
}: AgentAnswerPanelProps) {
  const [copied, setCopied] = useState(false);
  const [tokenExpanded, setTokenExpanded] = useState(false);
  const answerRef = useRef<HTMLDivElement>(null);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Determine display mode
  const isLlmError = isLlmUnavailable(answer);
  const isFallback = model.includes("evidence-only-fallback") || model.includes("extractive");
  const isLlmSuccess = !isLlmError && !isFallback && !model.includes("no LLM");
  const effectiveAnswer = isLlmError ? FALLBACK_MESSAGE : answer;

  // Mode badge
  let modeLabel: string;
  if (answerMode === "evidence_only") {
    modeLabel = "Evidence-only mode";
  } else if (isLlmSuccess) {
    modeLabel = answerMode === "auto" ? "Auto → LLM synthesis" : "LLM synthesis";
  } else if (isFallback) {
    modeLabel = answerMode === "llm" ? "LLM unavailable — evidence retrieved" : "Auto → Evidence fallback";
  } else {
    modeLabel = "Evidence-only mode";
  }
  const ModeIcon = isLlmSuccess ? Sparkles : Search;

  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-4 text-xs text-muted-foreground flex-wrap overflow-visible">
        <span className={cn(
          "inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium",
          isLlmError || isFallback
            ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300"
            : isLlmSuccess
            ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300"
            : "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300"
        )}>
          <ModeIcon className="h-3 w-3" />
          {modeLabel}
        </span>
        <span className="rounded-full bg-primary/10 px-2 py-0.5 font-medium text-primary">
          {intent || "hybrid"}
        </span>
        <span>{elapsedMs?.toFixed(0)}ms</span>
        <span>{contextUsed} chunks</span>
        <span>{papersCited} papers</span>
        <TokenUsageBadge
          tokenUsage={tokenUsage as Record<string,unknown> | null}
          expanded={tokenExpanded}
          onToggle={() => setTokenExpanded(!tokenExpanded)}
        />
        <button
          onClick={handleCopy}
          className="ml-auto flex items-center gap-1 rounded border px-2 py-0.5 text-xs hover:bg-muted transition-colors"
          aria-label="Copy answer"
        >
          {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>

      {/* Inline token detail panel */}
      {tokenExpanded && tokenUsage && (
        <TokenDetailPanel tokenUsage={tokenUsage as TokenUsage} />
      )}

      <hr className="mb-4 mt-3 border-border/40" />
      <div ref={answerRef} className="prose prose-sm dark:prose-invert max-w-3xl leading-7 text-[15px]">
        <ReactMarkdown
          components={{
            h2: ({ children }) => <h2 className="text-lg font-semibold mt-6 mb-2 text-foreground border-b pb-1">{children}</h2>,
            h3: ({ children }) => <h3 className="text-base font-semibold mt-4 mb-1.5 text-foreground/90">{children}</h3>,
            p: ({ children }) => {
              const text = String(children);
              if (typeof text === "string" && /\[Ref:\d+\]/.test(text)) {
                const parts = text.split(/(\[Ref:\d+\])/g);
                return <p className="my-1.5">{parts.map((part, i) =>
                  /\[Ref:\d+\]/.test(part) ? (
                    <button key={i} onClick={() => onRefClick(part)}
                      className={cn("inline-flex items-center rounded bg-primary/10 px-1.5 py-0.5 text-[11px] font-mono text-primary hover:bg-primary/20 cursor-pointer transition-colors align-middle", highlightedRef === part && "ring-2 ring-primary")}>
                      {part}
                    </button>
                  ) : <span key={i}>{part}</span>
                )}</p>;
              }
              return <p className="my-1.5">{children}</p>;
            },
            strong: ({ children }) => {
              const text = String(children);
              if (text.startsWith("Claim:") || text.startsWith("Current evidence:") || text.startsWith("Why stronger") || text.startsWith("Missing evidence:") || text.startsWith("Sources:")) {
                return <span className="inline-block text-[11px] font-medium text-primary/80 bg-primary/5 rounded px-1.5 py-0.5 mr-1">{children}</span>;
              }
              return <strong className="font-semibold">{children}</strong>;
            },
            ul: ({ children }) => <ul className="my-2 space-y-1 list-disc pl-5">{children}</ul>,
            li: ({ children }) => <li className="text-sm">{children}</li>,
          }}>
          {effectiveAnswer}
        </ReactMarkdown>
      </div>
    </div>
  );
}
