"use client";

import { useState } from "react";
import { Bug, X, Wifi, WifiOff, AlertTriangle } from "lucide-react";
import { useGlobalDataSource, API_BASE_URL } from "@/lib/use-api";
import type { DataSource } from "@/lib/use-api";

interface DebugPanelProps {
  stats?: {
    paperCount?: number;
    apiStatus?: string;
    lastError?: string | null;
    lastUrl?: string | null;
    lastStatus?: number | null;
  };
}

const SOURCE_LABELS: Record<DataSource, string> = {
  REAL_API: "REAL_API",
  DEMO_FALLBACK: "DEMO_FALLBACK",
  API_ERROR: "API_ERROR",
  LOADING: "LOADING",
};

const SOURCE_ICONS: Record<DataSource, React.ReactNode> = {
  REAL_API: <Wifi className="size-3 text-green-500" />,
  DEMO_FALLBACK: <WifiOff className="size-3 text-amber-500" />,
  API_ERROR: <AlertTriangle className="size-3 text-red-500" />,
  LOADING: <span className="size-3 animate-pulse text-gray-400">⋯</span>,
};

export function DebugPanel({ stats }: DebugPanelProps) {
  const [open, setOpen] = useState(false);
  const globalSource = useGlobalDataSource();

  // Always hidden in production; toggle with a small button in dev
  return (
    <>
      <button
        onClick={() => setOpen(!open)}
        className="fixed bottom-2 right-2 z-50 rounded-full bg-gray-800 p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 transition-colors shadow"
        title="Debug Panel"
      >
        <Bug className="size-4" />
      </button>

      {open && (
        <div className="fixed bottom-10 right-2 z-50 w-80 rounded-lg border border-gray-700 bg-gray-900 p-4 text-xs text-gray-300 shadow-xl font-mono">
          <div className="flex items-center justify-between mb-3">
            <span className="font-semibold text-gray-200">Debug Panel</span>
            <button onClick={() => setOpen(false)} className="text-gray-500 hover:text-white">
              <X className="size-3.5" />
            </button>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-500">API Base URL</span>
              <code className="text-blue-300">{API_BASE_URL}</code>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Data Source</span>
              <span className="flex items-center gap-1">
                {SOURCE_ICONS[globalSource]}
                <code className={globalSource === "REAL_API" ? "text-green-400" : "text-amber-400"}>
                  {SOURCE_LABELS[globalSource]}
                </code>
              </span>
            </div>
            {stats?.paperCount !== undefined && (
              <div className="flex justify-between">
                <span className="text-gray-500">Paper Count</span>
                <code className="text-green-300">{stats.paperCount}</code>
              </div>
            )}
            {stats?.apiStatus && (
              <div className="flex justify-between">
                <span className="text-gray-500">API Status</span>
                <code className="text-gray-300">{stats.apiStatus}</code>
              </div>
            )}
            {stats?.lastUrl && (
              <div className="flex justify-between">
                <span className="text-gray-500">Last URL</span>
                <code className="text-gray-400 truncate max-w-[180px]">{stats.lastUrl}</code>
              </div>
            )}
            {stats?.lastStatus && (
              <div className="flex justify-between">
                <span className="text-gray-500">Last Status</span>
                <code className={stats.lastStatus >= 400 ? "text-red-400" : "text-green-400"}>
                  {stats.lastStatus}
                </code>
              </div>
            )}
            {stats?.lastError && (
              <div>
                <span className="text-gray-500">Last Error</span>
                <pre className="mt-0.5 rounded bg-gray-800 p-1.5 text-red-400 whitespace-pre-wrap max-h-32 overflow-y-auto">
                  {stats.lastError}
                </pre>
              </div>
            )}
          </div>

          <div className="mt-3 pt-2 border-t border-gray-700 text-gray-600">
            Press <kbd className="text-gray-500">?</kbd> to toggle · dev only
          </div>
        </div>
      )}
    </>
  );
}
