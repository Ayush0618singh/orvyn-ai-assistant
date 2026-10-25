
"use client";

import Link from "next/link";
import { useCallback, useRef, useState } from "react";

import ChatInterface from "@/components/chat/ChatInterface";
import { useAuth } from "@/contexts/AuthContext";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import { useSpeechSynthesis } from "@/hooks/useSpeechSynthesis";
import CommandActionWorkspace from "@/components/command-center/CommandActionWorkspace";

import styles from "./OrvynHomeDashboard.module.css";

type ViewMode = "command" | "chat";
type VoiceLanguage = "en-IN" | "hi-IN";

type ActionResult = {
  title: string;
  message: string;
  status: "ready" | "success" | "warning";
};

type QuickCommand = {
  icon: string;
  title: string;
  command?: string;
  description: string;
  action: "prepare" | "chat";
};

const quickCommands: QuickCommand[] = [
  {
    icon: "▶",
    title: "YouTube",
    command: "YouTube par Arijit Singh ke songs search karo",
    description: "Find music and videos",
    action: "prepare",
  },
  {
    icon: "⌕",
    title: "Web search",
    command: "Google par Python tutorials search karo",
    description: "Search the web",
    action: "prepare",
  },
  {
    icon: "✦",
    title: "AI chat",
    description: "Open your conversational workspace",
    action: "chat",
  },
];

