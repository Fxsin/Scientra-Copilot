"use client";

import { Search, SlidersHorizontal, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SearchModeToggle } from "@/components/search-mode-toggle";
import type { QueryLevel, QueryMode } from "@/lib/types";

const TOP_K_OPTIONS = [10, 25, 50] as const;
const LEVEL_OPTIONS: { value: QueryLevel; label: string }[] = [
  { value: "metadata", label: "Metadata" },
  { value: "summary", label: "Summary" },
  { value: "chunks", label: "Chunks" },
  { value: "all", label: "All" },
];

const FILTER_CATEGORIES = [
  { key: "toxin", label: "Toxin" },
  { key: "host", label: "Host" },
  { key: "mechanism", label: "Mechanism" },
  { key: "method", label: "Method" },
] as const;

interface PaperFilterBarProps {
  query: string;
  onQueryChange: (v: string) => void;
  mode: QueryMode;
  onModeChange: (v: QueryMode) => void;
  topK: number;
  onTopKChange: (v: number) => void;
  level: QueryLevel;
  onLevelChange: (v: QueryLevel) => void;
  filters: Record<string, string>;
  onFilterChange: (category: string, value: string) => void;
  onSearch: () => void;
  loading: boolean;
}

export function PaperFilterBar({
  query,
  onQueryChange,
  mode,
  onModeChange,
  topK,
  onTopKChange,
  level,
  onLevelChange,
  filters,
  onFilterChange,
  onSearch,
  loading,
}: PaperFilterBarProps) {
  const hasFilters = Object.values(filters).some(Boolean);

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 shadow-sm">
      {/* Row 1: search + go */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground"
            strokeWidth={1.5}
          />
          <input
            type="text"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onSearch();
            }}
            placeholder="Search literature… e.g. Vip3A, Cry toxin, CRISPR"
            className="h-9 w-full rounded-lg border border-border bg-background pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
          />
        </div>
        <Button onClick={onSearch} disabled={loading} size="default">
          {loading ? "Searching…" : "Search"}
        </Button>
      </div>

      {/* Row 2: mode · topK · level · clear filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
            Mode
          </span>
          <SearchModeToggle value={mode} onChange={onModeChange} />
        </div>

        <div className="h-6 w-px bg-border" />

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
            Top K
          </span>
          <div className="inline-flex rounded-lg border border-border bg-muted p-0.5">
            {TOP_K_OPTIONS.map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => onTopKChange(k)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  topK === k
                    ? "bg-card text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {k}
              </button>
            ))}
          </div>
        </div>

        <div className="h-6 w-px bg-border" />

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
            Level
          </span>
          <div className="inline-flex rounded-lg border border-border bg-muted p-0.5">
            {LEVEL_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => onLevelChange(opt.value)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  level === opt.value
                    ? "bg-card text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {hasFilters && (
          <>
            <div className="h-6 w-px bg-border" />
            <Button
              variant="ghost"
              size="xs"
              onClick={() => {
                for (const cat of FILTER_CATEGORIES) {
                  onFilterChange(cat.key, "");
                }
              }}
            >
              <X className="size-3" />
              Clear filters
            </Button>
          </>
        )}
      </div>

      {/* Row 3: tag category filters */}
      <details className="group">
        <summary className="flex cursor-pointer items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors select-none">
          <SlidersHorizontal className="size-3.5" strokeWidth={1.5} />
          Tag Filters
        </summary>
        <div className="mt-2.5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {FILTER_CATEGORIES.map((cat) => (
            <div key={cat.key} className="flex flex-col gap-1">
              <label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                {cat.label}
              </label>
              <input
                type="text"
                value={filters[cat.key] ?? ""}
                onChange={(e) => onFilterChange(cat.key, e.target.value)}
                placeholder={`e.g. Cry, Vip3`}
                className="h-8 rounded-md border border-border bg-background px-2.5 text-xs text-foreground placeholder:text-muted-foreground outline-none focus-visible:border-ring"
              />
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
