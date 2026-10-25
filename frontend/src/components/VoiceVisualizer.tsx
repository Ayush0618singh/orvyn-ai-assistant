
"use client";

import styles from "./VoiceVisualizer.module.css";

type VoiceVisualizerProps = {
  listening: boolean;
  speaking: boolean;
  supported: boolean;
  onStart: () => void;
  onStop: () => void;
  onTestVoice: () => void;
};

const bars = [
  13, 21, 34, 17, 43, 27, 53, 31, 45, 19, 37, 57,
  25, 44, 18, 34, 50, 24, 41, 16, 30, 46, 22, 36,
];

export default function VoiceVisualizer({
  listening,
  speaking,
  supported,
  onStart,
  onStop,
  onTestVoice,
}: VoiceVisualizerProps) {
  const active = listening || speaking;

  return (
    <section className={styles.panel} aria-label="ORVYN voice interface">
      <div className={styles.header}>
        <div>
          <span className={styles.kicker}>VOICE INTERFACE</span>
          <h3>Talk to ORVYN</h3>
        </div>
        <span className={`${styles.status} ${active ? styles.active : ""}`}>
          <i />
          {listening ? "LISTENING" : speaking ? "SPEAKING" : "STANDBY"}
        </span>
      </div>

      <div className={`${styles.visual} ${active ? styles.visualActive : ""}`}>
        <div className={styles.halo} />
        <div className={styles.wave} aria-hidden="true">
          {bars.map((height, index) => (
            <span
              key={index}
              style={{
                height: `${height}px`,
                animationDelay: `${index * -0.065}s`,
              }}
            />
          ))}
        </div>
        <div className={styles.visualLabel}>
          {listening
            ? "ORVYN IS LISTENING"
            : speaking
              ? "ORVYN IS SPEAKING"
              : "READY WHEN YOU ARE"}
        </div>
      </div>

      <p className={styles.hint}>
        Speak naturally in Hindi, Hinglish or English.
      </p>

      {!supported && (
        <p className={styles.warning}>
          Speech recognition is not supported by this browser.
        </p>
      )}

      <div className={styles.actions}>
        {listening ? (
          <button className={styles.primary} onClick={onStop}>
            ■ Stop listening
          </button>
        ) : (
          <button
            className={styles.primary}
            onClick={onStart}
            disabled={!supported}
          >
            {speaking ? "Start listening" : "● Start speaking"}
          </button>
        )}

        <button className={styles.secondary} onClick={onTestVoice}>
          Test voice
        </button>
      </div>
    </section>
  );
}
