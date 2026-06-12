"use client";

import { AlertTriangle, Info } from "lucide-react";

interface AgentWarningsProps {
  response?: {
    answer?: string;
    model?: string;
    elapsed_ms?: number;
    citations?: Array<unknown>;
    context_used?: number;
  } | null;
  error?: string | null;
  answerMode?: string;
}

function hasLlmError(answer: string): boolean {
  const lower = answer.toLowerCase();
  return lower.includes("anthropic_api_key not set")
    || lower.includes("llm synthesis is unavailable")
    || lower.includes("context was retrieved successfully but llm")
    || lower.includes("agent error");
}

export function AgentWarnings({ response, error, answerMode }: AgentWarningsProps) {
  const warnings: string[] = [];
  const isFallback = response?.model?.includes("evidence-only-fallback") || false;

  if (response) {
    const answerLower = (response.answer || "").toLowerCase();
    const isLlmError = hasLlmError(response.answer || "");
    const hasContext = (response.context_used ?? 0) > 0;

    if (answerMode === "evidence_only") {
      warnings.push("Evidence-only mode: no LLM API was called. Showing retrieved evidence summary.");
    } else if (isLlmError || isFallback) {
      if (answerMode === "llm") {
        warnings.push("LLM synthesis was requested, but the backend LLM API is unavailable. Showing retrieved evidence instead.");
      } else {
        warnings.push("LLM API is not configured. Run: python Scripts/setup_llm.py to set up DeepSeek or Anthropic. Showing evidence fallback for now.");
      }
    }

    if (answerLower.includes("insufficient evidence")) {
      warnings.push("Insufficient evidence in current database for this question.");
    }
    if (answerLower.includes("outside the scope")) {
      warnings.push("This question is outside the scope of this literature database.");
    }
    if ((response.elapsed_ms ?? 0) > 20000) {
      warnings.push(`Response took ${((response.elapsed_ms ?? 0) / 1000).toFixed(1)}s. Consider reducing top_k.`);
    }
  }

  if (!warnings.length && !error) return null;

  return (
    <>
      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50/70 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/20 dark:text-red-300">
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <p className="font-medium">Connection Error</p>
            <p className="text-xs opacity-80 mt-0.5">{error}</p>
          </div>
        </div>
      )}
      {warnings.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-200/60 bg-amber-50/70 p-3 text-sm text-amber-800 dark:border-amber-800/60 dark:bg-amber-950/20 dark:text-amber-300">
          <Info className="h-4 w-4 mt-0.5 shrink-0" />
          <div className="space-y-1">
            {warnings.map((w, i) => <p key={i}>{w}</p>)}
          </div>
        </div>
      )}
    </>
  );
}
