#!/usr/bin/env python3
"""
English Teacher — variante con Kokoro TTS (Docker)
====================================================
Stack:
  STT  : faster-whisper          (local)
  LLM  : Groq API                (cloud, ~0.3s)
  TTS  : Kokoro-FastAPI (Docker) (local, ~1-2s en M4 CPU)

Ventajas vs variante Orpheus:
  · TTS de 11s baja a ~1-2s — mucho más conversacional
  · Sin LM Studio, sin Orpheus-FastAPI, sin dependencias MLX
  · Setup de un solo comando Docker
  · Imagen arm64 nativa para Apple Silicon

Prereqs — instalar una sola vez:
  pip install faster-whisper sounddevice soundfile numpy openai python-dotenv

Servicios que deben estar corriendo ANTES de ejecutar este script:
  1. Kokoro-FastAPI via Docker (versión estable):
       docker run -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-cpu:v0.2.2
     (descarga el modelo automáticamente la primera vez, ~345 MB)

  2. Nada más — sin LM Studio, sin Orpheus-FastAPI
"""

import sys
import io
import os
import numpy as np
import sounddevice as sd
import soundfile as sf
from openai import OpenAI
from faster_whisper import WhisperModel
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────
#  Configuración
# ─────────────────────────────────────────────────────
GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "gsk_TU_API_KEY_AQUI")
GROQ_MODEL    = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# Modelo Kokoro — con Docker no se especifica, el servidor lo maneja internamente
KOKORO_MODEL  = os.getenv("KOKORO_MODEL", "kokoro")

# Voces inglés americano : af_heart · af_bella · af_nova · af_sky · am_adam · am_echo
# Voces inglés británico : bf_alice · bf_emma · bm_daniel · bm_george
KOKORO_VOICE  = os.getenv("KOKORO_VOICE", "af_heart")
KOKORO_SPEED  = float(os.getenv("KOKORO_SPEED", "1.0"))

# Whisper: tiny.en · base.en · small.en
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base.en")

SAMPLE_RATE    = 16_000
MAX_HISTORY    = int(os.getenv("MAX_HISTORY", "12"))

SYSTEM_PROMPT = """You are a friendly English conversation partner helping a Spanish speaker \
at B1-B2 level practice their English.

Rules:
- Always respond in English only, never in Spanish.
- Keep responses concise: 2-4 sentences maximum.
- Speak naturally and conversationally.
- After your answer, ask ONE follow-up question to keep the conversation going.
- If the user makes a clear grammar mistake, gently correct it in one sentence.
- Use vocabulary appropriate for B1-B2 level: clear but not oversimplified.
- Topics: daily life, travel, hobbies, opinions, culture — keep it engaging."""

# ─────────────────────────────────────────────────────
#  Estado global
# ─────────────────────────────────────────────────────
conversation_history = []
recording            = False
recorded_frames      = []
sd_stream            = None

groq = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
)


# ─────────────────────────────────────────────────────
#  Whisper
# ─────────────────────────────────────────────────────
def load_whisper():
    print(f"[setup] Cargando Whisper '{WHISPER_MODEL}'...")
    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    print("[setup] Whisper listo.\n")
    return model


# ─────────────────────────────────────────────────────
#  Grabación push-to-talk
# ─────────────────────────────────────────────────────
def _audio_cb(indata, frames, time, status):
    if recording:
        recorded_frames.append(indata.copy())

def start_recording():
    global recording, recorded_frames, sd_stream
    recorded_frames = []
    recording = True
    sd_stream = sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1,
        dtype="float32", callback=_audio_cb,
    )
    sd_stream.start()
    print("  [REC] Grabando... pulsa ENTER para detener")

def stop_recording():
    global recording, sd_stream
    recording = False
    if sd_stream:
        sd_stream.stop()
        sd_stream.close()
        sd_stream = None
    if not recorded_frames:
        return None
    audio = np.concatenate(recorded_frames, axis=0).flatten()
    if len(audio) < SAMPLE_RATE * 0.4:
        return None
    return audio


# ─────────────────────────────────────────────────────
#  STT — faster-whisper
# ─────────────────────────────────────────────────────
def transcribe(whisper_model, audio: np.ndarray) -> str:
    print("  [STT] Transcribiendo...")
    buf = io.BytesIO()
    sf.write(buf, audio, SAMPLE_RATE, format="WAV")
    buf.seek(0)
    segments, _ = whisper_model.transcribe(
        buf,
        language="en",
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=400),
    )
    return " ".join(s.text for s in segments).strip()


