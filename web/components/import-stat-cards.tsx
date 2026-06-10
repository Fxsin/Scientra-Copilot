"use client";

import {
  FileDown,
  CheckCircle2,
  Loader2,
  XCircle,
  Clock,
} from "lucide-react";
import { useImportStats } from "@/lib/import-store";

const STATS = [
  { key: "total", label: "Total Imported", icon: FileDown },
  { key: "completed", label: "Completed", icon: CheckCircle2 },
  { key: "processing", label: "Processing", icon: Loader2 },
  { key: "failed", label: "Failed", icon: XCircle },
  { key: "waiting", label: "Waiting", icon: Clock },
] as const;

export function ImportStatCards() {
  const stats = useImportStats();

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {STATS.map(({ key, label, icon: Icon }) => (
        <div
          key={key}
          className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 shadow-sm"
        >
          <div className="flex size-9 items-center justify-center rounded-lg bg-muted">
            <Icon
              className={`size-4 ${
                key === "processing"
                  ? "animate-spin text-muted-foreground"
                  : "text-muted-foreground"
              }`}
              strokeWidth={1.5}
            />
          </div>
          <div className="flex flex-col">
            <span className="text-lg font-bold text-foreground">
              {stats[key]}
            </span>
            <span className="text-[11px] text-muted-foreground">{label}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
