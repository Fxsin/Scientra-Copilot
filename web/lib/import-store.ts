"use client";

import { useMemo } from "react";
import { create } from "zustand";
import type { ImportItem, ImportStatus } from "./import-types";
import { jobToItem } from "./import-types";
import {
  getImportJobs,
  runImportJob,
  retryImportJob,
  runAllImportJobs,
} from "./api";

/* ── Store ──
 *
 * This store is a compatibility shim for the legacy import workflow.
 * The new P0 Web Import Center uses direct API calls in the import page
 * (createUploadSession, uploadFilesBatch, generateImportPlan, etc.)
 * and does NOT use this store.
 *
 * loadJobs is a no-op when the legacy /import/jobs endpoint is unavailable.
 */

interface ImportStore {
  items: ImportItem[];
  loaded: boolean;
  polling: boolean;
  loadJobs: () => Promise<void>;
  uploadFiles: (files: File[]) => Promise<void>;
  removeItem: (id: string) => void;
  runJob: (importId: string) => Promise<void>;
  retryJob: (importId: string) => Promise<void>;
  runAll: () => Promise<void>;
  startPolling: () => void;
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
        items: (data.jobs || []).map(jobToItem),
        loaded: true,
      });
    } catch {
      // Legacy /import/jobs endpoint unavailable — mark as loaded (empty)
      set({ loaded: true });
    }
  },

  uploadFiles: async (_files) => {
    // Legacy upload is deprecated. Use the new Web Import Center API instead:
    // createUploadSession() → uploadFilesMultipart() or uploadFilesBatch()
    // This function is a no-op to prevent errors from the old endpoint.
  },

  removeItem: (id) => {
    set((s) => ({ items: s.items.filter((i) => i.id !== id) }));
  },

  runJob: async (importId) => {
    try {
      await runImportJob(importId);
      await get().loadJobs();
      get().startPolling();
    } catch {
      // Legacy endpoint may not exist
    }
  },

  retryJob: async (importId) => {
    try {
      await retryImportJob(importId);
      await get().loadJobs();
      get().startPolling();
    } catch {
      // Legacy endpoint may not exist
    }
  },

  runAll: async () => {
    try {
      await runAllImportJobs();
      await get().loadJobs();
      get().startPolling();
    } catch {
      // Legacy endpoint may not exist
    }
  },

  startPolling: () => {
    const { polling } = get();
    if (polling) return;
    set({ polling: true });
    _clearPoll();
    _pollTimer = setInterval(async () => {
      await get().loadJobs();
      const { items } = get();
      const allTerminal = items.every(
        (i) => i.status === "completed" || i.status === "failed",
      );
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
