import { Star } from "lucide-react";

interface CoreFindingCardProps {
  findings: string[];
}

export function CoreFindingCard({ findings }: CoreFindingCardProps) {
  if (findings.length === 0) return null;

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <div className="flex size-7 items-center justify-center rounded-md bg-secondary/10 text-secondary">
          <Star className="size-3.5" strokeWidth={2} />
        </div>
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Core Findings
        </span>
      </div>
      <div className="flex flex-col gap-3">
        {findings.map((finding, i) => (
          <div key={i} className="flex gap-3">
            <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-bold text-muted-foreground mt-0.5">
              {i + 1}
            </span>
            <p className="text-sm text-foreground/85 leading-relaxed">
              {finding}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