export default function OrvynHomeDashboard() {
  const { user, logout } = useAuth();

  const [view, setView] = useState<ViewMode>("command");
  const [language, setLanguage] = useState<VoiceLanguage>("hi-IN");
  const [command, setCommand] = useState("");
  const [lastTranscript, setLastTranscript] = useState("");

  const [actionResult, setActionResult] = useState<ActionResult>({
    title: "ORVYN is ready",
    message:
      "Enter a command or use voice input. Review any action before confirming it.",
    status: "ready",
  });

  const commandSectionRef = useRef<HTMLDivElement>(null);

  const handleTranscript = useCallback((transcript: string) => {
    setCommand(transcript);
    setLastTranscript(transcript);

    setActionResult({
      title: "Voice command received",
      message:
        "Review the recognised command in the Command Workspace before executing it.",
      status: "ready",
    });
  }, []);

  const handleVoiceError = useCallback((message: string) => {
    setActionResult({
      title: "Voice input unavailable",
      message,
      status: "warning",
    });
  }, []);

  const {
    isListening,
    isSupported: speechRecognitionSupported,
    startListening,
    stopListening,
  } = useSpeechRecognition({
    language,
    onTranscript: handleTranscript,
    onError: handleVoiceError,
  });

  const {
    speak,
    stopSpeaking,
    isSpeaking,
    isSupported: speechSynthesisSupported,
  } = useSpeechSynthesis();

  const speakText = useCallback(
    (text: string) => {
      if (!speechSynthesisSupported) {
        setActionResult({
          title: "Voice output unavailable",
          message:
            "This browser does not support speech synthesis. Text commands remain available.",
          status: "warning",
        });
        return;
      }

      speak(text, {
        language,
        rate: 0.95,
        pitch: 1,
        volume: 1,
      });
    },
    [language, speak, speechSynthesisSupported],
  );

  const handleQuickCommand = useCallback((item: QuickCommand) => {
    if (item.action === "chat") {
      setView("chat");
      return;
    }

    if (!item.command) return;

    setView("command");
    setCommand(item.command);

    setActionResult({
      title: `${item.title} command prepared`,
      message:
        "The command is ready in the workspace. Review the proposed action and confirm if requested.",
      status: "ready",
    });

    // Focus the command input without moving the whole page.
    window.requestAnimationFrame(() => {
      const input = document.getElementById(
        "orvyn-command-workspace-input",
      );

      input?.focus({ preventScroll: true });
    });
  }, []);

  const handleLogout = useCallback(async () => {
    try {
      await logout();
    } catch {
      setActionResult({
        title: "Sign out failed",
        message: "Could not sign out. Please try again.",
        status: "warning",
      });
    }
  }, [logout]);

  if (view === "chat") {
    return (
      <div className={styles.chatMode}>
        <header className={styles.chatTopbar}>
          <Link href="/" className={styles.brand}>
            <span className={styles.brandMark}>O</span>
            <span className={styles.brandText}>
              <strong>ORVYN</strong>
              <small>CHAT WORKSPACE</small>
            </span>
          </Link>

          <button
            className={styles.secondaryButton}
            onClick={() => setView("command")}
            type="button"
          >
            ← Command Center
          </button>
        </header>

        <div className={styles.chatBody}>
          <ChatInterface />
        </div>
      </div>
    );
  }

  const userInitial = (user?.email?.[0] ?? "U").toUpperCase();

  return (
    <main className={styles.shell}>
      <div className={styles.ambientGlow} aria-hidden="true" />

      <aside className={styles.sidebar}>
        <Link href="/" className={styles.brand} aria-label="ORVYN home">
          <span className={styles.brandMark}>O</span>

          <span className={styles.brandText}>
            <strong>ORVYN</strong>
            <small>PERSONAL AI SYSTEM</small>
          </span>
        </Link>

        <div className={styles.sidebarLabel}>WORKSPACE</div>

        <nav className={styles.navigation} aria-label="Main navigation">
          <button
            type="button"
            className={`${styles.navItem} ${styles.navItemActive}`}
            onClick={() => setView("command")}
          >
            <span>◈</span>
            Command Center
          </button>

          <button
            type="button"
            className={styles.navItem}
            onClick={() => setView("chat")}
          >
            <span>◉</span>
            Chat Workspace
          </button>

          <Link href="/memories" className={styles.navItem}>
            <span>◎</span>
            Memory
          </Link>

          <Link href="/agent-workspace" className={styles.navItem}>
            <span>⌘</span>
            Agent Workspace
          </Link>

          <Link href="/agent-executions" className={styles.navItem}>
            <span>↗</span>
            Agent Executions
          </Link>

          <Link href="/tool-approvals" className={styles.navItem}>
            <span>⚙</span>
            Tools &amp; Approvals
          </Link>
        </nav>

        <div className={styles.sidebarBottom}>
          <div className={styles.sidebarStatus}>
            <span className={styles.liveDot} />

            <div>
              <strong>Interface active</strong>
              <small>Browser workspace ready</small>
            </div>
          </div>

          <div className={styles.sidebarNote}>
            <span className={styles.shieldIcon}>⬡</span>

            <div>
              <strong>SECURITY FIRST</strong>
              <p>
                Review external actions before approving execution.
              </p>
            </div>
          </div>

          <div className={styles.profile}>
            <div className={styles.avatar}>{userInitial}</div>

            <div className={styles.profileText}>
              <strong>{user?.email ?? "ORVYN User"}</strong>
              <small>Authenticated session</small>
            </div>

            <button
              type="button"
              className={styles.logoutButton}
              onClick={() => void handleLogout()}
              aria-label="Sign out"
              title="Sign out"
            >
              ↪
            </button>
          </div>
        </div>
      </aside>

      <section className={styles.mainArea}>
        <header className={styles.topbar}>
          <div>
            <div className={styles.eyebrow}>
              PERSONAL MULTILINGUAL AI
            </div>
            <h1>Command Center</h1>
          </div>

          <div className={styles.topbarRight}>
            <span className={styles.sessionPill}>
              <span className={styles.liveDot} />
              SESSION ACTIVE
            </span>

            <span
              className={styles.userPill}
              aria-label="Signed-in user"
            >
              {userInitial}
            </span>
          </div>
        </header>

        <div className={styles.dashboard}>
          <section className={styles.heroRow}>
            <div>
              <p className={styles.eyebrow}>YOUR PERSONAL AGENT</p>
              <h2>Think clearly. Act securely.</h2>
              <p className={styles.heroDescription}>
                Talk naturally, prepare tasks, and manage your AI
                workspace from one screen.
              </p>
            </div>

            <div className={styles.systemBadge}>
              <span className={styles.liveDot} />
              <span>
                <strong>CORE UI</strong>
                <small>Ready</small>
              </span>
            </div>
          </section>

          <section
            className={styles.commandGrid}
            aria-label="Voice and command workspace"
          >
            <article
              className={`${styles.panel} ${styles.voicePanel}`}
            >
              <div className={styles.panelHeading}>
                <div>
                  <span className={styles.panelKicker}>
                    VOICE INTERFACE
                  </span>
                  <h3>Talk to ORVYN</h3>
                </div>

                <span className={styles.panelCode}>01 / VOICE</span>
              </div>

              <div className={styles.voiceStage}>
                <div
                  className={`${styles.voiceOrb} ${
                    isListening ? styles.voiceOrbListening : ""
                  } ${
                    isSpeaking ? styles.voiceOrbSpeaking : ""
                  }`}
                  role="img"
                  aria-label={
                    isListening
                      ? "ORVYN is listening"
                      : isSpeaking
                        ? "ORVYN is speaking"
                        : "ORVYN voice interface ready"
                  }
                >
                  <div className={styles.orbRing} />
                  <div className={styles.orbRingInner} />

                  <div className={styles.orbCore}>
                    <span className={styles.orbEye} />
                    <span className={styles.orbEye} />
                  </div>

                  <span className={styles.orbLabel}>ORVYN</span>
                </div>

                <div className={styles.voiceState}>
                  {isListening
                    ? "LISTENING"
                    : isSpeaking
                      ? "SPEAKING"
                      : "READY WHEN YOU ARE"}
                </div>

                <p className={styles.voiceHint}>
                  Speak in Hindi, Hinglish, or English. Recognised words
                  appear in the command workspace.
                </p>

                <div className={styles.voiceControls}>
                  <button
                    type="button"
                    className={styles.primaryButton}
                    onClick={
                      isListening ? stopListening : startListening
                    }
                    disabled={!speechRecognitionSupported}
                  >
                    {isListening
                      ? "■ Stop listening"
                      : "🎙 Start speaking"}
                  </button>

                  <button
                    type="button"
                    className={styles.secondaryButton}
                    onClick={() => {
                      if (isSpeaking) {
                        stopSpeaking();
                      } else {
                        speakText(
                          language === "hi-IN"
                            ? "Namaste! Main ORVYN hoon. Aap apni command bol sakte hain."
                            : "Hello! I am ORVYN. You can speak your command now.",
                        );
                      }
                    }}
                    disabled={!speechSynthesisSupported}
                  >
                    {isSpeaking ? "Stop voice" : "Test voice"}
                  </button>
                </div>

                <label
                  className={styles.languageLabel}
                  htmlFor="voice-language"
                >
                  Voice language
                </label>

                <select
                  id="voice-language"
                  className={styles.languageSelect}
                  value={language}
                  onChange={(event) =>
                    setLanguage(event.target.value as VoiceLanguage)
                  }
                >
                  <option value="hi-IN">Hindi / Hinglish</option>
                  <option value="en-IN">English (India)</option>
                </select>

                {!speechRecognitionSupported && (
                  <p className={styles.inlineWarning} role="status">
                    Speech recognition is not supported in this browser.
                    You can still type commands.
                  </p>
                )}
              </div>
            </article>

            <article
              className={`${styles.panel} ${styles.commandPanel}`}
              ref={commandSectionRef}
            >
              <div className={styles.panelHeading}>
                <div>
                  <span className={styles.panelKicker}>
                    COMMAND &amp; ACTION
                  </span>
                  <h3>What should I do?</h3>
                </div>

                <span className={styles.panelCode}>02 / ACTION</span>
              </div>

              <div className={styles.commandWorkspace}>
                <CommandActionWorkspace
                  command={command}
                  onCommandChange={setCommand}
                  onOpenChat={() => setView("chat")}
                  onSpeak={speakText}
                />
              </div>

              {lastTranscript && (
                <div className={styles.transcript}>
                  <span>LAST VOICE INPUT</span>
                  <p>{lastTranscript}</p>
                </div>
              )}

              <div
                className={`${styles.actionResult} ${
                  actionResult.status === "warning"
                    ? styles.resultWarning
                    : actionResult.status === "success"
                      ? styles.resultSuccess
                      : ""
                }`}
                role="status"
                aria-live="polite"
              >
                <span className={styles.resultDot} />

                <div>
                  <strong>{actionResult.title}</strong>
                  <p>{actionResult.message}</p>
                </div>
              </div>
            </article>
          </section>

          <section className={styles.bottomGrid}>
            <article
              className={`${styles.panel} ${styles.quickPanel}`}
            >
              <div className={styles.sectionTitle}>
                <div>
                  <span className={styles.panelKicker}>FAST ACCESS</span>
                  <h3>Quick commands</h3>
                </div>

                <span className={styles.panelCode}>
                  03 / SHORTCUTS
                </span>
              </div>

              <div className={styles.quickGrid}>
                {quickCommands.map((item) => (
                  <button
                    type="button"
                    key={item.title}
                    className={styles.quickCard}
                    onClick={() => handleQuickCommand(item)}
                    aria-label={item.title}
                  >
                    <span className={styles.quickIcon}>
                      {item.icon}
                    </span>

                    <span className={styles.quickCopy}>
                      <strong>{item.title}</strong>
                      <small>{item.description}</small>
                    </span>

                    <span className={styles.quickArrow}>↗</span>
                  </button>
                ))}
              </div>
            </article>

            <article
              className={`${styles.panel} ${styles.modulesPanel}`}
            >
              <div className={styles.sectionTitle}>
                <div>
                  <span className={styles.panelKicker}>
                    SYSTEM MODULES
                  </span>
                  <h3>Your workspace</h3>
                </div>

                <span className={styles.panelCode}>04 / MODULES</span>
              </div>

              <div className={styles.moduleGrid}>
                <button
                  type="button"
                  className={styles.moduleCard}
                  onClick={() => setView("chat")}
                >
                  <span className={styles.moduleIcon}>◉</span>
                  <span>
                    <strong>AI Chat</strong>
                    <small>Chat workspace</small>
                  </span>
                </button>

                <Link href="/memories" className={styles.moduleCard}>
                  <span className={styles.moduleIcon}>◎</span>
                  <span>
                    <strong>Memory</strong>
                    <small>Saved information</small>
                  </span>
                </Link>

                <Link
                  href="/agent-workspace"
                  className={styles.moduleCard}
                >
                  <span className={styles.moduleIcon}>⌘</span>
                  <span>
                    <strong>Agent plans</strong>
                    <small>Task workflows</small>
                  </span>
                </Link>

                <Link
                  href="/agent-executions"
                  className={styles.moduleCard}
                >
                  <span className={styles.moduleIcon}>↗</span>
                  <span>
                    <strong>Executions</strong>
                    <small>Execution history</small>
                  </span>
                </Link>

                <Link
                  href="/tool-approvals"
                  className={styles.moduleCard}
                >
                  <span className={styles.moduleIcon}>⚙</span>
                  <span>
                    <strong>Tools &amp; approvals</strong>
                    <small>Controlled actions</small>
                  </span>
                </Link>

                <Link
                  href="/command-center"
                  className={styles.moduleCard}
                >
                  <span className={styles.moduleIcon}>▦</span>
                  <span>
                    <strong>System dashboard</strong>
                    <small>Detailed overview</small>
                  </span>
                </Link>
              </div>
            </article>
          </section>

          <footer className={styles.footer}>
            <span>ORVYN · PERSONAL MULTILINGUAL AGENTIC AI</span>
            <span>UNDERSTAND · PLAN · REVIEW · ACT</span>
          </footer>
        </div>
      </section>
    </main>
  );
}
