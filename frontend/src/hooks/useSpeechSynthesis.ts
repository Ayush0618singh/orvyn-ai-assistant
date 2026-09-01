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


export function useSpeechSynthesis() {
  const [
    isSpeaking,
    setIsSpeaking,
  ] = useState(false);

  const [
    voices,
    setVoices,
  ] = useState<
    SpeechSynthesisVoice[]
  >([]);

  const activeUtteranceRef =
    useRef<
      SpeechSynthesisUtterance | null
    >(null);


  const isSupported =
    typeof window !== "undefined" &&
    "speechSynthesis" in window &&
    "SpeechSynthesisUtterance" in window;


  useEffect(() => {
    if (!isSupported) {
      return;
    }


    function loadVoices() {
      const availableVoices =
        window.speechSynthesis.getVoices();

      setVoices(
        availableVoices
      );
    }


    loadVoices();


    window.speechSynthesis.addEventListener(
      "voiceschanged",
      loadVoices
    );


    return () => {
      window.speechSynthesis.removeEventListener(
        "voiceschanged",
        loadVoices
      );

      window.speechSynthesis.cancel();

      activeUtteranceRef.current =
        null;
    };
  }, [
    isSupported,
  ]);


  const stopSpeaking =
    useCallback(() => {
      if (!isSupported) {
        return;
      }

      window.speechSynthesis.cancel();

      activeUtteranceRef.current =
        null;

      setIsSpeaking(
        false
      );
    }, [
      isSupported,
    ]);


  const speak =
    useCallback(
      (
        text: string,
        options?: SpeakOptions
      ) => {
        if (
          !isSupported ||
          !text.trim()
        ) {
          return;
        }


        window.speechSynthesis.cancel();


        const language =
          options?.language ??
          "en-IN";


        const utterance =
          new SpeechSynthesisUtterance(
            text
          );


        utterance.lang =
          language;


        const selectedByName =
          options?.voiceName
            ? voices.find(
                (voice) =>
                  voice.name ===
                  options.voiceName
              )
            : undefined;


        const exactLanguageVoice =
          voices.find(
            (voice) =>
              voice.lang.toLowerCase() ===
              language.toLowerCase()
          );


        const languagePrefix =
          language
            .split("-")[0]
            .toLowerCase();


        const fallbackLanguageVoice =
          voices.find(
            (voice) =>
              voice.lang
                .toLowerCase()
                .startsWith(
                  languagePrefix
                )
          );


        const selectedVoice =
          selectedByName ??
          exactLanguageVoice ??
          fallbackLanguageVoice;


        if (selectedVoice) {
          utterance.voice =
            selectedVoice;
        }


        utterance.rate =
          options?.rate ??
          0.95;

        utterance.pitch =
          options?.pitch ??
          1;

        utterance.volume =
          options?.volume ??
          1;


        utterance.onstart =
          () => {
            setIsSpeaking(
              true
            );
          };


        utterance.onend =
          () => {
            activeUtteranceRef.current =
              null;

            setIsSpeaking(
              false
            );
          };


        utterance.onerror =
          () => {
            activeUtteranceRef.current =
              null;

            setIsSpeaking(
              false
            );
          };


        activeUtteranceRef.current =
          utterance;


        window.speechSynthesis.speak(
          utterance
        );
      },
      [
        isSupported,
        voices,
      ]
    );


  return {
    speak,
    stopSpeaking,
    isSpeaking,
    isSupported,
    voices,
  };
}