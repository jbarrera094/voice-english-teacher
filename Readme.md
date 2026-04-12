# voice-english-teacher · `remote-brain-with-kokoro`

Audio-to-audio English conversation partner using Groq as the LLM and Kokoro for local TTS.

```
You (mic) → Whisper STT → Groq API → Kokoro Docker → Speaker
```

---

## Stack

| Component | Service                 | Details                             |
| --------- | ----------------------- | ----------------------------------- |
| STT       | faster-whisper          | runs locally, no server needed      |
| LLM       | Groq API                | `llama-3.1-8b-instant`, ~0.3 s      |
| TTS       | Kokoro-FastAPI (Docker) | `kokoro-fastapi-cpu:v0.2.2`, ~1–2 s |

**Total latency on M4:** ~2–3 s per turn.

---

## Requirements

- Python 3.9+
- Docker
- A free Groq API key — [console.groq.com](https://console.groq.com)

---

## Setup

### 1. Install Python dependencies

```bash
pip install faster-whisper sounddevice soundfile numpy openai python-dotenv
```

### 2. Start Kokoro via Docker

```bash
docker run -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-cpu:v0.2.2
```

The model (~345 MB) downloads automatically on first run. Use this exact version tag — `latest` has stability issues on Apple Silicon.

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
GROQ_API_KEY=gsk_your_key_here
KOKORO_MODEL=kokoro
KOKORO_VOICE=af_heart
```

### 4. Run

```bash
python english_teacher_kokoro.py
```

```
Press ENTER → speak in English → press ENTER again → listen to the response
Ctrl+C to quit
```

---

## Environment variables

| Variable        | Default                | Description                                  |
| --------------- | ---------------------- | -------------------------------------------- |
| `GROQ_API_KEY`  | —                      | Required. Get one free at console.groq.com   |
| `GROQ_MODEL`    | `llama-3.1-8b-instant` | `llama-3.3-70b-versatile` for higher quality |
| `KOKORO_MODEL`  | `kokoro`               | Do not change                                |
| `KOKORO_VOICE`  | `af_heart`             | See voices below                             |
| `KOKORO_SPEED`  | `1.0`                  | Range 0.5–2.0                                |
| `WHISPER_MODEL` | `base.en`              | `tiny.en` for speed, `small.en` for accuracy |
| `MAX_HISTORY`   | `12`                   | Conversation turns to remember               |

---

## Kokoro voices

| Voice                                       | Accent          |
| ------------------------------------------- | --------------- |
| `af_heart`, `af_bella`, `af_nova`, `af_sky` | American female |
| `am_adam`, `am_echo`                        | American male   |
| `bf_alice`, `bf_emma`                       | British female  |
| `bm_daniel`, `bm_george`                    | British male    |

---

## Customization

Edit `SYSTEM_PROMPT` in `english_teacher_kokoro.py` to change the teaching style. For example, to practice job interview English:

```python
SYSTEM_PROMPT = """You are a professional interview coach helping a non-native English speaker
prepare for a software engineering job interview. Ask one interview question at a time,
give brief feedback on vocabulary and clarity, and keep a professional tone."""
```

---

## Troubleshooting

**`Error code: 400 - invalid_model`** — Make sure `KOKORO_MODEL=kokoro` in your `.env` (not the mlx-audio model name).

**`[error] Kokoro-FastAPI no responde en puerto 8880`** — Check the Docker container is running with the pinned version `v0.2.2`.

**Whisper downloads on first run** — Normal. `base.en` (~150 MB) downloads once and is cached locally.

---

## License

MIT

---

_Kokoro by [hexgrad](https://huggingface.co/hexgrad/Kokoro-82M) · Whisper by OpenAI · Groq by [groq.com](https://groq.com)_
