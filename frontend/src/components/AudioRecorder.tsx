import { useCallback, useEffect, useRef, useState } from "react";

interface Props {
  onRecorded: (blob: Blob, durationSec: number) => void;
  disabled?: boolean;
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function AudioRecorder({ onRecorded, disabled = false }: Props) {
  const [recording, setRecording] = useState(false);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef(0);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm",
      });

      chunks.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data);
      };

      recorder.onstop = () => {
        if (timerRef.current) {
          clearInterval(timerRef.current);
          timerRef.current = null;
        }
        const finalDuration = Math.round(
          (Date.now() - startTimeRef.current) / 1000
        );
        const blob = new Blob(chunks.current, { type: recorder.mimeType });
        stream.getTracks().forEach((t) => t.stop());
        if (blob.size > 0) onRecorded(blob, finalDuration);
        setElapsed(0);
      };

      mediaRecorder.current = recorder;
      startTimeRef.current = Date.now();
      setElapsed(0);
      recorder.start(1000);
      setRecording(true);

      timerRef.current = setInterval(() => {
        setElapsed(Math.round((Date.now() - startTimeRef.current) / 1000));
      }, 1000);
    } catch {
      setPermissionDenied(true);
    }
  }, [onRecorded]);

  const stopRecording = useCallback(() => {
    if (mediaRecorder.current?.state === "recording") {
      mediaRecorder.current.stop();
    }
    setRecording(false);
  }, []);

  const handleClick = useCallback(() => {
    if (recording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [recording, startRecording, stopRecording]);

  if (permissionDenied) {
    return (
      <p className="text-xs text-danger text-center py-2">
        Microphone access denied. Please allow mic access and reload.
      </p>
    );
  }

  return (
    <div className="flex flex-col items-center gap-1">
      <button
        onClick={handleClick}
        disabled={disabled}
        type="button"
        className={`
          relative w-16 h-16 rounded-full flex items-center justify-center
          transition-all duration-200 cursor-pointer
          ${
            recording
              ? "bg-danger shadow-lg shadow-danger/30 scale-110"
              : disabled
                ? "bg-surface-overlay text-text-secondary cursor-not-allowed opacity-50"
                : "bg-accent hover:bg-accent-soft shadow-lg shadow-accent/20 hover:scale-105"
          }
        `}
        aria-label={recording ? "Stop recording" : "Start recording"}
      >
        {recording ? (
          <>
            <span className="absolute inset-0 rounded-full bg-danger/30 animate-ping" />
            <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          </>
        ) : (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
            <path d="M12 1a4 4 0 0 0-4 4v7a4 4 0 0 0 8 0V5a4 4 0 0 0-4-4Z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2H3v2a9 9 0 0 0 8 8.94V23h2v-2.06A9 9 0 0 0 21 12v-2h-2Z" />
          </svg>
        )}
      </button>
      {recording && (
        <span className="text-xs font-mono text-danger tabular-nums">
          {formatDuration(elapsed)}
        </span>
      )}
    </div>
  );
}
