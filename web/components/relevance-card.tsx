import { Target } from "lucide-react";
import type { RelevanceMatch } from "@/lib/knowledge";

interface RelevanceCardProps {
  matches: RelevanceMatch[];
}

export function RelevanceCard({ matches }: RelevanceCardProps) {
  if (matches.length === 0) return null;

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <div className="flex size-7 items-center justify-center rounded-md bg-emerald-100 text-emerald-700">
          <Target className="size-3.5" strokeWidth={2} />
        </div>
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Relevance to My Research
        </span>
      </div>
      <div className="flex flex-col gap-3">
        {matches.map((match, i) => (
          <div
            key={i}
            className="flex flex-col gap-1 rounded-lg border border-border bg-muted/30 p-3"
          >
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-foreground">
                {match.keyword}
              </span>
              <div className="flex gap-1">
                {match.matchedIn.map((src) => (
                  <span
                    key={src}
                    className="inline-flex rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-800"
                  >
                    {src}
                  </span>
                ))}
              </div>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              {match.reason}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
