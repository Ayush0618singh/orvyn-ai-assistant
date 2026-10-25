
"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { getBackendHealth, API_URL } from "@/services/api";
import { getAgentPlans } from "@/services/agentPlanService";
import type { AgentPlanSummary } from "@/types/agentPlan";

import styles from "./OrvynCommandCenter.module.css";

type ConnectionStatus = "checking" | "online" | "offline";

type ModuleItem = {
  id: string;
  title: string;
  description: string;
  href: string;
  icon: string;
  category: string;
  available: boolean;
};

const modules: ModuleItem[] = [
  {
    id: "chat",
    title: "AI Chat",
    description: "Multilingual conversations and AI assistance",
    href: "/",
    icon: "◉",
    category: "Intelligence",
    available: true,
  },
  {
    id: "agents",
    title: "Agent Workspace",
    description: "Create and inspect persistent task plans",
    href: "/agent-workspace",
    icon: "⌘",
    category: "Agents",
    available: true,
  },
  {
    id: "memory",
    title: "Memory",
    description: "Review stored personal memories",
    href: "/memories",
    icon: "◎",
    category: "Knowledge",
    available: true,
  },
  {
    id: "knowledge",
    title: "Knowledge & RAG",
    description: "Document-grounded AI assistance",
    href: "/",
    icon: "▤",
    category: "Knowledge",
    available: false,
  },
  {
    id: "tools",
    title: "Tools & Approvals",
    description: "Review permission-controlled actions",
    href: "/tool-approvals",
    icon: "⚙",
    category: "Security",
    available: true,
  },
  {
    id: "executions",
    title: "Agent Executions",
    description: "Inspect execution status, progress and audit history",
    href: "/agent-executions",
    icon: "↗",
    category: "Agents",
    available: true,
  },
  {
    id: "voice",
    title: "Voice Assistant",
    description: "Voice interaction capabilities",
    href: "/",
    icon: "♫",
    category: "Multimodal",
    available: false,
  },
];

const categories = [
  "All",
  "Intelligence",
  "Agents",
  "Knowledge",
  "Security",
  "Multimodal",
];

