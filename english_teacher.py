#!/usr/bin/env python3
"""
English Teacher — pipeline audio→audio  (solo LM Studio)
=========================================================
Stack:
  STT  : faster-whisper  (local, sin servidor)
  LLM  : LM Studio  →  http://localhost:1234/v1/chat/completions
  TTS  : LM Studio  →  Orpheus-FastAPI  →  http://localhost:5005

Prereqs — instalar una sola vez:
  pip install faster-whisper sounddevice soundfile numpy openai requests

Servicios que deben estar corriendo ANTES de ejecutar este script:
  ┌─────────────────────────────────────────────────────────────┐
  │ 1. LM Studio — Multi-model session                          │
  │    · Abre Playground → clic "+" → Multi Model Session       │
  │    · Carga: gemma-3-4b-it  (o cualquier chat model ≤4B)     │
  │    · Carga: orpheus-3b-0.1-ft-q4_k_m  (ya lo tienes)       │
  │    · Developer tab → Start Server                           │
  │                                                             │
  │ 2. Orpheus-FastAPI (decodificador SNAC)                     │
  │    git clone https://github.com/Lex-au/Orpheus-FastAPI      │
  │    cd Orpheus-FastAPI && pip install -r requirements.txt     │
  │    python app.py                                            │
  └─────────────────────────────────────────────────────────────┘

Para ver los nombres exactos de los modelos cargados:
  curl http://localhost:1234/v1/models

Uso:
  python english_teacher.py
  → ENTER para empezar a grabar tu voz
  → ENTER de nuevo para parar y procesar
  → Ctrl+C para salir
"""

import sys
import io
import numpy as np
import sounddevice as sd
import soundfile as sf
import requests
from openai import OpenAI
from faster_whisper import WhisperModel

# ─────────────────────────────────────────────────────
#  Configuración — ajusta estos valores según tu setup
# ─────────────────────────────────────────────────────

# Nombre del modelo de chat tal como aparece en LM Studio.
# → Developer tab → copia el identificador exacto del modelo cargado.
# Ejemplos comunes:
#   "lmstudio-community/gemma-3-4b-it-GGUF/gemma-3-4b-it-Q4_K_M.gguf"
#   "bartowski/Llama-3.2-3B-Instruct-GGUF/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
CHAT_MODEL    = "google/gemma-3-4b"

# Voz de Orpheus: tara · leah · jess · leo · dan · mia · zac · zoe
ORPHEUS_VOICE = "tara"
ORPHEUS_SPEED = 1.0

# Whisper: tiny.en (más rápido) · base.en (equilibrado) · small.en (más preciso)
WHISPER_MODEL = "base.en"

LM_STUDIO_URL   = "http://localhost:1234/v1"
ORPHEUS_TTS_URL = "http://localhost:5005/v1/audio/speech"
SAMPLE_RATE     = 16_000   # Hz — requerido por Whisper
MAX_HISTORY     = 10       # turnos de conversación a recordar

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

# Cliente OpenAI apuntando a LM Studio
lm = OpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")


# ─────────────────────────────────────────────────────
#  Whisper — carga única al inicio
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
#  LLM — LM Studio /v1/chat/completions
# ─────────────────────────────────────────────────────
def get_response(user_text: str) -> str:
    global conversation_history
    conversation_history.append({"role": "user", "content": user_text})

    if len(conversation_history) > MAX_HISTORY * 2:
        conversation_history = conversation_history[-(MAX_HISTORY * 2):]

    print("  [LLM] Pensando...")
    try:
        resp = lm.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history,
            temperature=0.75,
            max_tokens=200,
        )
    except Exception as e:
        return f"[LLM error: {e}]"

    reply = resp.choices[0].message.content.strip()
    conversation_history.append({"role": "assistant", "content": reply})
    return reply


# ─────────────────────────────────────────────────────
#  TTS — Orpheus-FastAPI (llama internamente a LM Studio)
# ─────────────────────────────────────────────────────
def speak(text: str):
    print("  [TTS] Sintetizando con Orpheus...")
    try:
        resp = requests.post(
            ORPHEUS_TTS_URL,
            json={
                "model": "orpheus",
                "input": text,
                "voice": ORPHEUS_VOICE,
                "response_format": "wav",
                "speed": ORPHEUS_SPEED,
            },
            timeout=90,
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("  [error] Orpheus-FastAPI no responde en puerto 5005.")
        print("          Ejecuta: cd Orpheus-FastAPI && python app.py")
        return
    except Exception as e:
        print(f"  [error] TTS: {e}")
        return

    audio_data, sr = sf.read(io.BytesIO(resp.content))
    print(f"  [TTS] Reproduciendo ({sr} Hz, {len(audio_data)/sr:.1f}s)...")
    sd.play(audio_data, sr)
    sd.wait()


# ─────────────────────────────────────────────────────
#  Verificar servicios al arranque
# ─────────────────────────────────────────────────────
def check_services() -> bool:
    ok = True

    # LM Studio
    try:
        models = lm.models.list()
        names  = [m.id for m in models.data]
        print(f"[ok] LM Studio activo — {len(names)} modelo(s) cargado(s):")
        for n in names:
            print(f"     · {n}")

        # Avisar si el modelo de chat configurado no coincide
        chat_found = any(CHAT_MODEL in n or n in CHAT_MODEL for n in names)
        if not chat_found:
            print(f"\n[warn] CHAT_MODEL configurado no encontrado:")
            print(f"       '{CHAT_MODEL}'")
            print(f"       Actualiza CHAT_MODEL en el script con uno de los nombres de arriba.\n")
    except Exception:
        print("[error] LM Studio no responde en puerto 1234.")
        print("        Abre LM Studio → Developer tab → Start Server")
        ok = False

    # Orpheus-FastAPI
    try:
        requests.get("http://localhost:5005", timeout=3)
        print("[ok] Orpheus-FastAPI activo.")
    except Exception:
        print("[error] Orpheus-FastAPI no responde en puerto 5005.")
        print("        Ejecuta: cd Orpheus-FastAPI && python app.py")
        ok = False

    print()
    return ok


# ─────────────────────────────────────────────────────
#  Loop principal
# ─────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  English Teacher · backend: solo LM Studio")
    print("=" * 55 + "\n")

    if not check_services():
        print("[abort] Arranca los servicios indicados y vuelve a intentarlo.")
        sys.exit(1)

    whisper_model = load_whisper()

    print("Cómo usar:")
    print("  ENTER  → empezar a grabar")
    print("  ENTER  → parar y procesar")
    print("  Ctrl+C → salir\n")

    # Saludo inicial hablado
    greeting = (
        "Hey! Great to meet you. I'm your English conversation partner. "
        "Just speak naturally — I'll keep you talking. "
        "What did you do today?"
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
