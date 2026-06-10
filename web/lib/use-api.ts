"use client";

import { useState, useEffect, useCallback } from "react";

/**
 * API-first with mock fallback.
 *
 * - Tries `apiFn` first.
 * - On success: returns data + `isDemo: false`.
 * - On failure: returns `mockData` + `isDemo: true`.
 * - `loading` is true until the first resolution.
 */
export function useApiWithFallback<T>(
  apiFn: () => Promise<T>,
  mockData: T,
  deps: unknown[] = [],
) {
  const [data, setData] = useState<T>(mockData);
  const [isDemo, setIsDemo] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await apiFn();
      setData(result);
      setIsDemo(false);
      setError(null);
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "API unreachable";
      console.warn("[useApiWithFallback] API failed, using mock data:", msg);
      setData(mockData);
      setIsDemo(true);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, deps);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, isDemo, loading, error, refetch: fetchData };
}
