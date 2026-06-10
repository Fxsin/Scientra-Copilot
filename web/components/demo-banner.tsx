"use client";

import { AlertTriangle, Wifi, WifiOff, RefreshCw } from "lucide-react";
import type { DataSource } from "@/lib/use-api";

interface DemoBannerProps {
  /** When true (old API), show the generic demo banner. */
  show?: boolean;
  /** New API: explicit data source state for richer messaging. */
  dataSource?: DataSource;
  /** Human-readable error message from the API call. */
  error?: string | null;
  /** The URL that was tried. */
  lastUrl?: string | null;
  /** HTTP status code if available. */
  lastStatus?: number | null;
  /** Retry callback. */
  onRetry?: () => void;
}

export function DemoBanner({
  show,
  dataSource,
  error,
  lastUrl,
  lastStatus,
  onRetry,
}: DemoBannerProps) {
  // Legacy usage with just `show` prop — default to hidden.
  // Pages that have real API data should use the `dataSource` prop instead.
  if (dataSource === undefined) {
    if (show !== true) return null;
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

  // New API with explicit data source
  if (dataSource === "REAL_API" || dataSource === "LOADING") {
    return null;
  }

  if (dataSource === "DEMO_FALLBACK") {
    return (
      <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-xs text-amber-800">
        <WifiOff className="size-3.5 shrink-0" />
        <span className="flex-1">
          <strong>Demo mode</strong> — API unavailable.
          {lastUrl && <> Tried <code className="bg-amber-100 px-1 rounded">{lastUrl}</code>.</>}
          {error && <span className="block text-amber-600 mt-0.5">{error}</span>}
        </span>
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-1 rounded bg-amber-200 px-2 py-1 text-amber-900 hover:bg-amber-300 transition-colors"
          >
            <RefreshCw className="size-3" /> Retry
          </button>
        )}
      </div>
    );
  }

  // API_ERROR
  return (
    <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-xs text-red-800">
      <AlertTriangle className="size-3.5 shrink-0 mt-0.5" />
      <span className="flex-1">
        <strong>API Error</strong>
        {lastStatus && <> (HTTP {lastStatus})</>}
        {lastUrl && <> — <code className="bg-red-100 px-1 rounded">{lastUrl}</code></>}
        {error && <span className="block text-red-600 mt-0.5">{error}</span>}
      </span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1 rounded bg-red-200 px-2 py-1 text-red-900 hover:bg-red-300 transition-colors"
        >
          <RefreshCw className="size-3" /> Retry
        </button>
      )}
    </div>
  );
}
