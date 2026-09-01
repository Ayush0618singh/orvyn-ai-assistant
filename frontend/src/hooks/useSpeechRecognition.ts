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

  onTranscript: (
    transcript: string
  ) => void;

  onError?: (
    message: string
  ) => void;
}


export function useSpeechRecognition({
  language = "en-IN",
  onTranscript,
  onError,
}: UseSpeechRecognitionOptions) {
  const recognitionRef =
    useRef<SpeechRecognitionLike | null>(
      null
    );


  const [
    isListening,
    setIsListening,
  ] = useState(false);


  const isSupported =
    typeof window !== "undefined" &&
    Boolean(
      window.SpeechRecognition ||
      window.webkitSpeechRecognition
    );


  useEffect(() => {
    if (!isSupported) {
      return;
    }


    const Recognition =
      window.SpeechRecognition ??
      window.webkitSpeechRecognition;


    if (!Recognition) {
      return;
    }


    const recognition =
      new Recognition();


    recognition.lang =
      language;

    recognition.continuous =
      false;

    recognition.interimResults =
      false;

    recognition.maxAlternatives =
      1;


    recognition.onstart =
      () => {
        setIsListening(
          true
        );
      };


    recognition.onend =
      () => {
        setIsListening(
          false
        );
      };


    recognition.onresult = (
      event:
        SpeechRecognitionEventLike
    ) => {
      let transcript = "";


      for (
        let index =
          event.resultIndex;
        index <
        event.results.length;
        index += 1
      ) {
        const result =
          event.results[
            index
          ];


        if (
          result.isFinal &&
          result[0]?.transcript
        ) {
          transcript +=
            result[0].transcript;
        }
      }


      const cleaned =
        transcript.trim();


      if (cleaned) {
        onTranscript(
          cleaned
        );
      }
    };


    recognition.onerror = (
      event:
        SpeechRecognitionErrorEventLike
    ) => {
      setIsListening(
        false
      );


      if (
        event.error ===
        "aborted"
      ) {
        return;
      }


      let message =
        "Unable to use voice input.";


      if (
        event.error ===
          "not-allowed" ||
        event.error ===
          "service-not-allowed"
      ) {
        message =
          "Microphone permission was denied.";
      } else if (
        event.error ===
        "no-speech"
      ) {
        message =
          "No speech was detected.";
      } else if (
        event.error ===
        "audio-capture"
      ) {
        message =
          "No microphone was detected.";
      } else if (
        event.error ===
        "network"
      ) {
        message =
          "Voice recognition network error.";
      }


      onError?.(
        message
      );
    };


    recognitionRef.current =
      recognition;


    return () => {
      recognition.abort();

      recognitionRef.current =
        null;
    };
  }, [
    language,
    onTranscript,
    onError,
    isSupported,
  ]);


  const startListening =
    useCallback(() => {
      if (
        !recognitionRef.current ||
        isListening
      ) {
        return;
      }


      try {
        recognitionRef.current.start();
      } catch {
        onError?.(
          "Unable to start voice input."
        );
      }
    }, [
      isListening,
      onError,
    ]);


  const stopListening =
    useCallback(() => {
      recognitionRef.current?.stop();
    }, []);


  return {
    isListening,
    isSupported,
    startListening,
    stopListening,
  };
}