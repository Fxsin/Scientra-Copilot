"use client";

import { useState, useCallback, type DragEvent } from "react";
import { Upload, FileText, AlertTriangle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Legacy UploadDropzone — deprecated in favor of the full Import Dashboard
 * at /import which provides the new Web Import Center with multipart upload,
 * import plan generation, and confirm workflow.
 *
 * This component is a stub that directs users to the new /import page.
 */
export function UploadDropzone() {
  const [over, setOver] = useState(false);

  const handleClick = () => {
    window.location.href = "/import";
  };

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={(e) => { e.preventDefault(); setOver(false); }}
      onDrop={(e) => { e.preventDefault(); setOver(false); }}
      onClick={handleClick}
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed p-10 text-center transition-colors cursor-pointer",
        over
          ? "border-accent bg-accent/5"
          : "border-border hover:border-muted-foreground/30",
      )}
    >
      <div
        className={cn(
          "flex size-14 items-center justify-center rounded-full transition-colors",
          over
            ? "bg-accent/20 text-accent-foreground"
            : "bg-muted text-muted-foreground",
        )}
      >
        <Upload className="size-7" strokeWidth={1.5} />
      </div>

      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium text-foreground">
          Open Import Center
        </p>
        <p className="text-xs text-muted-foreground">
          The new Import Dashboard supports PDF, Excel, CSV, ZIP, and folder uploads
        </p>
      </div>

      <a
        href="/import"
        className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium border-border bg-background text-foreground hover:bg-muted"
      >
        <Upload className="size-3.5" />
        Go to /import
      </a>

      <p className="text-[10px] text-muted-foreground/60">
        PDF · Excel · CSV · TSV · DOCX · ZIP · Max 100 MB per file
      </p>
    </div>
  );
}
