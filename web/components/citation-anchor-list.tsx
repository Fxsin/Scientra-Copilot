import { Link2 } from "lucide-react";
import type { ParsedCitationAnchor } from "@/lib/types";

/**
 * Parse citation anchor details from summary text.
 * Each anchor is embedded inline like:
 *   (S007 source_section=Page 1 page=unknown paragraph=8; S016 ...)
 */
function parseAnchorsFromText(summary: string): ParsedCitationAnchor[] {
  const seen = new Set<string>();
  const results: ParsedCitationAnchor[] = [];

  // Match anchor blocks: SXXX followed by key=value pairs
  const anchorRegex = /(S\d{3,})\s+((?:[a-z_]+=[^\s;)]+[;\s]*)+)/gi;
  let match: RegExpExecArray | null;
  while ((match = anchorRegex.exec(summary)) !== null) {
    const id = match[1];
    if (seen.has(id)) continue;
    seen.add(id);

    const props = match[2];
    const source_section = extractProp(props, "source_section");
    const page = extractProp(props, "page");
    const paragraph = extractProp(props, "paragraph");

    results.push({
      id,
      source_section: source_section || null,
      page: page && page !== "unknown" ? page : null,
      paragraph: paragraph ? parseInt(paragraph, 10) || null : null,
    });
  }

  // If regex didn't catch them, just use bare IDs from citation_anchors
  if (results.length === 0) {
    const bareRegex = /\b(S\d{3,})\b/g;
    while ((match = bareRegex.exec(summary)) !== null) {
      const id = match[1];
      if (seen.has(id)) continue;
      seen.add(id);
      results.push({ id, source_section: null, page: null, paragraph: null });
    }
  }

  return results;
}

function extractProp(props: string, key: string): string | undefined {
  const re = new RegExp(`${key}=([^\\s;)]+)`, "i");
  const m = props.match(re);
  return m ? m[1].replace(/[,)]$/, "") : undefined;
}

interface CitationAnchorListProps {
  summary: string;
  citationAnchors: string[];
}

export function CitationAnchorList({
  summary,
  citationAnchors,
}: CitationAnchorListProps) {
  const parsed = parseAnchorsFromText(summary);

  // Fallback: use the citation_anchors field if parsing found nothing
  const anchors: ParsedCitationAnchor[] =
    parsed.length > 0
      ? parsed
      : citationAnchors.map((id) => ({
          id,
          source_section: null,
          page: null,
          paragraph: null,
        }));

  if (anchors.length === 0) {
    return (
      <p className="text-xs text-muted-foreground italic">
        No citation anchors found.
      </p>
    );
  }

  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {anchors.map((anchor) => (
        <div
          key={anchor.id}
          className="flex flex-col gap-1 rounded-lg border border-border bg-card p-3 shadow-sm"
        >
          <div className="flex items-center gap-1.5">
            <Link2 className="size-3 text-muted-foreground" strokeWidth={1.5} />
            <span className="font-mono text-xs font-semibold text-foreground">
              {anchor.id}
            </span>
          </div>
          {anchor.source_section && (
            <span className="text-[11px] text-muted-foreground">
              Section: {anchor.source_section}
            </span>
          )}
          {anchor.page && (
            <span className="text-[11px] text-muted-foreground">
              Page: {anchor.page}
            </span>
          )}
          {anchor.paragraph !== null && (
            <span className="text-[11px] text-muted-foreground">
              ¶ {anchor.paragraph}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
