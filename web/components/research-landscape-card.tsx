// @ts-nocheck
import { CheckCircle2 } from "lucide-react";
import type { ResearchTopic } from "@/lib/types";

interface ResearchLandscapeCardProps {
  topic: ResearchTopic;
}

export function ResearchLandscapeCard({ topic }: ResearchLandscapeCardProps) {
  return (
    <div className="rounded-xl border border-secondary/20 bg-secondary/5 p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="size-4 text-secondary" strokeWidth={2} />
          <span className="text-sm font-semibold text-foreground">{topic.name}</span>
        </div>
        <span className="text-[10px] font-medium uppercase text-secondary">
          {topic.confidence ?? "mature"}
        </span>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">{topic.summary}</p>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-muted-foreground">
        {topic.year_span && <span>{topic.year_span}y span ({topic.year_range})</span>}
        {topic.method_diversity !== undefined && <span>{topic.method_diversity} methods</span>}
      </div>
    </div>
  );
}
