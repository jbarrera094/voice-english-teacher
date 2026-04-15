import { useEffect, useState } from "react";

const API = import.meta.env.PUBLIC_API_URL ?? "http://localhost:8000";

interface Health {
  lm_studio: boolean;
  orpheus: boolean;
}

export default function StatusBar() {
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const res = await fetch(`${API}/api/health`);
        if (!cancelled) setHealth(await res.json());
      } catch {
        if (!cancelled) setHealth(null);
      }
    }

    poll();
    const id = setInterval(poll, 15_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const dot = (ok: boolean | null) => {
    if (ok === null) return "bg-text-secondary";
    return ok ? "bg-success" : "bg-danger";
  };

  const apiOk = health !== null;
  const lmOk = health?.lm_studio ?? null;
  const ttsOk = health?.orpheus ?? null;

  return (
    <div className="flex items-center gap-3 text-xs text-text-secondary">
      <span className="flex items-center gap-1.5">
        <span className={`w-2 h-2 rounded-full ${dot(apiOk)}`} />
        API
      </span>
      <span className="flex items-center gap-1.5">
        <span className={`w-2 h-2 rounded-full ${dot(lmOk)}`} />
        LLM
      </span>
      <span className="flex items-center gap-1.5">
        <span className={`w-2 h-2 rounded-full ${dot(ttsOk)}`} />
        TTS
      </span>
    </div>
  );
}
