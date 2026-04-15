import { useCallback, useEffect, useRef, useState } from "react";
import { useConversation } from "../hooks/useConversation";
import type { LoadingStage } from "../hooks/useConversation";
import AudioRecorder from "./AudioRecorder";
import MessageBubble from "./MessageBubble";

const STAGE_LABELS: Record<Exclude<LoadingStage, null>, string> = {
  transcribing: "Processing your audio…",
  thinking: "Thinking…",
  speaking: "Generating speech…",
};

export default function ChatWindow() {
  const {
    messages,
    isLoading,
    loadingStage,
    sessionId,
    startSession,
    sendAudio,
    sendText,
    playAudio,
    stopAudio,
    isPlaying,
  } = useConversation();

  const [textInput, setTextInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    startSession();
  }, [startSession]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleTextSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (textInput.trim() && !isLoading) {
        sendText(textInput);
        setTextInput("");
      }
    },
    [textInput, isLoading, sendText]
  );

  const handleRecorded = useCallback(
    (blob: Blob, durationSec: number) => {
      sendAudio(blob, durationSec);
    },
    [sendAudio]
  );

  const hasMessages = messages.length > 0;
  const stageLabel = loadingStage ? STAGE_LABELS[loadingStage] : "Thinking…";

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto">
          {!hasMessages ? (
            <div className="flex items-center justify-center h-full text-text-secondary text-sm">
              Connecting to your teacher...
            </div>
          ) : null}

          {messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              onPlay={playAudio}
              onStop={stopAudio}
              isPlaying={isPlaying}
            />
          ))}

          {isLoading ? (
            <div className="flex justify-start mb-3">
              <div className="bg-teacher-bubble rounded-2xl rounded-bl-md px-4 py-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex gap-1.5">
                    <span className="w-2 h-2 bg-text-secondary rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-2 h-2 bg-text-secondary rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-2 h-2 bg-text-secondary rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                  <span className="text-xs text-text-secondary">
                    {stageLabel}
                  </span>
                </div>
              </div>
            </div>
          ) : null}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 border-t border-border-subtle bg-surface-raised">
        <div className="max-w-3xl mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            {/* Text input */}
            <form onSubmit={handleTextSubmit} className="flex-1 flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder={
                  isLoading
                    ? stageLabel
                    : "Type a message or use the mic..."
                }
                disabled={isLoading || !sessionId}
                className="flex-1 bg-surface-overlay border border-border-subtle rounded-xl
                           px-4 py-2.5 text-sm text-text-primary placeholder-text-secondary
                           focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/30
                           disabled:opacity-50 transition-colors"
              />
              <button
                type="submit"
                disabled={!textInput.trim() || isLoading || !sessionId}
                className="px-4 py-2.5 rounded-xl bg-accent text-black text-sm font-medium
                           hover:bg-accent-soft disabled:opacity-30 disabled:cursor-not-allowed
                           transition-colors cursor-pointer"
              >
                Send
              </button>
            </form>

            {/* Mic button */}
            <AudioRecorder
              onRecorded={handleRecorded}
              disabled={isLoading || !sessionId}
            />
          </div>

          <p className="text-center text-xs text-text-secondary mt-3">
            Press the mic button and speak in English. Press again to stop and send.
          </p>
        </div>
      </div>
    </div>
  );
}
