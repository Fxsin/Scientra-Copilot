"use client";

import { AlertTriangle } from "lucide-react";

interface DemoBannerProps {
  /** Optional: show only when explicitly set to true */
  show?: boolean;
}

export function DemoBanner({ show = true }: DemoBannerProps) {
  if (!show) return null;

  return (
    <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-xs text-amber-800">
      <AlertTriangle className="size-3.5 shrink-0" />
      <span>
        <strong>Demo Data</strong> — Showing example data. Import literature and
        start the API server to see your own research.
      </span>
    </div>
  );
}
