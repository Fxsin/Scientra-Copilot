"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SearchCheck, AlertCircle, Lightbulb, Target, Loader2 } from "lucide-react";
import { getResearchGaps } from "@/lib/api";
import type { ResearchGapsResponse, ResearchGap } from "@/lib/types";

const gapColors: Record<string, string> = {
  "Evidence Gap": "bg-red-50 text-red-700 border-red-200",
  "Method Gap": "bg-amber-50 text-amber-700 border-amber-200",
};

export default function ResearchGapsPage() {
  const router = useRouter();
  const [data, setData] = useState<ResearchGapsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getResearchGaps()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Skeleton />;
  if (error) return <ErrorState msg={error} />;
  if (!data || data.status === "cache_missing") return <EmptyState />;

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-16">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <SearchCheck className="size-5 text-blue-500" />
          <h1 className="text-2xl font-bold tracking-tight text-slate-800">Research Gaps</h1>
        </div>
        <p className="text-sm text-slate-400">
          Evidence gaps, method limitations, and under-represented research areas detected from {data.paper_count} papers.
        </p>
      </div>

      {data.gaps.length === 0 ? (
        <div className="rounded-xl border border-slate-200/50 bg-white p-8 text-center">
          <p className="text-sm text-slate-400">No significant gaps detected in the current literature collection.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {data.gaps.map((gap) => <GapCard key={gap.id} gap={gap} />)}
        </div>
      )}

      <p className="text-center text-[9px] text-slate-300">
        Detected from Research Map cache · {data.gap_count} gaps found
      </p>
    </div>
  );
}

function GapCard({ gap }: { gap: ResearchGap }) {
  const colors = gapColors[gap.gap_type] || gapColors["Evidence Gap"];

  const confidenceLabel = gap.confidence >= 80 ? "High" : gap.confidence >= 60 ? "Medium" : "Low";
  const confidenceColor = gap.confidence >= 80 ? "bg-emerald-50 text-emerald-600"
    : gap.confidence >= 60 ? "bg-amber-50 text-amber-600" : "bg-slate-100 text-slate-500";

  return (
    <div className="rounded-xl border border-slate-200/50 bg-white p-5 space-y-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold border ${colors}`}>{gap.gap_type}</span>
            {gap.facet_label && <span className="text-[10px] text-slate-400">{gap.facet_label}</span>}
            {gap.subtopic && <span className="text-[10px] text-slate-400">· {gap.subtopic.slice(0, 40)}</span>}
          </div>
          <h3 className="text-base font-semibold text-slate-800">{gap.title}</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${confidenceColor}`}>{confidenceLabel}</span>
          {gap.paper_count !== undefined && <span className="text-[10px] text-slate-400">{gap.paper_count} papers</span>}
        </div>
      </div>

      <p className="text-sm text-slate-500 leading-relaxed">{gap.description}</p>

      {gap.suggested_action && (
        <div className="flex items-start gap-2 rounded-lg bg-blue-50/50 border border-blue-100 p-3">
          <Lightbulb className="size-4 text-blue-500 shrink-0 mt-0.5" />
          <p className="text-[11px] text-blue-700">{gap.suggested_action}</p>
        </div>
      )}
    </div>
  );
}

function Skeleton() {
  return <div className="space-y-4 animate-pulse max-w-5xl mx-auto">{Array.from({length:4}).map((_,i)=><div key={i} className="h-32 bg-slate-50 rounded-xl"/>)}</div>;
}
function ErrorState({ msg }: { msg: string }) {
  return <div className="max-w-5xl mx-auto py-16 text-center"><AlertCircle className="size-8 text-red-300 mx-auto mb-2"/><p className="text-sm text-red-500">{msg}</p></div>;
}
function EmptyState() {
  return <div className="max-w-5xl mx-auto py-16 text-center"><SearchCheck className="size-8 text-slate-300 mx-auto mb-2"/><p className="text-sm text-slate-400">Research Map cache not available. Rebuild research map first.</p></div>;
}
