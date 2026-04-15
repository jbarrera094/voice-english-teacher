interface Props {
  url: string;
  isPlaying: boolean;
  onPlay: (url: string) => void;
  onStop: () => void;
}

export default function AudioPlayer({ url, isPlaying, onPlay, onStop }: Props) {
  return (
    <button
      onClick={() => (isPlaying ? onStop() : onPlay(url))}
      className="flex items-center gap-2 px-3 py-1.5 rounded-full
                 bg-surface-overlay hover:bg-border-subtle
                 text-xs text-text-secondary transition-colors
                 cursor-pointer w-fit"
      type="button"
    >
      {isPlaying ? (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <rect x="6" y="4" width="4" height="16" rx="1" />
          <rect x="14" y="4" width="4" height="16" rx="1" />
        </svg>
      ) : (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M8 5v14l11-7z" />
        </svg>
      )}
      {isPlaying ? "Stop" : "Play"}
    </button>
  );
}
