"use client";

import { useState, useCallback, type DragEvent } from "react";
import { Upload, FileText, AlertTriangle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useImportStore } from "@/lib/import-store";

export function UploadDropzone() {
  const [over, setOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const uploadFiles = useImportStore((s) => s.uploadFiles);

  const handleFiles = useCallback(
    async (fileList: FileList | null) => {
      if (!fileList || fileList.length === 0) return;
      setError(null);

      const pdfs: File[] = [];
      const rejected: string[] = [];

      for (let i = 0; i < fileList.length; i++) {
        const f = fileList[i];
        if (
          f.type === "application/pdf" ||
          f.name.toLowerCase().endsWith(".pdf")
        ) {
          pdfs.push(f);
        } else {
          rejected.push(f.name);
        }
      }

      if (rejected.length > 0) {
        setError(
          `Skipped non-PDF file${rejected.length > 1 ? "s" : ""}: ${rejected.join(", ")}`,
        );
      }

      if (pdfs.length === 0) {
        if (rejected.length === 0) setError("No files selected.");
        return;
      }

      setUploading(true);
      try {
        await uploadFiles(pdfs);
      } catch {
        // error already shown via store (optimistic entries become failed)
      } finally {
        setUploading(false);
      }
    },
    [uploadFiles],
  );

  const onDragOver = (e: DragEvent) => {
    e.preventDefault();
    setOver(true);
  };
  const onDragLeave = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
    <div
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed p-10 text-center transition-colors",
        over
          ? "border-accent bg-accent/5"
          : uploading
            ? "border-primary/40 bg-primary/5"
            : "border-border hover:border-muted-foreground/30",
      )}
    >
      <div
        className={cn(
          "flex size-14 items-center justify-center rounded-full transition-colors",
          over
            ? "bg-accent/20 text-accent-foreground"
            : uploading
              ? "bg-primary/10 text-primary"
              : "bg-muted text-muted-foreground",
        )}
      >
        {uploading ? (
          <Loader2 className="size-7 animate-spin" strokeWidth={1.5} />
        ) : over ? (
          <FileText className="size-7" strokeWidth={1.5} />
        ) : (
          <Upload className="size-7" strokeWidth={1.5} />
        )}
      </div>

      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium text-foreground">
          {uploading
            ? "Uploading..."
            : over
              ? "Drop PDF files here"
              : "Drag & drop PDF files"}
        </p>
        <p className="text-xs text-muted-foreground">
          {uploading
            ? "Saving to Literature_OS inbox..."
            : "or click the button below to browse"}
        </p>
      </div>

      <label
        className={cn(
          "inline-flex cursor-pointer items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
          uploading
            ? "border-muted bg-muted text-muted-foreground cursor-not-allowed"
            : "border-border bg-background text-foreground hover:bg-muted",
        )}
      >
        {uploading ? (
          <>
            <Loader2 className="size-3.5 animate-spin" />
            Uploading...
          </>
        ) : (
          <>
            <Upload className="size-3.5" />
            Select PDF Files
          </>
        )}
        <input
          type="file"
          accept=".pdf,application/pdf"
          multiple
          className="hidden"
          disabled={uploading}
          onChange={(e) => handleFiles(e.target.files)}
        />
      </label>

      {error && (
        <div className="flex items-center gap-1.5 rounded-lg bg-destructive/10 px-3 py-1.5 text-xs text-destructive">
          <AlertTriangle className="size-3" />
          {error}
        </div>
      )}

      <p className="text-[10px] text-muted-foreground/60">
        PDF only · Max 50 MB per file · Multiple files supported
      </p>
    </div>
  );
}
