"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import type {
  SpeechRecognitionErrorEventLike,
  SpeechRecognitionEventLike,
  SpeechRecognitionLike,
} from "@/types/speech";

interface UseSpeechRecognitionOptions {
  language?: string;
  onTranscript: (transcript: string) => void;
  onError?: (message: string) => void;
}

interface UseSpeechRecognitionReturn {
  isListening: boolean;
  isSupported: boolean;
  startListening: () => void;
  stopListening: () => void;
}

const ERROR_MESSAGES: Record<string, string> = {
  "not-allowed":
    "Microphone permission denied. Allow microphone access in browser settings.",
  "service-not-allowed":
    "Speech recognition service is not allowed by this browser.",
  "no-speech":
    "No speech detected. Please speak and try again.",
  "audio-capture":
    "No microphone detected. Check your microphone connection.",
  network:
    "Voice recognition network error. Check your internet connection.",
  "language-not-supported":
    "This language is not supported by your browser.",
};

export function useSpeechRecognition({
  language = "hi-IN",
  onTranscript,
  onError,
}: UseSpeechRecognitionOptions): UseSpeechRecognitionReturn {
  const recognitionRef =
    useRef<SpeechRecognitionLike | null>(null);

  const transcriptCallbackRef = useRef(onTranscript);
  const errorCallbackRef = useRef(onError);

  const mountedRef = useRef(false);
  const listeningRef = useRef(false);
  const startingRef = useRef(false);
  const generationRef = useRef(0);

  const [isListening, setIsListening] = useState(false);
  const [isSupported, setIsSupported] = useState(false);

  useEffect(() => {
    transcriptCallbackRef.current = onTranscript;
    errorCallbackRef.current = onError;
  }, [onTranscript, onError]);

  useEffect(() => {
    mountedRef.current = true;

    const generation = ++generationRef.current;

    const Recognition =
      typeof window !== "undefined"
        ? window.SpeechRecognition ??
          window.webkitSpeechRecognition
        : undefined;

    if (!Recognition) {
      setIsSupported(false);

      return () => {
        mountedRef.current = false;
      };
    }

    let recognition: SpeechRecognitionLike;

    try {
      recognition = new Recognition();
    } catch {
      setIsSupported(false);

      errorCallbackRef.current?.(
        "Could not initialise speech recognition.",
      );

      return () => {
        mountedRef.current = false;
      };
    }

    const isCurrentInstance = () =>
      mountedRef.current &&
      generationRef.current === generation &&
      recognitionRef.current === recognition;

    recognition.lang = language;
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      if (!isCurrentInstance()) return;

      startingRef.current = false;
      listeningRef.current = true;
      setIsListening(true);
    };

    recognition.onend = () => {
      if (!isCurrentInstance()) return;

      startingRef.current = false;
      listeningRef.current = false;
      setIsListening(false);
    };

    recognition.onresult = (
      event: SpeechRecognitionEventLike,
    ) => {
      if (!isCurrentInstance()) return;

      const transcripts: string[] = [];

      for (
        let index = event.resultIndex;
        index < event.results.length;
        index += 1
      ) {
        const result = event.results[index];
        const transcript = result?.[0]?.transcript?.trim();

        if (result?.isFinal && transcript) {
          transcripts.push(transcript);
        }
      }

      const finalTranscript = transcripts.join(" ").trim();

      if (finalTranscript) {
        transcriptCallbackRef.current(finalTranscript);
      }
    };

    recognition.onerror = (
      event: SpeechRecognitionErrorEventLike,
    ) => {
      if (!isCurrentInstance()) return;

      startingRef.current = false;
      listeningRef.current = false;
      setIsListening(false);

      if (event.error === "aborted") return;

      errorCallbackRef.current?.(
        ERROR_MESSAGES[event.error] ??
          `Voice recognition failed: ${event.error}. Please try again.`,
      );
    };

    recognitionRef.current = recognition;
    setIsSupported(true);

    return () => {
      mountedRef.current = false;
      listeningRef.current = false;
      startingRef.current = false;

      generationRef.current += 1;

      recognition.onstart = null;
      recognition.onend = null;
      recognition.onresult = null;
      recognition.onerror = null;

      try {
        recognition.abort();
      } catch {
        // Recognition may already have stopped.
      }

      if (recognitionRef.current === recognition) {
        recognitionRef.current = null;
      }
    };
  }, [language]);

  const startListening = useCallback(() => {
    const recognition = recognitionRef.current;

    if (!recognition) {
      errorCallbackRef.current?.(
        "Speech recognition is unavailable. Try Chrome or Edge, or use text input.",
      );
      return;
    }

    if (listeningRef.current || startingRef.current) {
      return;
    }

    startingRef.current = true;

    try {
      recognition.start();
    } catch {
      startingRef.current = false;

      errorCallbackRef.current?.(
        "Could not start the microphone. Check browser permissions and try again.",
      );
    }
  }, []);

  const stopListening = useCallback(() => {
    const recognition = recognitionRef.current;

    if (!recognition) return;

    startingRef.current = false;

    try {
      recognition.stop();
    } catch {
      listeningRef.current = false;

      if (mountedRef.current) {
        setIsListening(false);
      }
    }
  }, []);

  return {
    isListening,
    isSupported,
    startListening,
    stopListening,
  };
}