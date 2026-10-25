
"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  getSystemStatus,
} from "@/services/systemStatusService";

import type {
  SystemStatus,
} from "@/services/systemStatusService";

export function useSystemStatus() {
  const [data, setData] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setRefreshing(true);

    try {
      const result = await getSystemStatus(signal);

      if (!signal?.aborted) {
        setData(result);
        setError(null);
      }
    } catch (err) {
      if (signal?.aborted) return;

      setError(
        err instanceof Error
          ? err.message
          : "Unable to load system status.",
      );
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    void refresh(controller.signal);

    const intervalId = window.setInterval(() => {
      void refresh();
    }, 15_000);

    return () => {
      controller.abort();
      window.clearInterval(intervalId);
    };
  }, [refresh]);

  return {
    data,
    loading,
    refreshing,
    error,
    refresh: () => refresh(),
  };
}
