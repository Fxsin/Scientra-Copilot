import { ExternalLink } from "lucide-react";
import { TagBadge } from "@/components/tag-badge";
import type { PaperMetadata, PaperTags } from "@/lib/types";

interface MetadataPanelProps {
  metadata: PaperMetadata | null;
  tags: PaperTags | null;
}

const METADATA_FIELDS: { key: string; label: string }[] = [
  { key: "title", label: "Title" },
  { key: "year", label: "Year" },
  { key: "journal", label: "Journal" },
  { key: "abstract_source", label: "Abstract Source" },
  { key: "parse_status", label: "Parse Status" },
];

function sd(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

export function MetadataPanel({ metadata, tags }: MetadataPanelProps) {
  const md: Record<string, unknown> = metadata?.metadata ?? {};
  const doi = sd(md.doi);
  const hasOutputs =
    md.outputs !== null && md.outputs !== undefined && typeof md.outputs === "object";
  const outputs =
    hasOutputs ? (md.outputs as Record<string, unknown>) : null;

  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-foreground mb-3">Metadata</h3>
        <dl className="space-y-3">
          {METADATA_FIELDS.map(({ key, label }) => {
            const v = sd(md[key]);
            if (!v) return null;
            return (
              <div key={key} className="flex flex-col gap-0.5">
                <dt className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {label}
                </dt>
                <dd className="text-xs text-foreground/85 break-words">
                  {key === "title" ? (
                    <span className="line-clamp-3">{v}</span>
                  ) : (
                    v
                  )}
                </dd>
              </div>
            );
          })}

          {doi ? (
            <div className="flex flex-col gap-0.5">
              <dt className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                DOI
              </dt>
              <dd>
                <a
                  href={`https://doi.org/${doi}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-mono text-xs text-accent-foreground hover:underline"
                >
                  {doi}
                  <ExternalLink className="size-3" />
                </a>
              </dd>
            </div>
          ) : null}

          {outputs ? (
            <>
              <div className="border-t border-border pt-2" />
              <dt className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Processing
              </dt>
              {Object.entries(outputs).map(([k, v]) => (
                <dd
                  key={k}
                  className="text-[10px] text-muted-foreground truncate"
                  title={sd(v)}
                >
                  <span className="font-medium">{k}:</span> {sd(v)}
                </dd>
              ))}
            </>
          ) : null}
        </dl>
      </div>

      {tags && Object.keys(tags.assigned_tags).length > 0 ? (
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-foreground mb-3">
            Assigned Tags
          </h3>
          <div className="flex flex-col gap-3">
            {Object.entries(tags.assigned_tags).map(([category, tagList]) => (
              <div key={category} className="flex flex-col gap-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {category}
                </span>
                <div className="flex flex-wrap gap-1">
                  {tagList.map((tag) => (
                    <TagBadge key={tag} label={tag} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {tags && Object.keys(tags.candidate_tags).length > 0 ? (
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-foreground mb-3">
            Candidate Tags
          </h3>
          <div className="flex flex-col gap-3">
            {Object.entries(tags.candidate_tags).map(([category, tagList]) => (
              <div key={category} className="flex flex-col gap-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {category}
                </span>
                <div className="flex flex-wrap gap-1">
                  {tagList.map((tag) => (
                    <TagBadge key={tag} label={tag} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
