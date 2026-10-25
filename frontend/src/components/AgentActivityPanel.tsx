
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { listAgentExecutions } from "@/services/agentExecutionService";
import type {
  AgentExecution,
  AgentExecutionListResponse,
} from "@/types/agentExecution";

import styles from "./AgentActivityPanel.module.css";

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";

  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unknown"
    : date.toLocaleString();
}

function formatDuration(value: number | null | undefined): string {
  if (value == null) return "—";
  if (value < 1000) return `${value} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

function statusLabel(status: AgentExecution["status"]): string {
  return status === "started" ? "Running" : status;
}

function statusClass(status: AgentExecution["status"]): string {
  switch (status) {
    case "started":
      return styles.running;
    case "succeeded":
      return styles.succeeded;
    case "failed":
      return styles.failed;
    case "cancelled":
      return styles.cancelled;
    default:
      return styles.unknown;
  }
}

export default function AgentActivityPanel() {
  const [data, setData] =
    useState<AgentExecutionListResponse | null>(null);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadExecutions = useCallback(async (signal?: AbortSignal) => {
    setRefreshing(true);

    try {
      const result = await listAgentExecutions({
        limit: 10,
        offset: 0,
        signal,
      });

      if (!signal?.aborted) {
        setData(result);
        setError(null);
      }
    } catch (err) {
      if (signal?.aborted) return;

      setError(
        err instanceof Error
          ? err.message
          : "Unable to load agent activity.",
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

    void loadExecutions(controller.signal);

    const intervalId = window.setInterval(() => {
      void loadExecutions();
    }, 15_000);

    return () => {
      controller.abort();
      window.clearInterval(intervalId);
    };
  }, [loadExecutions]);

  const executions = data?.items ?? [];

  const running = executions.filter(
    (item) => item.status === "started",
  ).length;

  const succeeded = executions.filter(
    (item) => item.status === "succeeded",
  ).length;

  const failed = executions.filter(
    (item) => item.status === "failed",
  ).length;

  return (
    <section className={styles.panel} aria-live="polite">
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>AGENT OPERATIONS</span>
          <h2>Recent executions</h2>
          <p>Real execution audit records for your account</p>
        </div>

        <button
          type="button"
          className={styles.refresh}
          onClick={() => void loadExecutions()}
          disabled={refreshing}
        >
          {refreshing ? "Loading…" : "↻ Refresh"}
        </button>
      </header>

      {data && (
        <div className={styles.stats}>
          <div>
            <span>All records</span>
            <strong>{data.total}</strong>
          </div>
          <div>
            <span>Running in list</span>
            <strong>{running}</strong>
          </div>
          <div>
            <span>Succeeded in list</span>
            <strong>{succeeded}</strong>
          </div>
          <div>
            <span>Failed in list</span>
            <strong>{failed}</strong>
          </div>
        </div>
      )}

      {loading && !data && (
        <p className={styles.message}>Loading execution history…</p>
      )}

      {error && !data && (
        <div className={styles.error} role="alert">
          <strong>Execution history unavailable</strong>
          <p>{error}</p>
          <button
            type="button"
            onClick={() => void loadExecutions()}
          >
            Try again
          </button>
        </div>
      )}

      {error && data && (
        <p className={styles.warning}>
          Refresh failed. Showing the last successful response.
        </p>
      )}

      {data && executions.length === 0 && (
        <div className={styles.empty}>
          <strong>No executions recorded yet</strong>
          <p>When ORVYN records an agent execution, it will appear here.</p>
        </div>
      )}

      {executions.length > 0 && (
        <div className={styles.list}>
          {executions.map((execution) => (
            <article
              className={styles.execution}
              key={execution.id}
            >
              <div className={styles.executionTop}>
                <span className={styles.id}>
                  {execution.id.slice(0, 8)}
                </span>

                <span
                  className={`${styles.badge} ${statusClass(execution.status)}`}
                >
                  {statusLabel(execution.status)}
                </span>
              </div>

              <div className={styles.metadata}>
                <span>
                  Started: {formatDate(execution.started_at)}
                </span>
                <span>
                  Duration: {formatDuration(execution.duration_ms)}
                </span>
              </div>

              <div className={styles.progress}>
                <span>
                  Steps: {execution.completed_steps} / {execution.step_count}
                </span>

                <div className={styles.track}>
                  <span
                    style={{
                      width: `${
                        execution.step_count > 0
                          ? Math.min(
                              100,
                              (execution.completed_steps /
                                execution.step_count) *
                                100,
                            )
                          : 0
                      }%`,
                    }}
                  />
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      <footer className={styles.footer}>
        <span>
          {data
            ? `Showing ${executions.length} of ${data.total} records`
            : "Execution data not loaded"}
        </span>

        <Link href="/agent-executions">
          Open execution history →
        </Link>
      </footer>
    </section>
  );
}
