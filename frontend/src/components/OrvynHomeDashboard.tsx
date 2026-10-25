
"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import { useSpeechSynthesis } from "@/hooks/useSpeechSynthesis";

import CommandActionWorkspace from "@/components/command-center/CommandActionWorkspace";
import SystemStatusPanel from "@/components/SystemStatusPanel";
import OrvynCore from "@/components/OrvynCore";
import VoiceVisualizer from "@/components/VoiceVisualizer";
import AgentActivityPanel from "@/components/AgentActivityPanel";
import KnowledgeCenterPanel from "@/components/knowledge/KnowledgeCenterPanel";

import styles from "./OrvynHomeDashboard.module.css";

const modules = [
  {
    icon: "◉",
    title: "AI Chat",
    detail: "Chat workspace",
    href: "/chat",
  },
  {
    icon: "◎",
    title: "Memory",
    detail: "Saved information",
    href: "/memories",
  },
  {
    icon: "⌘",
    title: "Agent plans",
    detail: "Task workflows",
    href: "/agent-workspace",
  },
  {
    icon: "↗",
    title: "Executions",
    detail: "Execution history",
    href: "/agent-executions",
  },
  {
    icon: "◇",
    title: "Tools & approvals",
    detail: "Controlled actions",
    href: "/tools-approvals",
  },
  {
    icon: "▦",
    title: "System dashboard",
    detail: "System overview",
    href: "/command-center",
  },
];

const capabilityItems = [
  {
    title: "YouTube search",
    detail:
      "Search videos through the connected command workspace.",
    state: "Integrated UI",
  },
  {
    title: "Web search",
    detail:
      "Prepare a browser search from a command.",
    state: "Integrated UI",
  },
  {
    title: "External navigation",
    detail:
      "Review external destinations before opening them.",
    state: "Confirmation",
  },
  {
    title: "Persistent memory",
    detail:
      "Open the existing Memory module.",
    state: "Separate module",
  },
];

