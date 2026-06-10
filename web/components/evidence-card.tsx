import { TagBadge } from "@/components/tag-badge";
import type { TagEvidence } from "@/lib/types";

interface EvidenceCardProps {
  tagName: string;
  evidence: TagEvidence;
}

export function EvidenceCard({ tagName, evidence }: EvidenceCardProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-3 shadow-sm">
      {/* Tag name + category */}
      <div className="flex items-center gap-2 mb-2">
        <TagBadge label={tagName} variant={evidence.category} />
        {evidence.confidence && (
          <span className="text-[10px] font-medium text-muted-foreground uppercase">
            {evidence.confidence} confidence
          </span>
        )}
        {evidence.score !== undefined && (
          <span className="ml-auto font-mono text-[11px] text-muted-foreground">
            score: {evidence.score}
          </span>
        )}
      </div>

      {/* Matched terms */}
      {evidence.matched_terms && evidence.matched_terms.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1.5">
          {evidence.matched_terms.map((term) => (
            <span
              key={term}
              className="inline-flex rounded bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground"
            >
              {term}
            </span>
          ))}
        </div>
      )}

      {/* Sources */}
      {evidence.source && evidence.source.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {evidence.source.map((src) => (
            <span
              key={src}
              className="inline-flex rounded-full bg-secondary/10 px-1.5 py-0.5 text-[9px] font-medium text-secondary"
            >
              {src}
            </span>
          ))}
        </div>
      )}

      {/* Reason / excerpt */}
      {evidence.reason && (
        <p className="mt-2 text-[11px] text-muted-foreground leading-relaxed line-clamp-3">
          {evidence.reason}
        </p>
      )}
    </div>
  );
}
