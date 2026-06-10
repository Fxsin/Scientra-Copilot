"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import type { PaperMetadata } from "@/lib/types";

interface PaperHeaderProps {
  metadata: PaperMetadata;
}

export function PaperHeader({ metadata }: PaperHeaderProps) {
  const [authorsExpanded, setAuthorsExpanded] = useState(false);
  const md = metadata.metadata;

  const title = (md?.title as string) || "Untitled";
  const year = md?.year as number | undefined;
  const doi = md?.doi as string | undefined;
  const journal = md?.journal as string | undefined;
  const authors = md?.authors as
    | string
    | { name: string }[]
    | string[]
    | undefined;

  // Normalize authors to a flat string array
  const authorList: string[] = (() => {
    if (!authors) return [];
    if (typeof authors === "string")
      return authors.split(/[,;]/).map((s) => s.trim()).filter(Boolean);
    if (Array.isArray(authors)) {
      return authors.map((a) =>
        typeof a === "object" && a !== null && "name" in a
          ? (a as { name: string }).name
          : String(a),
      );
    }
    return [];
  })();

  const displayAuthors = authorsExpanded
    ? authorList
    : authorList.slice(0, 5);
  const hasMore = authorList.length > 5;

  return (
    <div className="flex flex-col gap-4">
      {/* Back link */}
      <div>
        <Link
          href="/library"
          className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors -ml-2"
        >
          <ArrowLeft className="size-3.5" />
          Back to Library
        </Link>
      </div>

      {/* Title */}
      <h1 className="text-2xl font-bold tracking-tight text-foreground leading-snug">
        {title}
      </h1>

      {/* Meta row */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm">
        {year && (
          <span className="font-medium text-foreground">{year}</span>
        )}
        {journal && (
          <span className="text-muted-foreground italic">{journal}</span>
        )}
        {doi && (
          <a
            href={`https://doi.org/${doi}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-mono text-xs text-accent-foreground hover:underline"
          >
            {doi}
            <ExternalLink className="size-3" />
          </a>
        )}
      </div>

      {/* Authors */}
      {authorList.length > 0 && (
        <div className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground/80">Authors: </span>
          {displayAuthors.join(", ")}
          {hasMore && (
            <button
              type="button"
              onClick={() => setAuthorsExpanded(!authorsExpanded)}
              className="ml-1.5 inline-flex items-center gap-0.5 text-xs font-medium text-primary hover:underline"
            >
              {authorsExpanded ? (
                <>
                  Show less <ChevronUp className="size-3" />
                </>
              ) : (
                <>
                  +{authorList.length - 5} more <ChevronDown className="size-3" />
                </>
              )}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
