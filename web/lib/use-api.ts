"use client";

import { useState, useEffect, useCallback } from "react";

/**
 * Data source state for the UI.
 *
 * - REAL_API     — API returned real data, show it.
 * - DEMO_FALLBACK — API unreachable or repeatedly failing, showing mock data.
 * - API_ERROR    — API returned an error, show error details + retry.
 * - LOADING      — Initial request in flight.
 */
export type DataSource = "REAL_API" | "DEMO_FALLBACK" | "API_ERROR" | "LOADING";

export interface ApiState<T> {
  data: T;
  dataSource: DataSource;
  loading: boolean;
  error: string | null;
  /** The full URL that was called (useful for debugging). */
  lastUrl: string | null;
  /** HTTP status code if available. */
  lastStatus: number | null;
  refetch: () => void;
}

/**
 * API-first hook with explicit data-source tracking.
 *
 * NEVER silently falls back to mock data — the caller always knows whether
 * the displayed data is real or demo via `dataSource`.
 */
export function useApiWithFallback<T>(
  apiFn: () => Promise<T>,
  mockData: T,
  deps: unknown[] = [],
): ApiState<T> {
  const [data, setData] = useState<T>(mockData);
  const [dataSource, setDataSource] = useState<DataSource>("LOADING");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUrl, setLastUrl] = useState<string | null>(null);
  const [lastStatus, setLastStatus] = useState<number | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setDataSource("LOADING");
    setError(null);
    try {
      const result = await apiFn();
      setData(result);              // result is the raw T, not wrapped
      setDataSource("REAL_API");
      setLastUrl(null);
      setLastStatus(200);
      setError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "API unreachable";
      let url: string | null = null;
      let status: number | null = null;
      if (err && typeof err === "object" && "url" in err) {
        url = (err as Record<string, unknown>).url as string;
      }
      if (err && typeof err === "object" && "status" in err) {
        status = (err as Record<string, unknown>).status as number;
      }

      console.error("[useApiWithFallback] API failed:", { url, status, error: msg });

      setLastUrl(url);
      setLastStatus(status);
      setError(msg);

      if (status === 0 || msg.includes("Cannot reach") || msg.includes("network_error")) {
        setData(mockData);
        setDataSource("DEMO_FALLBACK");
      } else {
        setData(mockData);
        setDataSource("API_ERROR");
      }
    } finally {
      setLoading(false);
    }
  }, deps);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, dataSource, loading, error, lastUrl, lastStatus, refetch: fetchData };
}

/**
 * Simpler version that only tracks the API data source across the whole app.
 * Call `updateGlobalSource(source)` from any page.
 */
let _globalSource: DataSource = "LOADING";
const _listeners = new Set<(s: DataSource) => void>();

export function getGlobalDataSource(): DataSource {
  return _globalSource;
}

export function updateGlobalDataSource(source: DataSource) {
  _globalSource = source;
  _listeners.forEach((fn) => fn(source));
}

export function useGlobalDataSource(): DataSource {
  const [val, setVal] = useState<DataSource>(_globalSource);
  useEffect(() => {
    _listeners.add(setVal);
    return () => { _listeners.delete(setVal); };
  }, []);
  return val;
}

export { API_BASE_URL } from "./api";
