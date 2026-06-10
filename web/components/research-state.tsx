"use client";

import {
  Loader2,
  Database,
  AlertTriangle,
  RefreshCw,
  FileSearch,
  FlaskConical,
  Calendar,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ProjectMeta } from "@/lib/data/researchIntelligenceMock";

/* ── DataSourceBadge ── */
export function DataSourceBadge({ source }: { source: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/50 px-2.5 py-0.5 text-[10px] font-medium text-muted-foreground">
      <Database className="size-3" />
      {source}
    </span>
  );
}

/* ── ResearchPageHeader ── */
export function ResearchPageHeader({
  title,
  description,
  projectMeta,
}: {
  title: string;
  description: string;
  projectMeta: ProjectMeta;
}) {
  const updated = new Date(projectMeta.lastUpdated).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <div className="flex flex-col gap-3">
      {/* Title + description */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          {title}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground max-w-3xl">
          {description}
        </p>
      </div>

      {/* Project meta bar */}
      <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <FlaskConical className="size-3.5 text-secondary" strokeWidth={1.5} />
          <span className="font-medium text-foreground/80">
            {projectMeta.projectName}
          </span>
        </span>
        <span className="text-border">|</span>
        <span className="inline-flex items-center gap-1">
          <FileSearch className="size-3" />
          {projectMeta.paperCount} papers
        </span>
        <span className="text-border">|</span>
        <span className="inline-flex items-center gap-1">
          <Calendar className="size-3" />
          Updated {updated}
        </span>
        <span className="text-border">|</span>
        <DataSourceBadge source={projectMeta.dataSource} />
      </div>
    </div>
  );
}

/* ── ResearchLoadingState ── */
export function ResearchLoadingState({
  title,
  message,
}: {
  title?: string;
  message?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-4">
      <Loader2 className="size-8 animate-spin text-muted-foreground" />
      <div className="text-center">
        <p className="text-sm font-medium text-foreground">
          {title ?? "Loading…"}
        </p>
        {message && (
          <p className="mt-1 text-xs text-muted-foreground">{message}</p>
        )}
      </div>
    </div>
  );
}

/* ── ResearchEmptyState ── */
export function ResearchEmptyState({
  title,
  description,
  actionLabel,
  onAction,
}: {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4 rounded-xl border border-dashed border-border bg-card/50">
      <div className="flex size-12 items-center justify-center rounded-full bg-muted">
        <FileSearch className="size-6 text-muted-foreground" strokeWidth={1.5} />
      </div>
      <div className="text-center max-w-sm">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="mt-1 text-xs text-muted-foreground">{description}</p>
      </div>
      {actionLabel && onAction && (
        <Button variant="outline" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

/* ── ResearchErrorState ── */
export function ResearchErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4 rounded-xl border border-destructive/30 bg-destructive/5">
      <div className="flex size-12 items-center justify-center rounded-full bg-destructive/10">
        <AlertTriangle className="size-6 text-destructive" strokeWidth={1.5} />
      </div>
      <div className="text-center max-w-sm">
        <p className="text-sm font-medium text-foreground">Something went wrong</p>
        <p className="mt-1 text-xs text-muted-foreground">{message}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="size-3.5" />
          Retry
        </Button>
      )}
    </div>
  );
}

/* ── Compact Score Bar (0–100) ── */
export function ScoreBar({
  label,
  score,
  colorClass = "bg-secondary",
}: {
  label: string;
  score: number;
  colorClass?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 text-[10px] text-muted-foreground shrink-0">
        {label}
      </span>
      <div className="h-1.5 flex-1 rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full rounded-full ${colorClass} transition-all`}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
        />
      </div>
      <span className="w-7 text-right text-[10px] font-mono text-muted-foreground">
        {score}
      </span>
    </div>
  );
}
