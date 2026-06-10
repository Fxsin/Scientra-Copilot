"use client";

import { Trash2, Play, RotateCcw, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FileStatusBadge } from "@/components/file-status-badge";
import { WorkflowProgress } from "@/components/workflow-progress";
import { useImportStore } from "@/lib/import-store";
import { formatFileSize, formatTime } from "@/lib/import-types";

const ACTIVE_STATUSES = ["parsing", "metadata", "tagging", "embedding"];

export function ImportHistoryTable() {
  const items = useImportStore((s) => s.items);
  const polling = useImportStore((s) => s.polling);
  const removeItem = useImportStore((s) => s.removeItem);
  const runJob = useImportStore((s) => s.runJob);
  const retryJob = useImportStore((s) => s.retryJob);

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-card/50 px-8 py-16 text-center">
        <p className="text-sm font-medium text-muted-foreground">
          No imports yet
        </p>
        <p className="text-xs text-muted-foreground/70">
          Drop PDF files above or click &quot;Select PDF Files&quot; to start
          importing.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-sm">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/50">
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Filename
            </th>
            <th className="hidden px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground sm:table-cell">
              Size
            </th>
            <th className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Status
            </th>
            <th className="hidden px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground md:table-cell">
              Progress
            </th>
            <th className="hidden px-3 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground lg:table-cell">
              Created
            </th>
            <th className="px-3 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((item) => (
            <tr
              key={item.id}
              className="group transition-colors hover:bg-muted/30"
            >
              {/* Filename */}
              <td className="px-4 py-3">
                <div className="flex flex-col">
                  <span
                    className="text-sm font-medium text-foreground line-clamp-1 max-w-[260px]"
                    title={item.filename}
                  >
                    {item.filename}
                  </span>
                  {item.error && (
                    <span className="mt-0.5 text-[10px] text-destructive line-clamp-1">
                      {item.error}
                    </span>
                  )}
                </div>
              </td>

              {/* Size */}
              <td className="hidden px-3 py-3 sm:table-cell whitespace-nowrap">
                <span className="font-mono text-xs text-muted-foreground">
                  {formatFileSize(item.sizeBytes)}
                </span>
              </td>

              {/* Status badge */}
              <td className="px-3 py-3 whitespace-nowrap">
                <FileStatusBadge status={item.status} />
              </td>

              {/* Progress bar */}
              <td className="hidden px-3 py-3 md:table-cell min-w-[200px]">
                <WorkflowProgress
                  status={item.status}
                  progress={item.progress}
                  currentStep={item.currentStep}
                  error={item.error}
                />
              </td>

              {/* Created */}
              <td className="hidden px-3 py-3 lg:table-cell whitespace-nowrap">
                <span className="text-xs text-muted-foreground">
                  {formatTime(item.createdAt)}
                </span>
              </td>

              {/* Actions */}
              <td className="px-3 py-3 text-right whitespace-nowrap">
                <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  {item.status === "queued" && (
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      onClick={() => runJob(item.id)}
                      disabled={polling}
                      aria-label="Run"
                      title="Run workflow"
                    >
                      <Play className="size-3.5" />
                    </Button>
                  )}
                  {item.status === "failed" && (
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      onClick={() => retryJob(item.id)}
                      disabled={polling}
                      aria-label="Retry"
                      title="Retry workflow"
                    >
                      <RotateCcw className="size-3.5" />
                    </Button>
                  )}
                  {item.status === "summary" &&
                    item.currentStep === "pending_agent_resolution" && (
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        onClick={() => retryJob(item.id)}
                        aria-label="Resume"
                        title="Resume after agent resolution"
                      >
                        <Play className="size-3.5" />
                      </Button>
                    )}
                  {ACTIVE_STATUSES.includes(item.status) && (
                    <Loader2 className="size-3.5 animate-spin text-muted-foreground" />
                  )}
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    onClick={() => removeItem(item.id)}
                    aria-label="Remove"
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
