"use client";

import { cn } from "@/lib/utils";
import type { QueryMode } from "@/lib/types";

const MODES: { value: QueryMode; label: string }[] = [
  { value: "keyword", label: "Keyword" },
  { value: "vector", label: "Vector" },
  { value: "hybrid", label: "Hybrid" },
];

interface SearchModeToggleProps {
  value: QueryMode;
  onChange: (mode: QueryMode) => void;
}

export function SearchModeToggle({ value, onChange }: SearchModeToggleProps) {
  return (
    <div className="inline-flex rounded-lg border border-border bg-muted p-0.5" role="radiogroup" aria-label="Search mode">
      {MODES.map((mode) => (
        <button
          key={mode.value}
          type="button"
          role="radio"
          aria-checked={value === mode.value}
          onClick={() => onChange(mode.value)}
          className={cn(
            "rounded-md px-3 py-1 text-xs font-medium transition-colors",
            value === mode.value
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {mode.label}
        </button>
      ))}
    </div>
  );
}
