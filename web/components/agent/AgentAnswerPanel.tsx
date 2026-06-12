"use client";

import { useRef, useState, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import { Copy, Check, Sparkles, Search } from "lucide-react";
import { cn } from "@/lib/utils";

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
  highlightedRef, onRefClick, answerMode,
}: AgentAnswerPanelProps) {
  const [copied, setCopied] = useState(false);
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
      <div className="flex items-center gap-2 mb-3 text-xs text-muted-foreground flex-wrap">
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
        <button
          onClick={handleCopy}
          className="ml-auto flex items-center gap-1 rounded border px-2 py-0.5 text-xs hover:bg-muted transition-colors"
          aria-label="Copy answer"
        >
          {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <div ref={answerRef} className="prose prose-sm dark:prose-invert max-w-none leading-relaxed">
        <ReactMarkdown
          components={{
            p: ({ children }) => {
              const text = String(children);
              if (typeof text === "string" && /\[Ref:\d+\]/.test(text)) {
                const parts = text.split(/(\[Ref:\d+\])/g);
                return (
                  <p>
                    {parts.map((part, i) =>
                      /\[Ref:\d+\]/.test(part) ? (
                        <button
                          key={i}
                          onClick={() => onRefClick(part)}
                          className={cn(
                            "inline rounded bg-primary/10 px-1 text-xs font-mono text-primary hover:bg-primary/20 cursor-pointer transition-colors",
                            highlightedRef === part && "ring-2 ring-primary"
                          )}
                        >
                          {part}
                        </button>
                      ) : (
                        <span key={i}>{part}</span>
                      )
                    )}
                  </p>
                );
              }
              return <p>{children}</p>;
            },
          }}
        >
          {effectiveAnswer}
        </ReactMarkdown>
      </div>
    </div>
  );
}
