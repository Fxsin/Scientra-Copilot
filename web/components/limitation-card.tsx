import { AlertCircle } from "lucide-react";

interface LimitationCardProps {
  limitations: string[];
}

export function LimitationCard({ limitations }: LimitationCardProps) {
  const isMissing =
    limitations.length === 1 && limitations[0] === "Not explicitly reported.";

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <div className="flex size-7 items-center justify-center rounded-md bg-amber-100 text-amber-700">
          <AlertCircle className="size-3.5" strokeWidth={2} />
        </div>
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Limitations
        </span>
      </div>
      {isMissing ? (
        <p className="text-sm text-muted-foreground italic">
          Not explicitly reported.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {limitations.map((lim, i) => (
            <li key={i} className="flex gap-2 text-sm text-foreground/80">
              <span className="text-muted-foreground mt-1">•</span>
              <span className="leading-relaxed">{lim}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