function formatClock(date: Date): string {
  return date.toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function formatDate(date: Date): string {
  return date.toLocaleDateString("en-IN", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatPlanStatus(status: string): string {
  return status.replaceAll("_", " ").toUpperCase();
}

function CoreVisual({ status }: { status: ConnectionStatus }) {
  return (
    <div className={styles.coreStage} aria-label="ORVYN AI core">
      <div className={styles.coreGrid} />
      <div className={styles.orbitOuter}>
        <span className={styles.orbitMarker} />
      </div>
      <div className={styles.orbitMiddle} />
      <div className={styles.orbitInner} />
      <div className={styles.coreGlow} />

      <div className={styles.coreCenter}>
        <div className={styles.coreEyes}>
          <span />
          <span />
        </div>
        <div className={styles.coreName}>ORVYN</div>
        <div className={styles.coreSub}>THINK • PLAN • ACT</div>
      </div>

      <div className={styles.coreBottom}>
        <span
          className={`${styles.statusDot} ${
            status === "online"
              ? styles.onlineDot
              : status === "offline"
                ? styles.offlineDot
                : ""
          }`}
        />
        {status === "online"
          ? "BACKEND CONNECTED"
          : status === "checking"
            ? "CHECKING CONNECTION"
            : "BACKEND DISCONNECTED"}
      </div>
    </div>
  );
}

export default function OrvynCommandCenter() {
  const [connection, setConnection] =
    useState<ConnectionStatus>("checking");

  const [clock, setClock] = useState<Date | null>(null);
  const [query, setQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState("All");
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  const [plans, setPlans] = useState<AgentPlanSummary[]>([]);
  const [totalPlans, setTotalPlans] = useState<number | null>(null);
  const [plansError, setPlansError] = useState<string | null>(null);
  const [plansLoading, setPlansLoading] = useState(true);

  const [healthError, setHealthError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const activeRequest = useRef<AbortController | null>(null);

  const refreshDashboard = useCallback(async () => {
    activeRequest.current?.abort();

    const controller = new AbortController();
    activeRequest.current = controller;

    setConnection("checking");
    setRefreshing(true);
    setHealthError(null);
    setPlansError(null);
    setPlansLoading(true);

    const checkedAt = () =>
      new Date().toLocaleTimeString("en-IN");

    const healthPromise = (async () => {
      try {
        // Use the project's existing health service and configured API URL.
        const health = await getBackendHealth();

        if (controller.signal.aborted) return;

        if (
          typeof health.status === "string" &&
          health.status.toLowerCase() === "healthy"
        ) {
          setConnection("online");
          setHealthError(null);
        } else {
          setConnection("offline");
          setHealthError("Health endpoint returned an unexpected status.");
        }
      } catch (error) {
        if (controller.signal.aborted) return;

        setConnection("offline");
        setHealthError(
          error instanceof Error
            ? error.message
            : "Unable to reach the backend health endpoint."
        );
      } finally {
        if (!controller.signal.aborted) {
          setLastChecked(checkedAt());
        }
      }
    })();

    const plansPromise = (async () => {
      try {
        // This endpoint is authenticated and returns plans belonging to the
        // currently authenticated user. Do not treat auth failures as zero.
        const response = await getAgentPlans(20, 0);

        if (controller.signal.aborted) return;

        setPlans(response.items);
        setTotalPlans(response.total);
        setPlansError(null);
      } catch (error) {
        if (controller.signal.aborted) return;

        setPlans([]);
        setTotalPlans(null);
        setPlansError(
          error instanceof Error
            ? error.message
            : "Unable to load agent plans."
        );
      } finally {
        if (!controller.signal.aborted) {
          setPlansLoading(false);
        }
      }
    })();

    try {
      await Promise.all([healthPromise, plansPromise]);
    } finally {
      if (!controller.signal.aborted) {
        setRefreshing(false);
      }

      if (activeRequest.current === controller) {
        activeRequest.current = null;
      }
    }
  }, []);

  useEffect(() => {
    void refreshDashboard();

    const interval = window.setInterval(() => {
      setClock(new Date());
    }, 1000);

    return () => {
      window.clearInterval(interval);
      activeRequest.current?.abort();
    };
  }, [refreshDashboard]);

  const filteredModules = modules.filter((module) => {
    const categoryMatches =
      activeCategory === "All" ||
      module.category === activeCategory;

    const searchText =
      `${module.title} ${module.description} ${module.category}`
        .toLowerCase();

    return (
      categoryMatches &&
      searchText.includes(query.trim().toLowerCase())
    );
  });

  const runningPlans = plans.filter(
    (plan) => plan.status === "running"
  ).length;

  const awaitingPlans = plans.filter(
    (plan) => plan.status === "awaiting_approval"
  ).length;

  return (
    <div className={styles.shell}>
      <div className={styles.backgroundGlow} />

      <aside className={styles.sidebar}>
        <Link href="/command-center" className={styles.brand}>
          <span className={styles.brandSymbol}>◈</span>
          <span>
            <strong>ORVYN</strong>
            <small>AI OPERATING SYSTEM</small>
          </span>
        </Link>

        <div className={styles.navLabel}>COMMAND SYSTEM</div>

        <nav className={styles.navigation} aria-label="Main navigation">
          <Link
            href="/command-center"
            className={styles.navActive}
            aria-current="page"
          >
            <span>◈</span>
            Command Center
          </Link>
          <Link href="/">
            <span>◉</span>
            AI Chat
          </Link>
          <Link href="/agent-workspace">
            <span>⌘</span>
            Agent Workspace
          </Link>
          <Link href="/memories">
            <span>◎</span>
            Memory
          </Link>
          <Link href="/tool-approvals">
            <span>⚙</span>
            Tool Approvals
          </Link>
          <Link href="/agent-executions">
            <span>↗</span>
            Agent Executions
          </Link>
        </nav>

        <div className={styles.sidebarDivider} />
        <div className={styles.navLabel}>INTELLIGENCE MODULES</div>

        <div className={styles.sidebarModules}>
          <Link href="/memories">
            <span>◎</span>
            Long-Term Memory
          </Link>
          <Link href="/tool-approvals">
            <span>⚙</span>
            Tools &amp; Approvals
          </Link>
          <Link href="/agent-executions">
            <span>↗</span>
            Agent Executions
          </Link>
          <Link href="/agent-workspace">
            <span>⌘</span>
            Agent Workspace
          </Link>
        </div>

        <div className={styles.sidebarFooter}>
          <div className={styles.securitySymbol}>◈</div>
          <strong>SECURITY FIRST</strong>
          <p>
            Sensitive actions require authorization and policy checks.
          </p>
        </div>
      </aside>

      <div className={styles.mainArea}>
        <header className={styles.topbar}>
          <div>
            <div className={styles.eyebrow}>
              PERSONAL AGENTIC AI SYSTEM
            </div>
            <h1>
              Command <span>Center</span>
            </h1>
            <p>Your intelligence. Your tools. Your control.</p>
          </div>

          <div className={styles.topbarRight}>
            <div className={styles.clock}>
              <strong>
                {clock ? formatClock(clock) : "--:--:--"}
              </strong>
              <small>
                {clock ? formatDate(clock) : "Loading date..."}
              </small>
            </div>

            <div className={styles.connectionBadge}>
              <span
                className={`${styles.statusDot} ${
                  connection === "online"
                    ? styles.onlineDot
                    : connection === "offline"
                      ? styles.offlineDot
                      : ""
                }`}
              />
              {connection === "online"
                ? "API ONLINE"
                : connection === "checking"
                  ? "CONNECTING"
                  : "API OFFLINE"}
            </div>
          </div>
        </header>

        <main className={styles.content}>
          <section
            className={styles.heroGrid}
            aria-label="ORVYN command overview"
          >
            <div className={styles.panel}>
              <div className={styles.panelHeader}>
                <span>SYSTEM CONNECTIVITY</span>
                <span className={styles.panelCode}>SYS-01</span>
              </div>

              <div className={styles.systemRows}>
                <div>
                  <span>Frontend</span>
                  <strong className={styles.good}>ACTIVE</strong>
                </div>
                <div>
                  <span>Backend API</span>
                  <strong
                    className={
                      connection === "online"
                        ? styles.good
                        : connection === "offline"
                          ? styles.warning
                          : styles.muted
                    }
                  >
                    {connection.toUpperCase()}
                  </strong>
                </div>
                <div>
                  <span>Agent Plan API</span>
                  <strong
                    className={
                      plansError
                        ? styles.warning
                        : plansLoading
                          ? styles.muted
                          : styles.good
                    }
                  >
                    {plansLoading
                      ? "CHECKING"
                      : plansError
                        ? "UNAVAILABLE"
                        : "RESPONDING"}
                  </strong>
                </div>
                <div>
                  <span>Trusted Execution</span>
                  <strong className={styles.warning}>
                    NOT VERIFIED HERE
                  </strong>
                </div>
              </div>

              {healthError && (
                <p className={styles.panelFootnote} role="alert">
                  Health check: {healthError}
                </p>
              )}

              <button
                type="button"
                className={styles.outlineButton}
                onClick={() => void refreshDashboard()}
                disabled={refreshing}
              >
                {refreshing
                  ? "Refreshing..."
                  : "↻ Refresh System Status"}
              </button>

              {lastChecked && (
                <p className={styles.panelFootnote}>
                  Last checked: {lastChecked}
                </p>
              )}
            </div>

            <div className={styles.corePanel}>
              <div className={styles.coreHeading}>
                <span>ORVYN INTELLIGENCE CORE</span>
                <span>CORE-01</span>
              </div>

              <CoreVisual status={connection} />

              <div className={styles.coreActions}>
                <Link href="/" className={styles.primaryButton}>
                  Open AI Chat →
                </Link>
                <Link
                  href="/agent-workspace"
                  className={styles.outlineButton}
                >
                  Agent Workspace
                </Link>
              </div>
            </div>

            <div className={styles.panel}>
              <div className={styles.panelHeader}>
                <span>AGENT PLAN OVERVIEW</span>
                <span className={styles.panelCode}>AGT-01</span>
              </div>

              <div className={styles.systemRows}>
                <div>
                  <span>Total plans</span>
                  <strong>
                    {plansLoading
                      ? "LOADING"
                      : plansError
                        ? "UNKNOWN"
                        : totalPlans}
                  </strong>
                </div>
                <div>
                  <span>Running (loaded page)</span>
                  <strong>{plansLoading || plansError ? "—" : runningPlans}</strong>
                </div>
                <div>
                  <span>Awaiting approval (loaded page)</span>
                  <strong>{plansLoading || plansError ? "—" : awaitingPlans}</strong>
                </div>
              </div>

              {plansError && (
                <p className={styles.panelFootnote} role="alert">
                  Could not load plans: {plansError}
                </p>
              )}

              {!plansError && !plansLoading && (
                <p className={styles.panelFootnote}>
                  Counts for running and approval-waiting plans are based on
                  the latest 20 plans returned by the API.
                </p>
              )}

              <Link
                href="/agent-workspace"
                className={styles.outlineButton}
              >
                Inspect Agent Plans →
              </Link>
            </div>
          </section>

          <section className={styles.section}>
            <div className={styles.sectionHeading}>
              <div>
                <div className={styles.eyebrow}>
                  ORVYN MODULE NETWORK
                </div>
                <h2>Intelligence Workspace</h2>
                <p>
                  Open working modules directly from this dashboard. Modules
                  marked as not connected are not yet available.
                </p>
              </div>
            </div>

            <div className={styles.toolbar}>
              <input
                aria-label="Search ORVYN modules"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search capabilities..."
                className={styles.searchInput}
              />

              <div className={styles.filters}>
                {categories.map((category) => (
                  <button
                    key={category}
                    type="button"
                    onClick={() => setActiveCategory(category)}
                    className={
                      activeCategory === category
                        ? styles.filterActive
                        : styles.filter
                    }
                  >
                    {category}
                  </button>
                ))}
              </div>
            </div>

            <div className={styles.moduleGrid}>
              {filteredModules.map((module) => (
                <Link
                  key={module.id}
                  href={module.href}
                  aria-disabled={!module.available}
                  onClick={(event) => {
                    if (!module.available) event.preventDefault();
                  }}
                  className={`${styles.moduleCard} ${
                    module.available ? "" : styles.moduleCardUnavailable
                  }`}
                >
                  <div className={styles.moduleIcon}>{module.icon}</div>
                  <span className={styles.moduleCategory}>
                    {module.category}
                  </span>
                  <h3>{module.title}</h3>
                  <p>{module.description}</p>
                  <span className={styles.moduleAction}>
                    {module.available
                      ? "Open Module →"
                      : "Not connected yet"}
                  </span>
                </Link>
              ))}

              {filteredModules.length === 0 && (
                <div className={styles.emptyState}>
                  No matching ORVYN modules.
                </div>
              )}
            </div>
          </section>

          <section className={styles.bottomGrid}>
            <div className={styles.panel}>
              <div className={styles.panelHeader}>
                <span>SECURE AGENT WORKFLOW</span>
                <span className={styles.panelCode}>AGT-02</span>
              </div>

              <div className={styles.workflow}>
                <span>USER REQUEST</span>
                <span>→</span>
                <span>PLAN</span>
                <span>→</span>
                <span>POLICY</span>
                <span>→</span>
                <span>APPROVAL</span>
              </div>

              <p className={styles.description}>
                Creating or viewing a plan does not execute tools. Sensitive
                actions must be protected by server-side authorization and
                policy checks.
              </p>

              <Link
                href="/agent-workspace"
                className={styles.outlineButton}
              >
                Open Planning Console →
              </Link>
            </div>

            <div className={styles.panel}>
              <div className={styles.panelHeader}>
                <span>LIVE DATA STATUS</span>
                <span className={styles.panelCode}>SYS-02</span>
              </div>

              <div className={styles.systemRows}>
                <div>
                  <span>Backend health</span>
                  <strong className={connection === "online" ? styles.good : styles.warning}>
                    {connection === "online" ? "HEALTHY" : connection.toUpperCase()}
                  </strong>
                </div>
                <div>
                  <span>Plan endpoint</span>
                  <strong className={plansError ? styles.warning : plansLoading ? styles.muted : styles.good}>
                    {plansLoading ? "LOADING" : plansError ? "ERROR" : "LOADED"}
                  </strong>
                </div>
                <div>
                  <span>Plans in current response</span>
                  <strong>
                    {plansLoading || plansError ? "—" : plans.length}
                  </strong>
                </div>
                <div>
                  <span>Configured API</span>
                  <strong>{API_URL ? "CONFIGURED" : "MISSING"}</strong>
                </div>
              </div>
            </div>
          </section>

          <footer className={styles.footer}>
            <span>
              ORVYN — PERSONAL MULTILINGUAL MULTIMODAL AGENTIC AI
            </span>
            <span>UNDERSTAND • THINK • PLAN • ACT</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
