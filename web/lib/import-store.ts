"use client";

import { useMemo } from "react";
import { create } from "zustand";
import type { ImportItem, ImportStatus } from "./import-types";
import { jobToItem } from "./import-types";
import {
  uploadPdfs,
  getImportJobs,
  runImportJob,
  retryImportJob,
  runAllImportJobs,
} from "./api";

/* ── Store ── */

interface ImportStore {
  items: ImportItem[];
  loaded: boolean;
  polling: boolean;
  /** Fetch jobs from API */
  loadJobs: () => Promise<void>;
  /** Upload files to API, refresh list on success */
  uploadFiles: (files: File[]) => Promise<void>;
  /** Remove an item locally */
  removeItem: (id: string) => void;
  /** Trigger workflow for a single job */
  runJob: (importId: string) => Promise<void>;
  /** Retry a failed job */
  retryJob: (importId: string) => Promise<void>;
  /** Run all queued/failed jobs */
  runAll: () => Promise<void>;
  /** Start polling for status updates */
  startPolling: () => void;
  /** Stop polling */
  stopPolling: () => void;
}

let _pollTimer: ReturnType<typeof setInterval> | null = null;

function _clearPoll() {
  if (_pollTimer) {
    clearInterval(_pollTimer);
    _pollTimer = null;
  }
}

export const useImportStore = create<ImportStore>((set, get) => ({
  items: [],
  loaded: false,
  polling: false,

  loadJobs: async () => {
    try {
      const data = await getImportJobs();
      set({
        items: data.jobs.map(jobToItem),
        loaded: true,
      });
    } catch {
      // API may not be running — keep current items, mark as attempted
      set({ loaded: true });
    }
  },

  uploadFiles: async (files) => {
    // Show optimistic "uploading" entries
    const now = new Date().toISOString();
    const optimistic: ImportItem[] = files.map((f, i) => ({
      id: `optimistic-${Date.now()}-${i}`,
      filename: f.name,
      sizeBytes: f.size,
      status: "uploading" as ImportStatus,
      progress: 0,
      currentStep: "Uploading",
      createdAt: now,
      completedAt: null,
      error: null,
    }));
    set((s) => ({ items: [...optimistic, ...s.items] }));

    try {
      await uploadPdfs(files);
      // Replace optimistic entries with real ones, refresh from API
      await get().loadJobs();
      // Also remove any optimistic entries that the API didn't return
      set((s) => ({
        items: s.items.filter((i) => !i.id.startsWith("optimistic-")),
      }));
      // Load again to get final state
      await get().loadJobs();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      // Mark optimistic entries as failed
      set((s) => ({
        items: s.items.map((i) =>
          i.id.startsWith("optimistic-") && i.status === "uploading"
            ? { ...i, status: "failed" as ImportStatus, error: msg }
            : i,
        ),
      }));
    }
  },

  removeItem: (id) => {
    set((s) => ({ items: s.items.filter((i) => i.id !== id) }));
  },

  runJob: async (importId) => {
    await runImportJob(importId);
    await get().loadJobs();
    get().startPolling();
  },

  retryJob: async (importId) => {
    await retryImportJob(importId);
    await get().loadJobs();
    get().startPolling();
  },

  runAll: async () => {
    await runAllImportJobs();
    await get().loadJobs();
    get().startPolling();
  },

  startPolling: () => {
    const { polling } = get();
    if (polling) return;
    set({ polling: true });
    _clearPoll();
    _pollTimer = setInterval(async () => {
      await get().loadJobs();
      const { items } = get();
      // Stop polling when all jobs are terminal
      const allTerminal = items.every(
        (i) => i.status === "completed" || i.status === "failed",
      );
      // Or if presence of a summary job with pending_agent → keep polling
      if (allTerminal) {
        get().stopPolling();
      }
    }, 3000);
  },

  stopPolling: () => {
    _clearPoll();
    set({ polling: false });
  },
}));

/* ── Derived selectors ── */

export function useImportStats() {
  const items = useImportStore((s) => s.items);

  return useMemo(() => {
    return {
      total: items.length,
      completed: items.filter((i) => i.status === "completed").length,
      processing: items.filter(
        (i) => !["completed", "failed", "waiting"].includes(i.status),
      ).length,
      failed: items.filter((i) => i.status === "failed").length,
      waiting: items.filter((i) => i.status === "waiting").length,
    };
  }, [items]);
}

export function useRecentImports(limit = 5) {
  const items = useImportStore((s) => s.items);

  return useMemo(() => {
    return [...items]
      .sort(
        (a, b) =>
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
      )
      .slice(0, limit);
  }, [items, limit]);
}
