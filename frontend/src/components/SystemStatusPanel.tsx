
"use client";

import styles from "./SystemStatusPanel.module.css";
import { useSystemStatus } from "@/hooks/useSystemStatus";

function formatBytes(bytes: number | null): string {
  if (bytes === null || !Number.isFinite(bytes)) {
    return "Unavailable";
  }

  const gb = bytes / (1024 ** 3);
  return `${gb.toFixed(1)} GB`;
}

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function metricValue(value: number | null): string {
  return value === null ? "N/A" : `${Math.round(value)}%`;
}

export default function SystemStatusPanel() {
  const {
    data,
    loading,
    refreshing,
    error,
    refresh,
  } = useSystemStatus();

  const databaseOnline = data?.database === "online";
  const serverOnline = data?.status === "online";

  return (
    <section className={styles.panel} aria-live="polite">
      <div className={styles.heading}>
        <div>
          <span className={styles.eyebrow}>LIVE SYSTEM STATUS</span>
          <h2>ORVYN infrastructure</h2>
        </div>

        <button
          type="button"
          className={styles.refresh}
          onClick={() => void refresh()}
          disabled={refreshing}
        >
          {refreshing ? "Checking…" : "↻ Refresh"}
        </button>
      </div>

      {loading && !data ? (
        <p className={styles.message}>Connecting to ORVYN backend…</p>
      ) : error && !data ? (
        <div className={styles.error} role="alert">
          <strong>Backend status unavailable</strong>
          <p>{error}</p>
          <button type="button" onClick={() => void refresh()}>
            Try again
          </button>
        </div>
      ) : data ? (
        <>
          <div className={styles.statusRow}>
            <div className={styles.statusItem}>
              <span className={`${styles.dot} ${serverOnline ? styles.green : styles.amber}`} />
              <span>
                <small>API SERVER</small>
                <strong>{data.status.toUpperCase()}</strong>
              </span>
            </div>

            <div className={styles.statusItem}>
              <span className={`${styles.dot} ${databaseOnline ? styles.green : styles.red}`} />
              <span>
                <small>DATABASE</small>
                <strong>{data.database.toUpperCase()}</strong>
              </span>
            </div>
          </div>

          <div className={styles.metrics}>
            <div className={styles.metric}>
              <span>CPU usage</span>
              <strong>{metricValue(data.resources.cpu_percent)}</strong>
              {data.resources.cpu_percent !== null && (
                <div className={styles.track}>
                  <span
                    style={{
                      width: `${Math.min(100, Math.max(0, data.resources.cpu_percent))}%`,
                    }}
                  />
                </div>
              )}
            </div>

            <div className={styles.metric}>
              <span>Memory usage</span>
              <strong>{metricValue(data.resources.memory_percent)}</strong>
              {data.resources.memory_percent !== null && (
                <div className={styles.track}>
                  <span
                    style={{
                      width: `${Math.min(100, Math.max(0, data.resources.memory_percent))}%`,
                    }}
                  />
                </div>
              )}
            </div>
          </div>

          <div className={styles.details}>
            <div>
              <span>Backend uptime</span>
              <strong>{formatUptime(data.uptime_seconds)}</strong>
            </div>
            <div>
              <span>Python</span>
              <strong>{data.python_version}</strong>
            </div>
            <div>
              <span>Host OS</span>
              <strong>{data.platform}</strong>
            </div>
            <div>
              <span>Physical memory</span>
              <strong>
                {formatBytes(data.resources.memory_used_bytes)}
                {data.resources.memory_total_bytes !== null
                  ? ` / ${formatBytes(data.resources.memory_total_bytes)}`
                  : ""}
              </strong>
            </div>
          </div>

          {!data.resources.available && (
            <p className={styles.note}>
              CPU and memory metrics require the optional psutil package.
            </p>
          )}

          {error && (
            <p className={styles.note}>
              The latest refresh failed; displaying the last successful response.
            </p>
          )}

          <p className={styles.timestamp}>
            Last updated: {new Date(data.timestamp).toLocaleTimeString()}
          </p>
        </>
      ) : null}
    </section>
  );
}