export default function OrvynHomeDashboard() {
  const router = useRouter();

  const [command, setCommand] = useState("");
  const [voiceError, setVoiceError] = useState("");

  const handleTranscript = useCallback(
    (transcript: string) => {
      setCommand(transcript);
      setVoiceError("");
    },
    [],
  );

  const handleVoiceError = useCallback(
    (message: string) => {
      setVoiceError(message);
    },
    [],
  );

  const recognition = useSpeechRecognition({
    language: "hi-IN",
    onTranscript: handleTranscript,
    onError: handleVoiceError,
  });

  const speech = useSpeechSynthesis();

  const listening = Boolean(recognition.isListening);
  const speaking = Boolean(speech.isSpeaking);
  const supported = Boolean(recognition.isSupported);

  const startListening = useCallback(() => {
    speech.stopSpeaking();
    setVoiceError("");
    recognition.startListening();
  }, [recognition, speech]);

  const stopListening = useCallback(() => {
    recognition.stopListening();
  }, [recognition]);

  const testVoice = useCallback(() => {
    speech.speak(
      "Hello. I am ORVYN, your personal multilingual AI assistant.",
      { language: "en-IN" },
    );
  }, [speech]);

  const speakText = useCallback(
    (text: string) => {
      if (text.trim()) {
        speech.speak(text, { language: "en-IN" });
      }
    },
    [speech],
  );

  const openChat = useCallback(() => {
    router.push("/chat");
  }, [router]);

  const coreStatus = listening
    ? "LISTENING TO YOUR COMMAND"
    : speaking
      ? "ORVYN IS SPEAKING"
      : "SYSTEM READY";

  return (
    <main className={styles.dashboard}>
      <header className={styles.topbar}>
        <Link
          href="/command-center"
          className={styles.brand}
          aria-label="ORVYN Command Center home"
        >
          <span className={styles.brandIcon}>O</span>

          <span>
            <strong>ORVYN</strong>
            <small>PERSONAL AI SYSTEM</small>
          </span>
        </Link>

        <nav
          className={styles.topNav}
          aria-label="Main navigation"
        >
          <Link
            className={styles.navActive}
            href="/command-center"
          >
            OVERVIEW
          </Link>

          <Link href="/agent-workspace">
            AGENTS
          </Link>

          <Link href="/memories">
            KNOWLEDGE
          </Link>

          <Link href="/tools-approvals">
            TOOLS
          </Link>

          <Link href="/agent-executions">
            AUTOMATIONS
          </Link>
        </nav>

        <div className={styles.online}>
          <span />

          <div>
            <strong>ORVYN INTERFACE</strong>
            <small>LOCAL SESSION ACTIVE</small>
          </div>
        </div>
      </header>

      <section className={styles.heading}>
        <div>
          <span className={styles.eyebrow}>
            PERSONAL MULTILINGUAL AI
          </span>

          <h1>Command Center</h1>

          <p>
            Understand. Plan. Review. Act — from one workspace.
          </p>
        </div>

        <div className={styles.secureLabel}>
          <span />
          REVIEW BEFORE ACTION
        </div>
      </section>

      <section className={styles.commandGrid}>
        <div className={styles.leftColumn}>
          {/* Live backend and database status */}
          <SystemStatusPanel />

          {/* Live agent execution activity */}
          <AgentActivityPanel />

          <section className={styles.panel}>
            <div className={styles.panelHeading}>
              <div>
                <span className={styles.eyebrow}>
                  MEMORY
                </span>

                <h2>Personal knowledge</h2>
              </div>

              <Link
                href="/memories"
                className={styles.textLink}
              >
                OPEN ↗
              </Link>
            </div>

            <p className={styles.panelDescription}>
              Access the existing memory module and saved
              information.
            </p>

            <Link
              href="/memories"
              className={styles.wideLink}
            >
              <span>◎</span>

              <span>
                <strong>Open Memory</strong>
                <small>View saved information</small>
              </span>

              <b>→</b>
            </Link>
          </section>

          <section className={styles.panel}>
            <div className={styles.panelHeading}>
              <div>
                <span className={styles.eyebrow}>
                  CONNECTED WORKSPACE
                </span>

                <h2>Tools & agents</h2>
              </div>
            </div>

            <div className={styles.chipList}>
              <span>Command engine</span>
              <span>Voice interface</span>
              <span>Agent workspace</span>
              <span>Execution history</span>
            </div>

            <Link
              href="/tools-approvals"
              className={styles.panelFooterLink}
            >
              Manage tools & approvals
              <span>↗</span>
            </Link>
          </section>
        </div>

        <OrvynCore
          listening={listening}
          speaking={speaking}
          status={coreStatus}
        />

        <div className={styles.rightColumn}>
          <section className={styles.panel}>
            <div className={styles.panelHeading}>
              <div>
                <span className={styles.eyebrow}>
                  AGENT WORKSPACE
                </span>

                <h2>Agent operations</h2>
              </div>

              <Link
                href="/agent-workspace"
                className={styles.textLink}
              >
                OPEN ↗
              </Link>
            </div>

            <div className={styles.agentTiles}>
              <Link href="/agent-workspace">
                <span>⌘</span>
                <strong>Planner</strong>
              </Link>

              <Link href="/agent-workspace">
                <span>⌕</span>
                <strong>Research</strong>
              </Link>

              <Link href="/agent-workspace">
                <span>⌁</span>
                <strong>Code</strong>
              </Link>

              <Link href="/agent-executions">
                <span>↗</span>
                <strong>Execute</strong>
              </Link>
            </div>

            <p className={styles.panelDescription}>
              Open the existing workspace to inspect agent
              plans and executions.
            </p>
          </section>

          <VoiceVisualizer
            listening={listening}
            speaking={speaking}
            supported={supported}
            onStart={startListening}
            onStop={stopListening}
            onTestVoice={testVoice}
          />

          {voiceError && (
            <p
              role="alert"
              className={styles.voiceError}
            >
              Voice: {voiceError}
            </p>
          )}

          <section className={styles.panel}>
            <div className={styles.panelHeading}>
                <div>
                <span className={styles.eyebrow}>
                    KNOWLEDGE ENGINE
                </span>

                <h2>Knowledge & Files</h2>
                </div>

                <Link
                href="/memories"
                className={styles.textLink}
                >
                VIEW ALL ↗
                </Link>
            </div>

            <KnowledgeCenterPanel />
            </section>
            </div>
            </section>

      <section className={styles.actionSection}>
        <div className={styles.sectionTitle}>
          <div>
            <span className={styles.eyebrow}>
              COMMAND & ACTION
            </span>

            <h2>What should ORVYN do?</h2>
          </div>

          <span className={styles.badge}>
            REVIEW BEFORE EXECUTION
          </span>
        </div>

        <div className={styles.actionWorkspace}>
          <CommandActionWorkspace
            command={command}
            onCommandChange={setCommand}
            onOpenChat={openChat}
            onSpeak={speakText}
          />
        </div>
      </section>

      <section className={styles.bottomGrid}>
        <section className={styles.panel}>
          <div className={styles.panelHeading}>
            <div>
              <span className={styles.eyebrow}>
                SYSTEM MODULES
              </span>

              <h2>Your workspace</h2>
            </div>
          </div>

          <div className={styles.moduleGrid}>
            {modules.map((module) => (
              <Link
                href={module.href}
                key={module.title}
                className={styles.module}
              >
                <span className={styles.moduleIcon}>
                  {module.icon}
                </span>

                <span>
                  <strong>{module.title}</strong>
                  <small>{module.detail}</small>
                </span>

                <b>↗</b>
              </Link>
            ))}
          </div>
        </section>

        <section className={styles.panel}>
          <div className={styles.panelHeading}>
            <div>
              <span className={styles.eyebrow}>
                CAPABILITY OVERVIEW
              </span>

              <h2>Connected experiences</h2>
            </div>
          </div>

          <div className={styles.capabilityList}>
            {capabilityItems.map((item) => (
              <article
                className={styles.capability}
                key={item.title}
              >
                <div>
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                </div>

                <span>{item.state}</span>
              </article>
            ))}
          </div>
        </section>
      </section>

      <footer className={styles.footer}>
        <span>
          ORVYN · PERSONAL MULTILINGUAL AGENTIC AI
        </span>

        <span>
          UNDERSTAND · PLAN · REVIEW · ACT
        </span>
      </footer>
    </main>
  );
}
