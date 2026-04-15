"""
EnglishTeacher — reusable engine extracted from english_teacher.py

Wraps Whisper STT, LM Studio chat, and Orpheus TTS into an async-friendly
class that FastAPI endpoints can call without managing global state.
"""

import logging
import os
import tempfile
import uuid
from typing import Optional

import requests
from faster_whisper import WhisperModel
from openai import OpenAI

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a friendly English conversation partner helping a Spanish speaker "
    "at B1-B2 level practice their English.\n\n"
    "Rules:\n"
    "- Always respond in English only, never in Spanish.\n"
    "- Keep responses concise: 2-4 sentences maximum.\n"
    "- Speak naturally and conversationally.\n"
    "- After your answer, ask ONE follow-up question to keep the conversation going.\n"
    "- If the user makes a clear grammar mistake, gently correct it in one sentence.\n"
    "- Use vocabulary appropriate for B1-B2 level: clear but not oversimplified.\n"
    "- Topics: daily life, travel, hobbies, opinions, culture — keep it engaging."
)

GREETING = (
    "Hey! Great to meet you. I'm your English conversation partner. "
    "Just speak naturally — I'll keep you talking. "
    "What did you do today?"
)


class EnglishTeacher:
    def __init__(self):
        self.lm_studio_url = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
        self.chat_model = os.getenv("CHAT_MODEL", "google/gemma-3-4b")
        self.orpheus_tts_url = os.getenv(
            "ORPHEUS_TTS_URL", "http://localhost:5005/v1/audio/speech"
        )
        self.orpheus_voice = os.getenv("ORPHEUS_VOICE", "tara")
        self.orpheus_speed = float(os.getenv("ORPHEUS_SPEED", "1.0"))
        self.whisper_size = os.getenv("WHISPER_MODEL", "large-v3-turbo")
        self.max_history = int(os.getenv("MAX_HISTORY", "10"))

        self.lm = OpenAI(base_url=self.lm_studio_url, api_key="lm-studio")
        self.whisper: Optional[WhisperModel] = None

        # Per-session conversation histories keyed by session id
        self._sessions: dict[str, list[dict]] = {}

    # ------------------------------------------------------------------
    #  Lifecycle
    # ------------------------------------------------------------------

    def load_whisper(self) -> None:
        logger.info("Loading Whisper model '%s' …", self.whisper_size)
        self.whisper = WhisperModel(self.whisper_size, device="cpu", compute_type="int8")
        logger.info("Whisper ready.")

    def create_session(self) -> str:
        sid = uuid.uuid4().hex[:12]
        self._sessions[sid] = []
        return sid

    def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    # ------------------------------------------------------------------
    #  STT
    # ------------------------------------------------------------------

    def transcribe(self, audio_bytes: bytes) -> str:
        if self.whisper is None:
            raise RuntimeError("Whisper model not loaded")

        with tempfile.NamedTemporaryFile(suffix=".webm", delete=True) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()

            segments, info = self.whisper.transcribe(
                tmp.name,
                language="en",
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=400),
                condition_on_previous_text=True,
            )
            text = " ".join(s.text for s in segments).strip()

        if info.duration < 0.4:
            return ""

        return text

    # ------------------------------------------------------------------
    #  LLM
    # ------------------------------------------------------------------

    def get_response(self, user_text: str, session_id: str) -> str:
        history = self._sessions.setdefault(session_id, [])
        history.append({"role": "user", "content": user_text})

        if len(history) > self.max_history * 2:
            self._sessions[session_id] = history[-self.max_history * 2 :]
            history = self._sessions[session_id]

        try:
            resp = self.lm.chat.completions.create(
                model=self.chat_model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
                temperature=0.75,
                max_tokens=200,
            )
        except Exception as e:
            logger.error("LLM error: %s", e)
            return f"[LLM error: {e}]"

        reply = resp.choices[0].message.content.strip()
        history.append({"role": "assistant", "content": reply})
        return reply

    # ------------------------------------------------------------------
    #  TTS
    # ------------------------------------------------------------------

    def synthesize(
        self, text: str, voice: Optional[str] = None, speed: Optional[float] = None
    ) -> bytes:
        resp = requests.post(
            self.orpheus_tts_url,
            json={
                "model": "orpheus",
                "input": text,
                "voice": voice or self.orpheus_voice,
                "response_format": "wav",
                "speed": speed or self.orpheus_speed,
            },
            timeout=90,
        )
        resp.raise_for_status()
        return resp.content

    # ------------------------------------------------------------------
    #  Health
    # ------------------------------------------------------------------

    def check_services(self) -> dict:
        status: dict = {"lm_studio": False, "orpheus": False, "models": []}

        try:
            models = self.lm.models.list()
            status["models"] = [m.id for m in models.data]
            status["lm_studio"] = True
        except Exception:
            pass

        try:
            requests.get(
                self.orpheus_tts_url.rsplit("/", 3)[0], timeout=3
            )
            status["orpheus"] = True
        except Exception:
            pass

        return status
