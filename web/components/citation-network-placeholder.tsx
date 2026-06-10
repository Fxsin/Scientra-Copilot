import { AlertTriangle } from "lucide-react";

export function CitationNetworkPlaceholder() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-xl border border-dashed border-border bg-card/50 px-8 py-20 text-center">
      <div className="flex size-14 items-center justify-center rounded-full bg-muted">
        <AlertTriangle className="size-7 text-muted-foreground" strokeWidth={1.5} />
      </div>
      <div className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold text-foreground">
          Citation Network is not enabled yet
        </h2>
        <p className="max-w-md text-sm text-muted-foreground">
          Citation Network requires structured references from each paper.
          The current database has not yet parsed and linked citations between papers.
          This feature will be enabled once reference extraction is complete.
        </p>
      </div>
      <div className="flex flex-col items-center gap-2">
        <span className="text-xs font-medium text-muted-foreground">
          Prerequisites:
        </span>
        <ul className="text-xs text-muted-foreground text-left space-y-1">
          <li>• Structured reference parsing from PDF/XML</li>
          <li>• DOI-to-paper_id linking</li>
          <li>• Citation graph construction</li>
        </ul>
      </div>
    </div>
  );
}
