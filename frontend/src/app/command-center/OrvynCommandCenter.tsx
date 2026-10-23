
"use client";

import Link from "next/link";
import {
  useEffect,
  useRef,
  useState,
} from "react";

import styles from "./OrvynCommandCenter.module.css";

type ConnectionStatus = "checking" | "online" | "offline";

type ModuleItem = {
  id: string;
  title: string;
  description: string;
  href: string;
  icon: string;
  category: string;
};

const modules: ModuleItem[] = [
  {
    id: "chat",
    title: "AI Chat",
    description: "Multilingual conversations and AI assistance",
    href: "/",
    icon: "◉",
    category: "Intelligence",
  },
  {
    id: "agents",
    title: "Agent Workspace",
    description: "Secure planning and task orchestration",
    href: "/agent-workspace",
    icon: "⌘",
    category: "Agents",
  },
  {
    id: "memory",
    title: "Memory",
    description: "Context-aware personal intelligence",
    href: "/",
    icon: "◎",
    category: "Knowledge",
  },
  {
    id: "knowledge",
    title: "Knowledge & RAG",
    description: "Document-grounded AI assistance",
    href: "/",
    icon: "▤",
    category: "Knowledge",
  },
  {
    id: "tools",
    title: "Tools & Approvals",
    description: "Permission-controlled AI actions",
    href: "/agent-workspace",
    icon: "⚙",
    category: "Security",
  },
  {
    id: "voice",
    title: "Voice Assistant",
    description: "Speak and interact with ORVYN",
    href: "/",
    icon: "♫",
    category: "Multimodal",
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

const backendOrigin = (
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000/api/v1"
)
  .replace(/\/api\/v1\/?$/, "")
  .replace(/\/+$/, "");

/**
 * Fetch backend status without updating React state.
 * This helper can safely be used by effects and event handlers.
 */
async function fetchBackendStatus(
  signal: AbortSignal
): Promise<ConnectionStatus> {
  try {
    const response = await fetch(
      `${backendOrigin}/openapi.json`,
      {
        method: "GET",
        cache: "no-store",
        signal,
      }
    );

    return response.ok ? "online" : "offline";
  } catch {
    if (signal.aborted) {
      throw new Error("Connection check aborted.");
    }

    return "offline";
  }
}

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

function CoreVisual({
  status,
}: {
  status: ConnectionStatus;
}) {
  return (
    <div
      className={styles.coreStage}
      aria-label="Animated ORVYN AI core"
    >
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

        <div className={styles.coreName}>
          ORVYN
        </div>

        <div className={styles.coreSub}>
          THINK • PLAN • ACT
        </div>
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

  const [clock, setClock] =
    useState<Date | null>(null);

  const [query, setQuery] = useState("");

  const [activeCategory, setActiveCategory] =
    useState("All");

  const [lastChecked, setLastChecked] =
    useState<string | null>(null);

  const activeRequest = useRef<AbortController | null>(
    null
  );

  /*
   * Initial connection check.
   *
   * State changes happen only after the asynchronous
   * fetch settles, not synchronously in the effect body.
   */
  useEffect(() => {
    const controller = new AbortController();

    activeRequest.current = controller;

    fetchBackendStatus(controller.signal)
      .then((status) => {
        if (controller.signal.aborted) return;

        setConnection(status);
        setLastChecked(
          new Date().toLocaleTimeString("en-IN")
        );
      })
      .catch(() => {
        // Aborted requests are intentionally ignored.
      });

    return () => {
      controller.abort();

      if (activeRequest.current === controller) {
        activeRequest.current = null;
      }
    };
  }, []);

  /*
   * Update the clock on a timer.
   * The initial null value avoids a server/client
   * hydration mismatch.
   */
  useEffect(() => {
    const interval = window.setInterval(() => {
      setClock(new Date());
    }, 1000);

    return () => {
      window.clearInterval(interval);
    };
  }, []);

  /*
   * Manual refresh is initiated by a user event.
   * Any previous request is cancelled before starting.
   */
  const handleRecheck = async () => {
    activeRequest.current?.abort();

    const controller = new AbortController();

    activeRequest.current = controller;

    setConnection("checking");

    try {
      const status = await fetchBackendStatus(
        controller.signal
      );

      if (
        controller.signal.aborted ||
        activeRequest.current !== controller
      ) {
        return;
      }

      setConnection(status);
      setLastChecked(
        new Date().toLocaleTimeString("en-IN")
      );
    } catch {
      if (
        controller.signal.aborted ||
        activeRequest.current !== controller
      ) {
        return;
      }

      setConnection("offline");
      setLastChecked(
        new Date().toLocaleTimeString("en-IN")
      );
    }
  };

  const filteredModules = modules.filter(
    (module) => {
      const categoryMatches =
        activeCategory === "All" ||
        module.category === activeCategory;

      const searchText =
        `${module.title} ${module.description} ${module.category}`
          .toLowerCase();

      const queryMatches = searchText.includes(
        query.trim().toLowerCase()
      );

      return categoryMatches && queryMatches;
    }
  );

  return (
    <div className={styles.shell}>
      <div className={styles.backgroundGlow} />

      <aside className={styles.sidebar}>
        <Link
          href="/command-center"
          className={styles.brand}
        >
          <span className={styles.brandSymbol}>
            ◈
          </span>

          <span>
            <strong>ORVYN</strong>
            <small>AI OPERATING SYSTEM</small>
          </span>
        </Link>

        <div className={styles.navLabel}>
          COMMAND SYSTEM
        </div>

        <nav
          className={styles.navigation}
          aria-label="Main navigation"
        >
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
        </nav>

        <div className={styles.sidebarDivider} />

        <div className={styles.navLabel}>
          INTELLIGENCE MODULES
        </div>

        <div className={styles.sidebarModules}>
          <div>
            <span>◎</span>
            Long-Term Memory
          </div>

          <div>
            <span>▤</span>
            Knowledge & RAG
          </div>

          <div>
            <span>⚙</span>
            Tools & Approvals
          </div>

          <div>
            <span>♫</span>
            Multimodal AI
          </div>
        </div>

        <div className={styles.sidebarFooter}>
          <div className={styles.securitySymbol}>
            ◈
          </div>

          <strong>SECURITY FIRST</strong>

          <p>
            Sensitive actions require
            authorization and policy checks.
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

            <p>
              Your intelligence. Your tools.
              Your control.
            </p>
          </div>

          <div className={styles.topbarRight}>
            <div className={styles.clock}>
              <strong>
                {clock
                  ? formatClock(clock)
                  : "--:--:--"}
              </strong>

              <small>
                {clock
                  ? formatDate(clock)
                  : "Loading date..."}
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
                <span className={styles.panelCode}>
                  SYS-01
                </span>
              </div>

              <div className={styles.systemRows}>
                <div>
                  <span>Frontend</span>
                  <strong className={styles.good}>
                    ACTIVE
                  </strong>
                </div>

                <div>
                  <span>Backend API</span>
                  <strong
                    className={
                      connection === "online"
                        ? styles.good
                        : styles.muted
                    }
                  >
                    {connection.toUpperCase()}
                  </strong>
                </div>

                <div>
                  <span>Agent Planner</span>
                  <strong>
                    AVAILABLE VIA API
                  </strong>
                </div>

                <div>
                  <span>Secure Execution</span>
                  <strong className={styles.warning}>
                    IN DEVELOPMENT
                  </strong>
                </div>
              </div>

              <button
                type="button"
                className={styles.outlineButton}
                onClick={handleRecheck}
                disabled={connection === "checking"}
              >
                ↻ Recheck Connection
              </button>

              {lastChecked && (
                <p className={styles.panelFootnote}>
                  Last checked: {lastChecked}
                </p>
              )}
            </div>

            <div className={styles.corePanel}>
              <div className={styles.coreHeading}>
                <span>
                  ORVYN INTELLIGENCE CORE
                </span>
                <span>CORE-01</span>
              </div>

              <CoreVisual status={connection} />

              <div className={styles.coreActions}>
                <Link
                  href="/"
                  className={styles.primaryButton}
                >
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
                <span>ACTIVE CAPABILITIES</span>
                <span className={styles.panelCode}>
                  CAP-01
                </span>
              </div>

              <div className={styles.capabilityList}>
                <div>
                  <span className={styles.capIcon}>
                    ◉
                  </span>

                  <span>
                    <strong>
                      Multilingual Chat
                    </strong>
                    <small>
                      Text conversations
                    </small>
                  </span>
                </div>

                <div>
                  <span className={styles.capIcon}>
                    ◎
                  </span>

                  <span>
                    <strong>
                      Memory & RAG
                    </strong>
                    <small>
                      Context and retrieval
                    </small>
                  </span>
                </div>

                <div>
                  <span className={styles.capIcon}>
                    ⌘
                  </span>

                  <span>
                    <strong>
                      Agent Planning
                    </strong>
                    <small>
                      Persistent task plans
                    </small>
                  </span>
                </div>

                <div>
                  <span className={styles.capIcon}>
                    ⚙
                  </span>

                  <span>
                    <strong>
                      Secure Approvals
                    </strong>
                    <small>
                      Permission-controlled tools
                    </small>
                  </span>
                </div>
              </div>

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

                <h2>
                  Intelligence Workspace
                </h2>

                <p>
                  Access connected capabilities
                  through the ORVYN interface.
                </p>
              </div>
            </div>

            <div className={styles.toolbar}>
              <input
                aria-label="Search ORVYN modules"
                value={query}
                onChange={(event) =>
                  setQuery(event.target.value)
                }
                placeholder="Search capabilities..."
                className={styles.searchInput}
              />

              <div className={styles.filters}>
                {categories.map((category) => (
                  <button
                    key={category}
                    type="button"
                    onClick={() =>
                      setActiveCategory(category)
                    }
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
                  className={styles.moduleCard}
                >
                  <div className={styles.moduleIcon}>
                    {module.icon}
                  </div>

                  <span
                    className={styles.moduleCategory}
                  >
                    {module.category}
                  </span>

                  <h3>{module.title}</h3>

                  <p>{module.description}</p>

                  <span
                    className={styles.moduleAction}
                  >
                    Open Module →
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
                <span>
                  SECURE AGENT WORKFLOW
                </span>
                <span className={styles.panelCode}>
                  AGT-01
                </span>
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
                ORVYN prepares structured plans
                and requires verified permission
                before sensitive actions.
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
                <span>
                  DEVELOPMENT STATUS
                </span>
                <span className={styles.panelCode}>
                  DEV-01
                </span>
              </div>

              <div className={styles.systemRows}>
                <div>
                  <span>
                    Chat and Conversation
                  </span>
                  <strong className={styles.good}>
                    IMPLEMENTED
                  </strong>
                </div>

                <div>
                  <span>
                    Agent Plan Storage
                  </span>
                  <strong className={styles.good}>
                    IMPLEMENTED
                  </strong>
                </div>

                <div>
                  <span>
                    Approval-Step Binding
                  </span>
                  <strong className={styles.good}>
                    SERVICE ADDED
                  </strong>
                </div>

                <div>
                  <span>
                    Trusted Execution Engine
                  </span>
                  <strong className={styles.warning}>
                    PENDING
                  </strong>
                </div>
              </div>
            </div>
          </section>

          <footer className={styles.footer}>
            <span>
              ORVYN — PERSONAL MULTILINGUAL
              MULTIMODAL AGENTIC AI
            </span>

            <span>
              UNDERSTAND • THINK • PLAN • ACT
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
