import { useCallback, useRef, useState } from "react";

const API = import.meta.env.PUBLIC_API_URL ?? "http://localhost:8000";

export type LoadingStage =
  | null
  | "transcribing"
  | "thinking"
  | "speaking";

export interface Message {
  id: string;
  role: "user" | "teacher";
  text: string;
  audioUrl?: string;
  audioDuration?: number;
  timestamp: number;
}

interface UseConversationReturn {
  messages: Message[];
  isLoading: boolean;
  loadingStage: LoadingStage;
  sessionId: string | null;
  startSession: () => Promise<void>;
  sendAudio: (blob: Blob, durationSec: number) => Promise<void>;
  sendText: (text: string) => Promise<void>;
  playAudio: (url: string) => void;
  stopAudio: () => void;
  isPlaying: boolean;
}

const REQUEST_TIMEOUT_MS = 120_000;

let nextId = 0;
function makeId(): string {
  return `msg-${Date.now()}-${nextId++}`;
}

export function useConversation(): UseConversationReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState<LoadingStage>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const startSession = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/session`, { method: "POST" });
      const data = await res.json();
      setSessionId(data.session_id);

      const greetingMsg: Message = {
        id: makeId(),
        role: "teacher",
        text: data.greeting,
        timestamp: Date.now(),
      };
      setMessages([greetingMsg]);

      try {
        const ttsRes = await fetch(`${API}/api/tts`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: data.greeting }),
        });
        if (ttsRes.ok) {
          const blob = await ttsRes.blob();
          const url = URL.createObjectURL(blob);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === greetingMsg.id ? { ...m, audioUrl: url } : m
            )
          );
          playAudioUrl(url);
        }
      } catch {
        // TTS not available — text-only is fine
      }
    } catch (err) {
      console.error("Failed to start session:", err);
    }
  }, []);

  const playAudioUrl = useCallback((url: string) => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    const audio = new Audio(url);
    audioRef.current = audio;
    setIsPlaying(true);
    audio.onended = () => setIsPlaying(false);
    audio.onerror = () => setIsPlaying(false);
    audio.play().catch(() => setIsPlaying(false));
  }, []);

  const stopAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setIsPlaying(false);
  }, []);

  const sendAudio = useCallback(
    async (blob: Blob, durationSec: number) => {
      if (!sessionId) return;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

      setIsLoading(true);
      setLoadingStage("transcribing");

      const form = new FormData();
      form.append("audio", blob, "recording.webm");
      form.append("session_id", sessionId);

      try {
        const res = await fetch(`${API}/api/converse`, {
          method: "POST",
          body: form,
          signal: controller.signal,
        });

        if (!res.ok) {
          const err = await res.text();
          console.error("Converse failed:", err);
          return;
        }

        const userText = res.headers.get("X-User-Text") ?? "";
        const replyText = res.headers.get("X-Reply-Text") ?? "";

        const userMsg: Message = {
          id: makeId(),
          role: "user",
          text: userText,
          audioDuration: durationSec,
          timestamp: Date.now(),
        };

        const audioBlob = await res.blob();
        const audioUrl =
          audioBlob.size > 0 ? URL.createObjectURL(audioBlob) : undefined;

        const teacherMsg: Message = {
          id: makeId(),
          role: "teacher",
          text: replyText,
          audioUrl,
          timestamp: Date.now(),
        };

        setMessages((prev) => [...prev, userMsg, teacherMsg]);

        if (audioUrl) {
          playAudioUrl(audioUrl);
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          console.error("sendAudio error:", err);
        }
      } finally {
        clearTimeout(timeout);
        abortRef.current = null;
        setIsLoading(false);
        setLoadingStage(null);
      }
    },
    [sessionId, playAudioUrl]
  );

  const sendText = useCallback(
    async (text: string) => {
      if (!sessionId || !text.trim()) return;
      setIsLoading(true);
      setLoadingStage("thinking");

      const userMsg: Message = {
        id: makeId(),
        role: "user",
        text: text.trim(),
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);

      try {
        const chatRes = await fetch(`${API}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: text.trim(), session_id: sessionId }),
        });
        const { reply } = await chatRes.json();

        const teacherMsg: Message = {
          id: makeId(),
          role: "teacher",
          text: reply,
          timestamp: Date.now(),
        };

        try {
          const ttsRes = await fetch(`${API}/api/tts`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: reply }),
          });
          if (ttsRes.ok) {
            const blob = await ttsRes.blob();
            teacherMsg.audioUrl = URL.createObjectURL(blob);
          }
        } catch {
          // TTS unavailable
        }

        setMessages((prev) => [...prev, teacherMsg]);
        if (teacherMsg.audioUrl) {
          playAudioUrl(teacherMsg.audioUrl);
        }
      } catch (err) {
        console.error("sendText error:", err);
      } finally {
        setIsLoading(false);
        setLoadingStage(null);
      }
    },
    [sessionId, playAudioUrl]
  );

  return {
    messages,
    isLoading,
    loadingStage,
    sessionId,
    startSession,
    sendAudio,
    sendText,
    playAudio: playAudioUrl,
    stopAudio,
    isPlaying,
  };
}
