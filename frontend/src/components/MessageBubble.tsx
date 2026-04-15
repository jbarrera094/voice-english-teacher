import type { Message } from "../hooks/useConversation";
import AudioPlayer from "./AudioPlayer";

interface Props {
  message: Message;
  onPlay: (url: string) => void;
  onStop: () => void;
  isPlaying: boolean;
}

export default function MessageBubble({ message, onPlay, onStop, isPlaying }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      <div className={`max-w-[80%] flex flex-col gap-1.5`}>
        <div className="flex items-center gap-2 px-1">
          {!isUser ? (
            <span className="text-xs font-medium text-accent">Teacher</span>
          ) : null}
          {isUser ? (
            <span className="text-xs font-medium text-user-bubble ml-auto">You</span>
          ) : null}
        </div>

        <div
          className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
            isUser
              ? "bg-user-bubble text-white rounded-br-md"
              : "bg-teacher-bubble text-text-primary rounded-bl-md"
          }`}
        >
          {message.text}
          {isUser && message.audioDuration != null && message.audioDuration > 0 ? (
            <span className="block text-[11px] opacity-60 mt-1">
              {Math.floor(message.audioDuration / 60)}:
              {(message.audioDuration % 60).toString().padStart(2, "0")} audio
            </span>
          ) : null}
        </div>

        {message.audioUrl ? (
          <AudioPlayer
            url={message.audioUrl}
            isPlaying={isPlaying}
            onPlay={onPlay}
            onStop={onStop}
          />
        ) : null}
      </div>
    </div>
  );
}