# ─────────────────────────────────────────────────────
#  LLM — Groq API
# ─────────────────────────────────────────────────────
def get_response(user_text: str) -> str:
    global conversation_history
    conversation_history.append({"role": "user", "content": user_text})

    if len(conversation_history) > MAX_HISTORY * 2:
        conversation_history = conversation_history[-(MAX_HISTORY * 2):]

    print("  [LLM] Groq pensando...")
    try:
        resp = groq.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history,
            temperature=0.75,
            max_tokens=120,
        )
    except Exception as e:
        return f"[Groq error: {e}]"

    reply = resp.choices[0].message.content.strip()
    conversation_history.append({"role": "assistant", "content": reply})
    return reply


# ─────────────────────────────────────────────────────
#  TTS — Kokoro via Kokoro-FastAPI Docker (OpenAI SDK)
# ─────────────────────────────────────────────────────

# Cliente dedicado para Kokoro (separado del cliente Groq)
kokoro = OpenAI(
    base_url="http://localhost:8880/v1",
    api_key="not-needed",
)

def speak(text: str):
    print("  [TTS] Kokoro sintetizando...")
    try:
        response = kokoro.audio.speech.create(
            model=KOKORO_MODEL,
            voice=KOKORO_VOICE,
            input=text,
            response_format="wav",
            speed=KOKORO_SPEED,
        )
        audio_data, sr = sf.read(io.BytesIO(response.content))
        print(f"  [TTS] Reproduciendo ({sr} Hz, {len(audio_data)/sr:.1f}s)...")
        sd.play(audio_data, sr)
        sd.wait()
    except Exception as e:
        err = str(e)
        if "Connection" in err or "refused" in err.lower():
            print("  [error] Kokoro-FastAPI no responde en puerto 8880.")
            print("          Ejecuta: docker run -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-cpu:v0.2.2")
        else:
            print(f"  [error] TTS: {e}")


# ─────────────────────────────────────────────────────
#  Verificar servicios al arranque
# ─────────────────────────────────────────────────────
def check_services() -> bool:
    ok = True

    # Groq
    if GROQ_API_KEY.startswith("gsk_TU_API_KEY"):
        print("[error] Groq API key no configurada.")
        print("        Edita tu .env y añade: GROQ_API_KEY=gsk_...")
        ok = False
    else:
        try:
            groq.models.list()
            print(f"[ok] Groq API activa — modelo: {GROQ_MODEL}")
        except Exception as e:
            print(f"[error] Groq API: {e}")
            ok = False

    # Kokoro-FastAPI Docker
    try:
        kokoro.models.list()
        print(f"[ok] Kokoro-FastAPI Docker activo — voz: {KOKORO_VOICE}")
    except Exception:
        print("[error] Kokoro-FastAPI no responde en puerto 8880.")
        print("        Ejecuta en otra terminal:")
        print("        docker run -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-cpu:v0.2.2")
        ok = False

    print()
    return ok


# ─────────────────────────────────────────────────────
#  Loop principal
# ─────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  English Teacher · LLM: Groq  |  TTS: Kokoro Docker")
    print("=" * 55 + "\n")

    if not check_services():
        print("[abort] Resuelve los errores anteriores y vuelve a intentarlo.")
        sys.exit(1)

    whisper_model = load_whisper()

    print("Cómo usar:")
    print("  ENTER  → empezar a grabar")
    print("  ENTER  → parar y procesar")
    print("  Ctrl+C → salir\n")

    greeting = (
        "Hey! I'm your English conversation partner. "
        "I'll help you practice naturally and correct any mistakes along the way. "
        "What have you been up to today?"
    )
    print(f"[Teacher] {greeting}\n")
    speak(greeting)

    while True:
        try:
            input("  Pulsa ENTER para hablar...")
        except KeyboardInterrupt:
            print("\n\n[bye] ¡Hasta la próxima!")
            break

        start_recording()

        try:
            input()
        except KeyboardInterrupt:
            stop_recording()
            print("\n\n[bye] ¡Hasta la próxima!")
            break

        audio = stop_recording()
        if audio is None:
            print("  [warn] Audio demasiado corto. Inténtalo de nuevo.\n")
            continue

        user_text = transcribe(whisper_model, audio)
        if not user_text:
            print("  [warn] No se detectó habla. ¿Estás hablando en inglés?\n")
            continue

        print(f"\n  [You]     {user_text}")
        reply = get_response(user_text)
        print(f"  [Teacher] {reply}\n")
        speak(reply)


if __name__ == "__main__":
    main()