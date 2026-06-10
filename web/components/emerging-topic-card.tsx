import { TrendingUp } from "lucide-react";
import type { ResearchTopic } from "@/lib/types";

interface EmergingTopicCardProps {
  topic: ResearchTopic;
}

export function EmergingTopicCard({ topic }: EmergingTopicCardProps) {
  return (
    <div className="rounded-xl border border-accent/20 bg-accent/5 p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <TrendingUp className="size-4 text-accent-foreground" strokeWidth={2} />
          <span className="text-sm font-semibold text-foreground">{topic.name}</span>
        </div>
        <span className="text-[10px] font-medium text-accent-foreground">
          {topic.growth_rate}
        </span>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">{topic.summary}</p>
    </div>
  );
}
