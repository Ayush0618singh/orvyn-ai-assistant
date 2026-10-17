
"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import Link from "next/link";

import { useAuth } from "@/contexts/AuthContext";

import {
  getAgentExecution,
  listAgentExecutions,
} from "@/services/agentExecutionService";

import type {
  AgentExecution,
  AgentExecutionFilter,
  AgentExecutionListResponse,
  AgentExecutionStatus,
} from "@/types/agentExecution";

const PAGE_SIZE = 10;

const filters: {
  label: string;
  value: AgentExecutionFilter;
}[] = [
  { label: "All", value: "all" },
  { label: "Running", value: "started" },
  { label: "Succeeded", value: "succeeded" },
  { label: "Failed", value: "failed" },
  { label: "Cancelled", value: "cancelled" },
];

const statusColors: Record<
  AgentExecutionStatus,
  string
> = {
  started: "#60a5fa",
  succeeded: "#34d399",
  failed: "#fb7185",
  cancelled: "#fbbf24",
};

function formatDate(value: string | null): string {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return date.toLocaleString();
}

function formatDuration(value: number | null): string {
  if (value === null) return "—";

  if (value < 1000) {
    return `${value} ms`;
  }

  return `${(value / 1000).toFixed(2)} s`;
}

function StatusLabel({
  status,
}: {
  status: AgentExecutionStatus;
}) {
  return (
    <span
      style={{
        color: statusColors[status],
        fontWeight: 600,
        textTransform: "capitalize",
      }}
    >
      {status === "started" ? "Running" : status}
    </span>
  );
}

