import { Lightbulb } from "lucide-react";
import type { ResearchTopic } from "@/lib/types";

interface GapCardProps {
  topic: ResearchTopic;
}

export function GapCard({ topic }: GapCardProps) {
  return (
    <div className="rounded-xl border border-destructive/15 bg-destructive/3 p-4 shadow-sm">
      <div className="flex items-start gap-2">
        <Lightbulb className="size-4 text-amber-500 shrink-0 mt-0.5" strokeWidth={2} />
        <div className="flex-1">
          <span className="text-sm font-semibold text-foreground">{topic.name}</span>
          <p className="mt-1 text-xs text-muted-foreground">{topic.opportunity ?? topic.summary}</p>
          {topic.connected_to && topic.connected_to.length > 0 && (
            <div className="mt-2 flex items-center gap-1 text-[10px] text-muted-foreground">
              Connected to: {topic.connected_to.join(", ")}
            </div>
          )}
        </div>
        <span className="font-mono text-xs text-muted-foreground">{topic.paper_count}p</span>
      </div>
    </div>
  );
}
