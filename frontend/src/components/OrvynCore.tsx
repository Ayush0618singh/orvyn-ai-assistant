
"use client";

import styles from "./OrvynCore.module.css";

type OrvynCoreProps = {
  listening?: boolean;
  speaking?: boolean;
  status?: string;
};

export default function OrvynCore({
  listening = false,
  speaking = false,
  status = "SYSTEM READY",
}: OrvynCoreProps) {
  const active = listening || speaking;

  return (
    <section className={styles.corePanel} aria-label="ORVYN AI core">
      <div className={styles.eyebrow}>
        <span className={styles.liveDot} />
        PERSONAL AI OPERATIONS MANAGER
      </div>

      <div
        className={`${styles.core} ${active ? styles.active : ""}`}
        role="img"
        aria-label={`ORVYN AI core: ${status}`}
      >
        <div className={styles.orbitOuter} />
        <div className={styles.orbitMiddle} />
        <div className={styles.orbitInner} />

        <div className={styles.coreFace}>
          <div className={styles.eyePair}>
            <span />
            <span />
          </div>
          <strong>ORVYN</strong>
          <small>PERSONAL AI</small>
        </div>

        <span className={`${styles.node} ${styles.nodeTop}`} />
        <span className={`${styles.node} ${styles.nodeRight}`} />
        <span className={`${styles.node} ${styles.nodeBottom}`} />
        <span className={`${styles.node} ${styles.nodeLeft}`} />
      </div>

      <h2 className={styles.status}>{status}</h2>
      <p className={styles.motto}>PLAN <i /> REASON <i /> ACT</p>
      <p className={styles.description}>
        Your personal multilingual AI assistant
      </p>

      <div className={styles.capabilities}>
        <span>INTELLIGENCE</span>
        <span>MEMORY</span>
        <span>ACTION</span>
      </div>
    </section>
  );
}
