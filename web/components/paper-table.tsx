"use client";

import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { TagBadge } from "@/components/tag-badge";
import type { QueryResultItem } from "@/lib/types";

interface PaperTableProps {
  results: QueryResultItem[];
}

function collectTags(item: QueryResultItem): string[] {
  const seen = new Set<string>();
  // matched tags first, then assigned
  for (const t of item.matched_tags) {
    if (t) seen.add(t);
  }
  for (const [, tags] of Object.entries(item.assigned_tags)) {
    for (const t of tags) {
      if (t) seen.add(t);
    }
  }
  return [...seen].slice(0, 8); // max 8 badges per row
}

export function PaperTable({ results }: PaperTableProps) {
  if (results.length === 0) return null;

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-sm">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/50">
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Title
            </th>
            <th className="hidden px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground md:table-cell">
              Year
            </th>
            <th className="hidden px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground lg:table-cell">
              DOI
            </th>
            <th className="hidden px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground lg:table-cell">
              Tags
            </th>
            <th className="hidden px-3 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground sm:table-cell">
              Score
            </th>
            <th className="hidden px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground sm:table-cell">
              Level
            </th>
            <th className="hidden px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground xl:table-cell">
              Preview
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {results.map((item, idx) => {
            const tags = collectTags(item);
            return (
              <tr
                key={`${item.record_id}-${idx}`}
                className="group transition-colors hover:bg-muted/40"
              >
                {/* Title + link */}
                <td className="px-4 py-3">
                  <Link
                    href={`/papers/${item.paper_id}`}
                    className="flex items-start gap-1.5 text-foreground hover:text-primary transition-colors"
                  >
                    <span
                      className="line-clamp-2 font-medium"
                      title={item.title ?? undefined}
                    >
                      {item.title || (
                        <span className="italic text-muted-foreground">
                          Untitled
                        </span>
                      )}
                    </span>
                    <ExternalLink className="mt-0.5 size-3 shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                  </Link>
                </td>

                {/* Year */}
                <td className="hidden px-3 py-3 text-muted-foreground md:table-cell whitespace-nowrap">
                  {item.year ?? "—"}
                </td>

                {/* DOI */}
                <td className="hidden px-3 py-3 lg:table-cell">
                  {item.doi ? (
                    <span
                      className="block max-w-[180px] truncate font-mono text-xs text-muted-foreground"
                      title={item.doi}
                    >
                      {item.doi}
                    </span>
                  ) : (
                    <span className="text-muted-foreground/50">—</span>
                  )}
                </td>

                {/* Tags */}
                <td className="hidden px-3 py-3 lg:table-cell">
                  <div className="flex flex-wrap gap-1 max-w-[220px]">
                    {tags.length > 0 ? (
                      tags.map((tag) => <TagBadge key={tag} label={tag} />)
                    ) : (
                      <span className="text-xs text-muted-foreground/50">
                        —
                      </span>
                    )}
                  </div>
                </td>

                {/* Score */}
                <td className="hidden px-3 py-3 text-right sm:table-cell whitespace-nowrap">
                  <span
                    className={cn(
                      "inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-xs font-medium",
                      item.score >= 5
                        ? "bg-secondary/10 text-secondary"
                        : item.score >= 1
                          ? "bg-accent/20 text-accent-foreground"
                          : "bg-muted text-muted-foreground",
                    )}
                  >
                    {item.score.toFixed(3)}
                  </span>
                </td>

                {/* Level */}
                <td className="hidden px-3 py-3 sm:table-cell whitespace-nowrap">
                  <span className="rounded-md bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground uppercase">
                    {item.level}
                  </span>
                </td>

                {/* Preview */}
                <td className="hidden px-4 py-3 xl:table-cell">
                  {item.text_preview ? (
                    <p
                      className="line-clamp-2 max-w-[320px] text-xs text-muted-foreground leading-relaxed"
                      title={item.text_preview}
                    >
                      {item.text_preview}
                    </p>
                  ) : (
                    <span className="text-xs text-muted-foreground/50">
                      —
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
