import { Lightbulb } from "lucide-react";

interface KnowledgeOverviewCardProps {
  overview: string;
}

export function KnowledgeOverviewCard({ overview }: KnowledgeOverviewCardProps) {
  return (
    <div className="rounded-xl border border-accent/30 bg-accent/5 p-5 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-accent/20 text-accent-foreground">
          <Lightbulb className="size-4" strokeWidth={1.5} />
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold uppercase tracking-wider text-accent-foreground/70">
            Knowledge Overview
          </span>
          <p className="text-sm font-medium text-foreground leading-relaxed">
            {overview}
          </p>
        </div>
      </div>
    </div>
  );
}
