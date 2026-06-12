"use client";

import { AlertTriangle, Info } from "lucide-react";

interface AgentWarningsProps {
  /** Build warnings from the response and current settings */
  response?: {
    answer?: string;
    model?: string;
    elapsed_ms?: number;
    citations?: Array<unknown>;
    context_used?: number;
  } | null;
  error?: string | null;
  useLlm?: boolean;
}

export function AgentWarnings({ response, error, useLlm }: AgentWarningsProps) {
  const warnings: string[] = [];

  if (response) {
    const answerLower = (response.answer || "").toLowerCase();
    if (!response.citations?.length && (response.context_used ?? 0) > 0) {
      warnings.push("Retrieved context available, but no citations were generated.");
    }
    if (answerLower.includes("insufficient evidence")) {
      warnings.push("Insufficient evidence in current database.");
    }
    if (answerLower.includes("outside the scope")) {
      warnings.push("Question is outside the scope of this literature database.");
    }
    if (response.model?.includes("no LLM") || response.model?.includes("extractive")) {
      warnings.push("Extractive mode — no LLM synthesis. Enable 'Use LLM' for AI-generated answers.");
    }
    if ((response.elapsed_ms ?? 0) > 20000) {
      warnings.push(`Slow response (${((response.elapsed_ms ?? 0) / 1000).toFixed(1)}s). Consider reducing top_k.`);
    }
  }

  if (!warnings.length && !error) return null;

  return (
    <>
      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300">
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <p className="font-medium">Error</p>
            <p className="text-xs opacity-80">{error}</p>
          </div>
        </div>
      )}
      {warnings.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
          <Info className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            {warnings.map((w, i) => (
              <p key={i} className={i > 0 ? "mt-1" : ""}>{w}</p>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
