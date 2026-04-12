# English Teacher 🎙️

A fully local, audio-to-audio English conversation partner running on your Mac. Speak naturally, get a spoken response — no cloud, no subscriptions, no internet required after setup.

```
You (mic) → Whisper STT → LM Studio LLM → Orpheus-FastAPI TTS → Speaker
```

---

## What it does

- Listens to you speak English via your microphone
- Transcribes your speech locally with Whisper
- Generates a natural conversation response with a small LLM
- Reads the response aloud using Orpheus TTS — one of the most natural-sounding open-source voices available
- Gently corrects grammar mistakes and keeps the conversation going with follow-up questions

Tuned for **B1–B2 Spanish speakers** practicing conversational English, but easy to adapt for any level or language pair.

---

## Requirements

### Hardware

- Mac with Apple Silicon (M1–M4)
- 16 GB unified memory minimum

### Software

- Python 3.9+
- [LM Studio](https://lmstudio.ai) — serves both the chat model and Orpheus TTS
- [Orpheus-FastAPI](https://github.com/Lex-au/Orpheus-FastAPI) — SNAC decoder bridge for Orpheus audio

### Models (loaded in LM Studio)

| Role       | Model                                       | Size on disk |
| ---------- | ------------------------------------------- | ------------ |
| Chat (LLM) | `google/gemma-3-4b` or any ≤4B chat model   | ~3 GB        |
| TTS        | `isaiahbjork/orpheus-3b-0.1-ft-Q4_K_M-GGUF` | ~2.5 GB      |

Both models run simultaneously via LM Studio's multi-model session. Combined VRAM usage is ~5.5 GB, well within 16 GB.

---

## Installation

### 1. Install LM Studio

Download from [lmstudio.ai](https://lmstudio.ai) and download both models from the Discover tab.

### 2. Install Orpheus-FastAPI

```bash
git clone https://github.com/Lex-au/Orpheus-FastAPI
cd Orpheus-FastAPI
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

```env
ORPHEUS_API_URL=http://localhost:1234/v1/completions
ORPHEUS_MODEL_NAME=orpheus-3b-0.1-ft
ORPHEUS_MAX_TOKENS=8192
```

The value of `ORPHEUS_MODEL_NAME` must match exactly what LM Studio reports — run `curl http://localhost:1234/v1/models` to check.

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the script

Open `english_teacher.py` and update:

```python
# Match the exact model ID shown in LM Studio
CHAT_MODEL    = "google/gemma-3-4b"

# Orpheus voice: tara · leah · jess · leo · dan · mia · zac · zoe
ORPHEUS_VOICE = "tara"

# Whisper size: tiny.en (fastest) · base.en (balanced) · small.en (most accurate)
WHISPER_MODEL = "base.en"
```

---

## Running

Start the services in this order, each in its own terminal:

**Terminal 1 — LM Studio**

```
Open LM Studio → Playground → "+" → Multi Model Session
Load: gemma-3-4b  +  orpheus-3b-0.1-ft
Developer tab → Start Server
```

**Terminal 2 — Orpheus-FastAPI**

```bash
cd Orpheus-FastAPI
python app.py
```

**Terminal 3 — English Teacher**

```bash
python english_teacher.py
```

---

## Usage

```
Press ENTER → speak in English → press ENTER again → listen to the response
Ctrl+C to quit
```

On startup the script checks that all services are running and prints the loaded models. If `CHAT_MODEL` doesn't match, copy the exact name from the output and update the variable.

---

## How it works

```
┌──────────┐    voice     ┌───────────────┐   text   ┌──────────────────────┐
│   You    │ ──────────▶  │  Whisper STT  │ ───────▶ │  LM Studio  (LLM)    │
│  (mic)   │              │  faster-whis  │          │  /v1/chat/completions │
└──────────┘              └───────────────┘          └──────────┬───────────┘
                                                                 │ text
                                                                 ▼
┌──────────┐    audio     ┌───────────────┐          ┌──────────────────────┐
│ Speaker  │ ◀──────────  │ Orpheus-FastAPI│ ◀──────  │  LM Studio  (TTS)    │
│          │              │  SNAC decoder  │  tokens  │  /v1/completions     │
└──────────┘              └───────────────┘          └──────────────────────┘
```

**Why Orpheus-FastAPI is still needed:** Orpheus is not a conventional TTS model. It generates audio as special SNAC tokens via the standard completions endpoint. Orpheus-FastAPI handles the SNAC decoding step and exposes a clean `/v1/audio/speech` endpoint that returns a standard WAV file.

---

## Estimated latency (Apple M4, 16 GB)

| Step                  | Typical time |
| --------------------- | ------------ |
| STT (Whisper base.en) | ~0.3 s       |
| LLM (gemma-3-4b)      | ~1–2 s       |
| TTS (Orpheus Q4_K_M)  | ~3–5 s       |
| **Total per turn**    | **~4–8 s**   |

Most of the latency is in Orpheus synthesis. If you want faster responses at the cost of voice quality, switch to Kokoro via `mlx-audio` — it runs natively on Apple Silicon and reduces TTS latency to under a second.

---

## Customization

### Change the teaching style

Edit `SYSTEM_PROMPT` in `english_teacher.py`. For example, to practice job interview English:

```python
SYSTEM_PROMPT = """You are a professional interview coach helping a non-native English speaker
prepare for a software engineering job interview. Ask common interview questions one at a time,
give concise feedback on vocabulary and clarity after each answer, and keep a professional tone."""
```

### Change Orpheus voice

Available voices and their character:

| Voice  | Style                                                       |
| ------ | ----------------------------------------------------------- |
| `tara` | Female, conversational, clear — best for listening practice |
| `dan`  | Male, casual, friendly — good for informal conversation     |
| `leo`  | Male, authoritative, deep                                   |
| `mia`  | Female, professional, articulate                            |
| `zac`  | Male, enthusiastic, dynamic                                 |
| `zoe`  | Female, calm, soothing                                      |

You can also add emotion tags directly in the system prompt output:

```
I was so surprised! <laugh> I couldn't believe it.
```

Supported tags: `<laugh>`, `<chuckle>`, `<sigh>`, `<cough>`, `<gasp>`, `<yawn>`

---

## Troubleshooting

**`[TTS] Reproduciendo (24000 Hz, 0.0s)`** — Orpheus-FastAPI is not finding the model. Check that `ORPHEUS_MODEL_NAME` in `.env` matches the model ID in LM Studio exactly.

**`[warn] CHAT_MODEL configurado no encontrado`** — Copy the exact model name printed at startup and update `CHAT_MODEL` in the script.

**`[error] LM Studio no responde en puerto 1234`** — Make sure the server is started from the Developer tab in LM Studio, not just the Playground.

**`[error] Orpheus-FastAPI no responde en puerto 5005`** — Check that `python app.py` is running in the Orpheus-FastAPI directory.

**Whisper downloads on first run** — This is normal. `base.en` (~150 MB) downloads once and is cached locally.

---

## Project structure

```
.
├── english_teacher.py   # main pipeline script
└── README.md
```

Orpheus-FastAPI lives in its own cloned repo at whatever path you chose.

---

## License

MIT — do whatever you want with it.

---

_Built for a MacBook Air M4 · Orpheus TTS by [Canopy Labs](https://github.com/canopyai/Orpheus-TTS) · Whisper by OpenAI · LM Studio by [LM Studio](https://lmstudio.ai)_
