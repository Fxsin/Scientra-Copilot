"use client";

import {
  SearchCheck,
  AlertCircle,
  Lightbulb,
  Target,
  Hash,
} from "lucide-react";
import {
  mockResearchGaps,
  type ResearchGapItem,
  type GapType,
} from "@/lib/data/researchIntelligenceMock";

const gapTypeConfig: Record<GapType, { color: string; bg: string }> = {
  "Evidence Gap": { color: "text-red-700", bg: "bg-red-50" },
  "Method Gap": { color: "text-amber-700", bg: "bg-amber-50" },
  "Species / Model Gap": { color: "text-purple-700", bg: "bg-purple-50" },
  "Contradiction Gap": { color: "text-orange-700", bg: "bg-orange-50" },
};

export default function ResearchGapsPage() {
  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <SearchCheck className="size-5 text-blue-500" />
          <h1 className="text-2xl font-bold tracking-tight">Research Gaps</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Identified evidence gaps, method limitations, and contradictions in the
          current literature.
        </p>
      </div>

      <div className="space-y-4">
        {mockResearchGaps.map((gap) => (
          <GapCard key={gap.id} gap={gap} />
        ))}
      </div>
    </div>
  );
}

function GapCard({ gap }: { gap: ResearchGapItem }) {
  const typeCfg = gapTypeConfig[gap.gapType];

  return (
    <div className="rounded-xl border bg-card p-6 shadow-sm space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${typeCfg.color} ${typeCfg.bg}`}
            >
              {gap.gapType}
            </span>
            <span className="text-[11px] font-medium text-emerald-600">
              {gap.opportunityLevel} Opportunity
            </span>
          </div>
          <h3 className="text-lg font-semibold">{gap.title}</h3>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <MetricBadge label="Confidence" value={gap.confidence} color="blue" />
          <MetricBadge label="Impact" value={gap.impact} color="emerald" />
          <MetricBadge label="Feasibility" value={gap.feasibility} color="amber" />
        </div>
      </div>

      <p className="text-sm text-muted-foreground leading-relaxed">
        {gap.description}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-lg bg-blue-50/50 border border-blue-100 p-3">
          <p className="text-xs font-semibold text-blue-800 mb-1">
            <Hash className="size-3 inline mr-1" />
            What is Known
          </p>
          <p className="text-xs text-blue-700 leading-relaxed">
            {gap.knownSummary}
          </p>
        </div>
        <div className="rounded-lg bg-red-50/50 border border-red-100 p-3">
          <p className="text-xs font-semibold text-red-800 mb-1">
            <AlertCircle className="size-3 inline mr-1" />
            What is Missing
          </p>
          <p className="text-xs text-red-700 leading-relaxed">
            {gap.missingSummary}
          </p>
        </div>
      </div>

      <div className="rounded-lg bg-emerald-50/50 border border-emerald-100 p-3">
        <p className="text-xs font-semibold text-emerald-800 mb-1 flex items-center gap-1">
          <Lightbulb className="size-3" />
          Suggested Next Step
        </p>
        <p className="text-xs text-emerald-700 leading-relaxed">
          {gap.suggestedNextStep}
        </p>
      </div>

      <div className="flex items-center gap-4 text-xs text-muted-foreground border-t pt-3">
        <span>
          <Target className="size-3 inline mr-1" />
          {gap.evidenceBasis.paperCount} papers
        </span>
        <span>{gap.evidenceBasis.directEvidenceCount} direct evidence</span>
        <span>{gap.evidenceBasis.indirectEvidenceCount} indirect</span>
        {gap.evidenceBasis.contradictionCount > 0 && (
          <span className="text-amber-600">
            {gap.evidenceBasis.contradictionCount} contradictions
          </span>
        )}
      </div>
    </div>
  );
}

function MetricBadge({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: "blue" | "emerald" | "amber";
}) {
  const colors = {
    blue: "bg-blue-50 text-blue-700",
    emerald: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
  };
  return (
    <div className="text-center">
      <div
        className={`text-xs font-bold rounded-full size-10 flex items-center justify-center ${colors[color]}`}
      >
        {value}
      </div>
      <p className="text-[10px] text-muted-foreground mt-0.5">{label}</p>
    </div>
  );
}