export default function AgentExecutionDashboard() {
  const { user, loading: authLoading } = useAuth();

  const [filter, setFilter] =
    useState<AgentExecutionFilter>("all");

  const [page, setPage] = useState(0);

  const [data, setData] =
    useState<AgentExecutionListResponse | null>(null);

  const [selected, setSelected] =
    useState<AgentExecution | null>(null);

  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] =
    useState<string | null>(null);

  const [refreshKey, setRefreshKey] = useState(0);

  const loadHistory = useCallback(
    async (signal: AbortSignal) => {
      setLoading(true);
      setError(null);

      try {
        const result = await listAgentExecutions({
          status: filter,
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
          signal,
        });

        if (!signal.aborted) {
          setData(result);
        }
      } catch (err) {
        if (!signal.aborted) {
          setData(null);
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load execution history."
          );
        }
      } finally {
        if (!signal.aborted) {
          setLoading(false);
        }
      }
    },
    [filter, page]
  );

  useEffect(() => {
    if (authLoading || !user) {
        return;
    }

    const controller = new AbortController();

    const startLoading = () => {
        void loadHistory(controller.signal);
    };

    queueMicrotask(startLoading);

    return () => {
        controller.abort();
    };
    }, [authLoading, user, loadHistory, refreshKey]);

  async function openDetails(id: string) {
    setSelected(null);
    setDetailError(null);
    setDetailLoading(true);

    try {
      const record = await getAgentExecution(id);
      setSelected(record);
    } catch (err) {
      setDetailError(
        err instanceof Error
          ? err.message
          : "Unable to load execution details."
      );
    } finally {
      setDetailLoading(false);
    }
  }

  const totalPages = data
    ? Math.max(1, Math.ceil(data.total / PAGE_SIZE))
    : 1;

  const surface: React.CSSProperties = {
    background: "#151c2e",
    border: "1px solid #2c3650",
    borderRadius: 16,
    padding: 20,
  };

  const button: React.CSSProperties = {
    background: "#26344e",
    color: "#f1f5f9",
    border: "1px solid #40506c",
    borderRadius: 9,
    padding: "9px 14px",
    cursor: "pointer",
  };

  if (authLoading) {
    return (
      <main style={{ padding: 32 }}>
        Checking your session...
      </main>
    );
  }

  if (!user) {
    return (
      <main
        style={{
          minHeight: "100vh",
          background: "#0b1020",
          color: "#f8fafc",
          padding: 32,
        }}
      >
        <h1>Agent Execution History</h1>
        <p>Please sign in to view your execution history.</p>
        <Link href="/" style={{ color: "#93c5fd" }}>
          Go to ORVYN
        </Link>
      </main>
    );
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "#0b1020",
        color: "#f8fafc",
        padding: "32px 20px",
      }}
    >
      <div
        style={{
          maxWidth: 1100,
          margin: "0 auto",
          display: "grid",
          gap: 24,
        }}
      >
        <header>
          <Link
            href="/"
            style={{
              color: "#93c5fd",
              textDecoration: "none",
            }}
          >
            ← Back to ORVYN
          </Link>

          <h1
            style={{
              fontSize: 30,
              fontWeight: 700,
              marginTop: 16,
            }}
          >
            Agent Execution History
          </h1>

          <p style={{ color: "#94a3b8", marginTop: 8 }}>
            Review your multi-step AI agent executions,
            results, duration and failures.
          </p>
        </header>

        <section style={surface}>
          <div
            style={{
              display: "flex",
              gap: 10,
              flexWrap: "wrap",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 20,
            }}
          >
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 8,
              }}
            >
              {filters.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => {
                    setFilter(item.value);
                    setPage(0);
                    setSelected(null);
                    setDetailError(null);
                  }}
                  aria-pressed={filter === item.value}
                  style={{
                    ...button,
                    background:
                      filter === item.value
                        ? "#3159a7"
                        : "#26344e",
                  }}
                >
                  {item.label}
                </button>
              ))}
            </div>

            <button
              type="button"
              style={button}
              onClick={() => {
                setSelected(null);
                setDetailError(null);
                setRefreshKey((value) => value + 1);
              }}
              disabled={loading}
            >
              {loading ? "Loading..." : "Refresh"}
            </button>
          </div>

          {error && (
            <p role="alert" style={{ color: "#fda4af" }}>
              {error}
            </p>
          )}

          {loading && (
            <p role="status" style={{ color: "#94a3b8" }}>
              Loading execution history...
            </p>
          )}

          {!loading && !error && data?.items.length === 0 && (
            <p style={{ color: "#94a3b8" }}>
              No executions found for this filter.
            </p>
          )}

          {!loading && !error && data && data.items.length > 0 && (
            <>
              <div style={{ overflowX: "auto" }}>
                <table
                  style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    textAlign: "left",
                    minWidth: 700,
                  }}
                >
                  <thead>
                    <tr style={{ color: "#94a3b8" }}>
                      <th style={{ padding: 12 }}>Status</th>
                      <th style={{ padding: 12 }}>Steps</th>
                      <th style={{ padding: 12 }}>Duration</th>
                      <th style={{ padding: 12 }}>Started</th>
                      <th style={{ padding: 12 }}>Details</th>
                    </tr>
                  </thead>

                  <tbody>
                    {data.items.map((execution) => (
                      <tr
                        key={execution.id}
                        style={{
                          borderTop: "1px solid #2c3650",
                        }}
                      >
                        <td style={{ padding: 12 }}>
                          <StatusLabel status={execution.status} />
                        </td>
                        <td style={{ padding: 12 }}>
                          {execution.completed_steps}/
                          {execution.step_count}
                        </td>
                        <td style={{ padding: 12 }}>
                          {formatDuration(execution.duration_ms)}
                        </td>
                        <td style={{ padding: 12 }}>
                          {formatDate(execution.started_at)}
                        </td>
                        <td style={{ padding: 12 }}>
                          <button
                            type="button"
                            style={button}
                            onClick={() => void openDetails(execution.id)}
                          >
                            View
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginTop: 20,
                  gap: 12,
                }}
              >
                <span style={{ color: "#94a3b8" }}>
                  Page {page + 1} of {totalPages} · {data.total} records
                </span>

                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    type="button"
                    style={button}
                    disabled={page === 0 || loading}
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                  >
                    Previous
                  </button>

                  <button
                    type="button"
                    style={button}
                    disabled={
                      loading || (page + 1) * PAGE_SIZE >= data.total
                    }
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          )}
        </section>

        {(detailLoading || detailError || selected) && (
          <section style={surface}>
            <h2
              style={{
                fontSize: 21,
                fontWeight: 600,
                marginBottom: 16,
              }}
            >
              Execution Details
            </h2>

            {detailLoading && <p>Loading details...</p>}

            {detailError && (
              <p role="alert" style={{ color: "#fda4af" }}>
                {detailError}
              </p>
            )}

            {selected && !detailLoading && (
              <dl
                style={{
                  display: "grid",
                  gridTemplateColumns:
                    "repeat(auto-fit, minmax(220px, 1fr))",
                  gap: 16,
                  overflowWrap: "anywhere",
                }}
              >
                <div>
                  <dt style={{ color: "#94a3b8" }}>Execution ID</dt>
                  <dd>{selected.id}</dd>
                </div>
                <div>
                  <dt style={{ color: "#94a3b8" }}>Status</dt>
                  <dd>
                    <StatusLabel status={selected.status} />
                  </dd>
                </div>
                <div>
                  <dt style={{ color: "#94a3b8" }}>Completed Steps</dt>
                  <dd>
                    {selected.completed_steps}/{selected.step_count}
                  </dd>
                </div>
                <div>
                  <dt style={{ color: "#94a3b8" }}>Duration</dt>
                  <dd>{formatDuration(selected.duration_ms)}</dd>
                </div>
                <div>
                  <dt style={{ color: "#94a3b8" }}>Started</dt>
                  <dd>{formatDate(selected.started_at)}</dd>
                </div>
                <div>
                  <dt style={{ color: "#94a3b8" }}>Finished</dt>
                  <dd>{formatDate(selected.finished_at)}</dd>
                </div>
                <div>
                  <dt style={{ color: "#94a3b8" }}>Failure Category</dt>
                  <dd>{selected.failure_category ?? "None"}</dd>
                </div>
              </dl>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
