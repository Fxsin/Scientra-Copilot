"use client";

import { Coins } from "lucide-react";

export interface TokenUsage {
  provider?: string;
  model?: string;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  estimated_input_cost_usd?: number | null;
  estimated_output_cost_usd?: number | null;
  estimated_total_cost_usd?: number | null;
  currency?: string;
  source?: string;
  note?: string | null;
}

export const fmt = (n: number | null | undefined) => {
  if (n == null) return "—";
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
  return String(n);
};
export const fmtCost = (n: number | null | undefined) => {
  if (n == null) return "—";
  if (n < 0.0001) return "<$0.0001";
  return "$" + n.toFixed(4);
};

interface TokenUsageBadgeProps {
  tokenUsage?: TokenUsage | null;
  expanded?: boolean;
  onToggle?: () => void;
}

export function TokenUsageBadge({ tokenUsage, expanded, onToggle }: TokenUsageBadgeProps) {
  if (!tokenUsage) return null;
  const { source, total_tokens, estimated_total_cost_usd } = tokenUsage;

  // No-LLM / unavailable — non-interactive
  if (source === "no_llm" || source === "unavailable" || !total_tokens) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-muted/60 px-1.5 py-0.5 text-[10px] text-muted-foreground">
        <Coins className="h-3 w-3 opacity-50" />
        {source === "no_llm" ? "No LLM tokens" : "Tokens N/A"}
      </span>
    );
  }

  const costStr = estimated_total_cost_usd != null ? `≈ ${fmtCost(estimated_total_cost_usd)}` : "";

  return (
    <button
      onClick={onToggle}
      className="inline-flex items-center gap-1 rounded-full border bg-emerald-50/80 px-2 py-0.5 text-[10px] font-medium text-emerald-700 hover:bg-emerald-100 transition-colors dark:bg-emerald-900/20 dark:border-emerald-800/40 dark:text-emerald-400"
    >
      <Coins className="h-3 w-3" />
      {fmt(total_tokens)} tokens
      {costStr && <span className="opacity-60">{costStr}</span>}
      <span className="text-[9px] ml-0.5 opacity-50">{expanded ? "▲" : "▼"}</span>
    </button>
  );
}

interface TokenDetailPanelProps {
  tokenUsage: TokenUsage;
}

export function TokenDetailPanel({ tokenUsage }: TokenDetailPanelProps) {
  const { prompt_tokens, completion_tokens, total_tokens,
    estimated_input_cost_usd, estimated_output_cost_usd, estimated_total_cost_usd,
    provider, model, source, note } = tokenUsage;

  const hasCost = estimated_input_cost_usd != null || estimated_output_cost_usd != null;

  return (
    <div className="mt-2 rounded-lg border bg-muted/30 px-4 py-3 max-w-md text-xs space-y-3">
      {/* Tokens */}
      <div className="space-y-1">
        <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">Tokens</p>
        <Row label="Prompt" value={fmt(prompt_tokens)} />
        <Row label="Completion" value={fmt(completion_tokens)} />
        <Row label="Total" value={fmt(total_tokens)} bold />
      </div>

      {/* Cost */}
      {hasCost && (
        <div className="space-y-1 border-t pt-2">
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">Est. cost (USD)</p>
          {estimated_input_cost_usd != null && <Row label="Input" value={fmtCost(estimated_input_cost_usd)} />}
          {estimated_output_cost_usd != null && <Row label="Output" value={fmtCost(estimated_output_cost_usd)} />}
          {estimated_total_cost_usd != null && <Row label="Total" value={fmtCost(estimated_total_cost_usd)} bold />}
        </div>
      )}

      {/* Provider */}
      <div className="border-t pt-2 text-[9px] text-muted-foreground/60 flex justify-between">
        <span>{provider && model ? `${provider} / ${model}` : provider || model || "—"}</span>
        <span>{source}{note ? ` · ${note}` : ""}</span>
      </div>
    </div>
  );
}

function Row({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className={`flex justify-between ${bold ? "font-semibold" : ""}`}>
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono tabular-nums">{value}</span>
    </div>
  );
}
