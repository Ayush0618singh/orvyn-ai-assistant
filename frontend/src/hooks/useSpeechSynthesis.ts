"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

interface SpeakOptions {
  language?: string;
  voiceName?: string;
  rate?: number;
  pitch?: number;
  volume?: number;
}

interface UseSpeechSynthesisReturn {
  speak: (text: string, options?: SpeakOptions) => void;
  stopSpeaking: () => void;
  isSpeaking: boolean;
  isSupported: boolean;
  voices: SpeechSynthesisVoice[];
}

const DEFAULT_OPTIONS = {
  rate: 0.95,
  pitch: 1,
  volume: 1,
};

function clamp(
  value: number,
  minimum: number,
  maximum: number,
): number {
  return Math.min(maximum, Math.max(minimum, value));
}

function normaliseLanguage(language: string): string {
  return language.trim().replace("_", "-").toLowerCase();
}

function selectVoice(
  voices: SpeechSynthesisVoice[],
  language: string,
  voiceName?: string,
): SpeechSynthesisVoice | undefined {
  if (voiceName) {
    const namedVoice = voices.find(
      (voice) => voice.name === voiceName,
    );

    if (namedVoice) return namedVoice;
  }

  const targetLanguage = normaliseLanguage(language);
  const languagePrefix = targetLanguage.split("-")[0];

  return (
    voices.find(
      (voice) =>
        normaliseLanguage(voice.lang) === targetLanguage,
    ) ??
    voices.find(
      (voice) =>
        normaliseLanguage(voice.lang).startsWith(
          `${languagePrefix}-`,
        ) ||
        normaliseLanguage(voice.lang) === languagePrefix,
    )
  );
}

export function useSpeechSynthesis(): UseSpeechSynthesisReturn {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [isSupported, setIsSupported] = useState(false);

  const activeUtteranceRef =
    useRef<SpeechSynthesisUtterance | null>(null);

  const mountedRef = useRef(false);
  const requestIdRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;

    const supported =
      typeof window !== "undefined" &&
      "speechSynthesis" in window &&
      "SpeechSynthesisUtterance" in window;

    setIsSupported(supported);

    if (!supported) {
      return () => {
        mountedRef.current = false;
      };
    }

    const loadVoices = () => {
      if (!mountedRef.current) return;

      setVoices(window.speechSynthesis.getVoices());
    };

    loadVoices();

    window.speechSynthesis.addEventListener(
      "voiceschanged",
      loadVoices,
    );

    return () => {
      mountedRef.current = false;
      requestIdRef.current += 1;

      window.speechSynthesis.removeEventListener(
        "voiceschanged",
        loadVoices,
      );

      window.speechSynthesis.cancel();
      activeUtteranceRef.current = null;
    };
  }, []);

  const stopSpeaking = useCallback(() => {
    requestIdRef.current += 1;
    activeUtteranceRef.current = null;

    if (
      typeof window !== "undefined" &&
      "speechSynthesis" in window
    ) {
      window.speechSynthesis.cancel();
    }

    if (mountedRef.current) {
      setIsSpeaking(false);
    }
  }, []);

  const speak = useCallback(
    (text: string, options?: SpeakOptions) => {
      const cleanedText = text.trim();

      if (!cleanedText || !isSupported) return;

      const requestId = ++requestIdRef.current;

      window.speechSynthesis.cancel();
      activeUtteranceRef.current = null;
      setIsSpeaking(false);

      const language = options?.language ?? "en-IN";
      const utterance = new SpeechSynthesisUtterance(cleanedText);

      utterance.lang = language;

      const selectedVoice = selectVoice(
        voices,
        language,
        options?.voiceName,
      );

      if (selectedVoice) {
        utterance.voice = selectedVoice;
      }

      utterance.rate = clamp(
        options?.rate ?? DEFAULT_OPTIONS.rate,
        0.5,
        2,
      );

      utterance.pitch = clamp(
        options?.pitch ?? DEFAULT_OPTIONS.pitch,
        0,
        2,
      );

      utterance.volume = clamp(
        options?.volume ?? DEFAULT_OPTIONS.volume,
        0,
        1,
      );

      utterance.onstart = () => {
        if (
          mountedRef.current &&
          requestIdRef.current === requestId
        ) {
          setIsSpeaking(true);
        }
      };

      utterance.onend = () => {
        if (requestIdRef.current !== requestId) return;

        activeUtteranceRef.current = null;

        if (mountedRef.current) {
          setIsSpeaking(false);
        }
      };

      utterance.onerror = (event) => {
        if (requestIdRef.current !== requestId) return;

        activeUtteranceRef.current = null;

        if (mountedRef.current) {
          setIsSpeaking(false);
        }

        if (
          event.error !== "canceled" &&
          event.error !== "interrupted"
        ) {
          console.warn(
            "[ORVYN Voice] Speech synthesis failed:",
            event.error,
          );
        }
      };

      activeUtteranceRef.current = utterance;

      try {
        window.speechSynthesis.speak(utterance);
      } catch (error) {
        activeUtteranceRef.current = null;

        if (mountedRef.current) {
          setIsSpeaking(false);
        }

        console.error(
          "[ORVYN Voice] Unable to start speech:",
          error,
        );
      }
    },
    [isSupported, voices],
  );

  return {
    speak,
    stopSpeaking,
    isSpeaking,
    isSupported,
    voices,
  };
}