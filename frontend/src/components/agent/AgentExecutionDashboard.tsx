
"use client";

import {
  useCallback,
  useEffect,
  useRef,
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
const REFRESH_INTERVAL_MS = 5000;

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

const statusColors: Record<AgentExecutionStatus, string> = {
  started: "#60a5fa",
  succeeded: "#34d399",
  failed: "#fb7185",
  cancelled: "#fbbf24",
};

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

function StatusLabel({ status }: { status: AgentExecutionStatus }) {
  return (
    <span
      style={{
        color: statusColors[status],
        fontWeight: 700,
        textTransform: "capitalize",
      }}
    >
      <span aria-hidden="true">
        {status === "started"
          ? "● "
          : status === "succeeded"
            ? "✓ "
            : status === "failed"
              ? "✕ "
              : "Ⅱ "}
      </span>
      {status === "started" ? "Running" : status}
    </span>
  );
}

function MetricCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number;
  accent: string;
}) {
  return (
    <div
      style={{
        background: "#151c2e",
        border: "1px solid #2c3650",
        borderRadius: 14,
        padding: 18,
        minWidth: 0,
      }}
    >
      <p style={{ color: "#94a3b8", fontSize: 13 }}>{label}</p>
      <p
        style={{
          color: accent,
          fontSize: 27,
          fontWeight: 750,
          marginTop: 8,
          overflowWrap: "anywhere",
        }}
      >
        {value}
      </p>
    </div>
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
  const [detailError, setDetailError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const selectedIdRef = useRef<string | null>(null);

  const loadHistory = useCallback(
    async (signal: AbortSignal, background = false) => {
      if (!background) setLoading(true);
      setError(null);

      try {
        const result = await listAgentExecutions({
          status: filter,
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
          signal,
        });

        if (signal.aborted) return;

        setData(result);
        setLastUpdated(new Date().toISOString());

        // Refresh an open detail panel without changing the selected record.
        const selectedId = selectedIdRef.current;
        if (selectedId) {
          const stillListed = result.items.some(
            (item) => item.id === selectedId,
          );

          if (!stillListed && filter !== "all") {
            selectedIdRef.current = null;
            setSelected(null);
          }
        }
      } catch (err) {
        if (!signal.aborted) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load execution history.",
          );
        }
      } finally {
        if (!signal.aborted && !background) {
          setLoading(false);
        }
      }
    },
    [filter, page],
  );

  useEffect(() => {
    if (authLoading || !user) return;

    const controller = new AbortController();
    void loadHistory(controller.signal);

    return () => controller.abort();
  }, [authLoading, user, loadHistory, refreshKey]);

  const hasRunningExecutions =
    data?.items.some((item) => item.status === "started") ?? false;

  useEffect(() => {
    if (
      authLoading ||
      !user ||
      !autoRefresh ||
      !hasRunningExecutions
    ) {
      return;
    }

    const controller = new AbortController();
    const interval = window.setInterval(() => {
      void loadHistory(controller.signal, true);
    }, REFRESH_INTERVAL_MS);

    return () => {
      window.clearInterval(interval);
      controller.abort();
    };
  }, [
    authLoading,
    user,
    autoRefresh,
    hasRunningExecutions,
    loadHistory,
  ]);

  async function openDetails(id: string) {
    selectedIdRef.current = id;
    setSelected(null);
    setDetailError(null);
    setDetailLoading(true);

    try {
      const record = await getAgentExecution(id);
      if (selectedIdRef.current === id) {
        setSelected(record);
      }
    } catch (err) {
      if (selectedIdRef.current === id) {
        setDetailError(
          err instanceof Error
            ? err.message
            : "Unable to load execution details.",
        );
      }
    } finally {
      if (selectedIdRef.current === id) {
        setDetailLoading(false);
      }
    }
  }

  function closeDetails() {
    selectedIdRef.current = null;
    setSelected(null);
    setDetailError(null);
    setDetailLoading(false);
  }

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const runningCount = items.filter(
    (item) => item.status === "started",
  ).length;
  const succeededCount = items.filter(
    (item) => item.status === "succeeded",
  ).length;
  const failedCount = items.filter(
    (item) => item.status === "failed",
  ).length;

  const surface: React.CSSProperties = {
    background: "#151c2e",
    border: "1px solid #2c3650",
    borderRadius: 16,
    padding: 20,
    minWidth: 0,
  };

  const button: React.CSSProperties = {
    background: "#26344e",
    color: "#f1f5f9",
    border: "1px solid #40506c",
    borderRadius: 9,
    padding: "9px 14px",
    cursor: "pointer",
    fontSize: 13,
  };

  if (authLoading) {
    return (
      <main
        style={{
          minHeight: "100vh",
          background: "#0b1020",
          color: "#f8fafc",
          padding: 32,
        }}
      >
        Checking your session…
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
        <h1 style={{ fontSize: 28, fontWeight: 750 }}>
          Agent Execution History
        </h1>
        <p style={{ color: "#94a3b8", marginTop: 12 }}>
          Please sign in to view your execution history.
        </p>
        <Link
          href="/"
          style={{
            display: "inline-block",
            marginTop: 16,
            color: "#93c5fd",
          }}
        >
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
          maxWidth: 1180,
          margin: "0 auto",
          display: "grid",
          gap: 24,
        }}
      >
        <header>
          <Link
            href="/command-center"
            style={{
              color: "#93c5fd",
              textDecoration: "none",
              fontSize: 14,
            }}
          >
            ← Back to Command Center
          </Link>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              gap: 16,
              flexWrap: "wrap",
              marginTop: 18,
            }}
          >
            <div>
              <p
                style={{
                  color: "#38bdf8",
                  fontSize: 12,
                  fontWeight: 750,
                  letterSpacing: 2,
                  textTransform: "uppercase",
                }}
              >
                ORVYN / Operations
              </p>
              <h1
                style={{
                  fontSize: 30,
                  fontWeight: 800,
                  marginTop: 8,
                }}
              >
                Agent Execution Monitor
              </h1>
              <p
                style={{
                  color: "#94a3b8",
                  marginTop: 8,
                  maxWidth: 680,
                  lineHeight: 1.6,
                }}
              >
                Inspect audited agent runs, progress, execution duration,
                and failure outcomes.
              </p>
            </div>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button
                type="button"
                style={{
                  ...button,
                  background: autoRefresh ? "#123d42" : "#26344e",
                  borderColor: autoRefresh ? "#167e80" : "#40506c",
                }}
                aria-pressed={autoRefresh}
                onClick={() => setAutoRefresh((value) => !value)}
              >
                Auto-refresh: {autoRefresh ? "On" : "Off"}
              </button>
              <button
                type="button"
                style={button}
                disabled={loading}
                onClick={() => {
                  setRefreshKey((value) => value + 1);
                }}
              >
                {loading ? "Refreshing…" : "Refresh now"}
              </button>
            </div>
          </div>

          <p
            style={{
              color: "#64748b",
              fontSize: 12,
              marginTop: 12,
            }}
            aria-live="polite"
          >
            {lastUpdated
              ? `Last updated: ${formatDate(lastUpdated)}`
              : "Waiting for first data load"}
            {autoRefresh && hasRunningExecutions
              ? " · Live polling every 5 seconds while runs are active"
              : ""}
          </p>
        </header>

        <section
          aria-label="Execution summary"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: 14,
          }}
        >
          <MetricCard
            label="Executions in current page"
            value={items.length}
            accent="#e2e8f0"
          />
          <MetricCard
            label="Running on current page"
            value={runningCount}
            accent="#60a5fa"
          />
          <MetricCard
            label="Succeeded on current page"
            value={succeededCount}
            accent="#34d399"
          />
          <MetricCard
            label="Failed on current page"
            value={failedCount}
            accent="#fb7185"
          />
        </section>

        <section style={surface}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 14,
              marginBottom: 18,
            }}
          >
            <h2 style={{ fontSize: 18, fontWeight: 700 }}>
              Execution history
            </h2>
            <span style={{ color: "#94a3b8", fontSize: 13 }}>
              {total} total records
            </span>
          </div>

          <div
            role="group"
            aria-label="Filter executions by status"
            style={{
              display: "flex",
              gap: 8,
              flexWrap: "wrap",
              marginBottom: 20,
            }}
          >
            {filters.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => {
                  setFilter(item.value);
                  setPage(0);
                  closeDetails();
                }}
                aria-pressed={filter === item.value}
                style={{
                  ...button,
                  background:
                    filter === item.value ? "#3159a7" : "#26344e",
                  borderColor:
                    filter === item.value ? "#60a5fa" : "#40506c",
                }}
              >
                {item.label}
              </button>
            ))}
          </div>

          {error && (
            <div
              role="alert"
              style={{
                background: "#351923",
                border: "1px solid #713044",
                color: "#fda4af",
                padding: 14,
                borderRadius: 10,
                marginBottom: 16,
              }}
            >
              <p>{error}</p>
              <button
                type="button"
                style={{ ...button, marginTop: 10 }}
                onClick={() => setRefreshKey((value) => value + 1)}
              >
                Retry
              </button>
            </div>
          )}

          {loading && !data && (
            <p role="status" style={{ color: "#94a3b8", padding: 12 }}>
              Loading execution history…
            </p>
          )}

          {!loading && !error && items.length === 0 && (
            <div
              style={{
                textAlign: "center",
                padding: "44px 16px",
                color: "#94a3b8",
              }}
            >
              <p style={{ fontSize: 17, color: "#e2e8f0" }}>
                No executions found
              </p>
              <p style={{ marginTop: 8, fontSize: 13 }}>
                Try another status filter or run an agent task first.
              </p>
            </div>
          )}

          {items.length > 0 && (
            <>
              <div style={{ overflowX: "auto" }}>
                <table
                  style={{
                    width: "100%",
                    minWidth: 700,
                    borderCollapse: "collapse",
                    textAlign: "left",
                  }}
                >
                  <thead>
                    <tr
                      style={{
                        color: "#94a3b8",
                        borderBottom: "1px solid #2c3650",
                      }}
                    >
                      {["Status", "Progress", "Duration", "Started", "Details"].map(
                        (heading) => (
                          <th
                            key={heading}
                            scope="col"
                            style={{
                              padding: "13px 12px",
                              fontSize: 12,
                              fontWeight: 650,
                            }}
                          >
                            {heading}
                          </th>
                        ),
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((execution) => {
                      const percentage =
                        execution.step_count > 0
                          ? Math.min(
                              100,
                              Math.round(
                                (execution.completed_steps /
                                  execution.step_count) *
                                  100,
                              ),
                            )
                          : 0;

                      return (
                        <tr
                          key={execution.id}
                          style={{
                            borderBottom: "1px solid #253047",
                          }}
                        >
                          <td style={{ padding: 13 }}>
                            <StatusLabel status={execution.status} />
                          </td>
                          <td style={{ padding: 13, minWidth: 150 }}>
                            <div
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                gap: 8,
                                color: "#cbd5e1",
                                fontSize: 12,
                                marginBottom: 7,
                              }}
                            >
                              <span>
                                {execution.completed_steps}/
                                {execution.step_count} steps
                              </span>
                              <span>{percentage}%</span>
                            </div>
                            <div
                              style={{
                                height: 6,
                                background: "#29344b",
                                borderRadius: 99,
                                overflow: "hidden",
                              }}
                            >
                              <div
                                style={{
                                  height: "100%",
                                  width: `${percentage}%`,
                                  background:
                                    execution.status === "failed"
                                      ? "#fb7185"
                                      : execution.status === "succeeded"
                                        ? "#34d399"
                                        : "#60a5fa",
                                  borderRadius: 99,
                                  transition: "width 200ms ease",
                                }}
                              />
                            </div>
                          </td>
                          <td style={{ padding: 13 }}>
                            {formatDuration(execution.duration_ms)}
                          </td>
                          <td style={{ padding: 13, whiteSpace: "nowrap" }}>
                            {formatDate(execution.started_at)}
                          </td>
                          <td style={{ padding: 13 }}>
                            <button
                              type="button"
                              style={button}
                              onClick={() => void openDetails(execution.id)}
                            >
                              View details
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 12,
                  flexWrap: "wrap",
                  marginTop: 20,
                }}
              >
                <span style={{ color: "#94a3b8", fontSize: 13 }}>
                  Page {page + 1} of {totalPages}
                </span>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    type="button"
                    style={button}
                    disabled={page === 0 || loading}
                    onClick={() => setPage((value) => Math.max(0, value - 1))}
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    style={button}
                    disabled={loading || (page + 1) * PAGE_SIZE >= total}
                    onClick={() => setPage((value) => value + 1)}
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          )}
        </section>

        {(detailLoading || detailError || selected) && (
          <section style={surface} aria-labelledby="execution-details-title">
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: 12,
                marginBottom: 18,
              }}
            >
              <h2
                id="execution-details-title"
                style={{ fontSize: 20, fontWeight: 750 }}
              >
                Execution details
              </h2>
              <button
                type="button"
                style={button}
                onClick={closeDetails}
              >
                Close
              </button>
            </div>

            {detailLoading && (
              <p role="status" style={{ color: "#94a3b8" }}>
                Loading execution details…
              </p>
            )}

            {detailError && (
              <p role="alert" style={{ color: "#fda4af" }}>
                {detailError}
              </p>
            )}

            {selected && !detailLoading && (
              <>
                <dl
                  style={{
                    display: "grid",
                    gridTemplateColumns:
                      "repeat(auto-fit, minmax(200px, 1fr))",
                    gap: 18,
                    overflowWrap: "anywhere",
                  }}
                >
                  <div>
                    <dt style={{ color: "#94a3b8", fontSize: 12 }}>
                      Execution ID
                    </dt>
                    <dd style={{ marginTop: 6, fontSize: 13 }}>
                      {selected.id}
                    </dd>
                  </div>
                  <div>
                    <dt style={{ color: "#94a3b8", fontSize: 12 }}>
                      Status
                    </dt>
                    <dd style={{ marginTop: 6 }}>
                      <StatusLabel status={selected.status} />
                    </dd>
                  </div>
                  <div>
                    <dt style={{ color: "#94a3b8", fontSize: 12 }}>
                      Progress
                    </dt>
                    <dd style={{ marginTop: 6 }}>
                      {selected.completed_steps}/{selected.step_count} steps
                    </dd>
                  </div>
                  <div>
                    <dt style={{ color: "#94a3b8", fontSize: 12 }}>
                      Duration
                    </dt>
                    <dd style={{ marginTop: 6 }}>
                      {formatDuration(selected.duration_ms)}
                    </dd>
                  </div>
                  <div>
                    <dt style={{ color: "#94a3b8", fontSize: 12 }}>
                      Started at
                    </dt>
                    <dd style={{ marginTop: 6 }}>
                      {formatDate(selected.started_at)}
                    </dd>
                  </div>
                  <div>
                    <dt style={{ color: "#94a3b8", fontSize: 12 }}>
                      Finished at
                    </dt>
                    <dd style={{ marginTop: 6 }}>
                      {formatDate(selected.finished_at)}
                    </dd>
                  </div>
                  <div>
                    <dt style={{ color: "#94a3b8", fontSize: 12 }}>
                      Failure category
                    </dt>
                    <dd style={{ marginTop: 6 }}>
                      {selected.failure_category ?? "None"}
                    </dd>
                  </div>
                  <div>
                    <dt style={{ color: "#94a3b8", fontSize: 12 }}>
                      Last heartbeat
                    </dt>
                    <dd style={{ marginTop: 6 }}>
                      {"last_heartbeat_at" in selected
                        ? formatDate(
                            (
                              selected as AgentExecution & {
                                last_heartbeat_at?: string | null;
                              }
                            ).last_heartbeat_at,
                          )
                        : "Not provided by API"}
                    </dd>
                  </div>
                </dl>

                <div
                  style={{
                    marginTop: 20,
                    padding: 14,
                    background: "#0d1425",
                    border: "1px solid #2c3650",
                    borderRadius: 10,
                  }}
                >
                  <p style={{ color: "#94a3b8", fontSize: 12 }}>
                    Execution record
                  </p>
                  <p
                    style={{
                      color: "#cbd5e1",
                      fontSize: 13,
                      lineHeight: 1.7,
                      marginTop: 6,
                    }}
                  >
                    This panel shows the audited status and progress returned
                    by the backend. It does not retry, resume, or modify an
                    execution.
                  </p>
                </div>
              </>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
