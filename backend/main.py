"""
FastAPI backend for the English Teacher web app.

Endpoints expose the Whisper → LM Studio → Orpheus pipeline
so the Astro frontend can drive conversations via HTTP.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from teacher import EnglishTeacher, GREETING

# Load .env from backend/ dir first, fall back to project root
_here = Path(__file__).resolve().parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

teacher: EnglishTeacher


@asynccontextmanager
async def lifespan(app: FastAPI):
    global teacher
    teacher = EnglishTeacher()
    teacher.load_whisper()
    logger.info("English Teacher ready.")
    yield


app = FastAPI(title="English Teacher API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4321",
        "http://localhost:3000",
        "http://127.0.0.1:4321",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-User-Text", "X-Reply-Text"],
)


# ── Request / Response models ──────────────────────────

class ChatRequest(BaseModel):
    text: str
    session_id: str


class ChatResponse(BaseModel):
    reply: str


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    speed: Optional[float] = None


class TranscribeResponse(BaseModel):
    text: str


class SessionResponse(BaseModel):
    session_id: str
    greeting: str


class SessionHistoryResponse(BaseModel):
    session_id: str
    history: list[dict]


class HealthResponse(BaseModel):
    lm_studio: bool
    orpheus: bool
    models: list[str]


# ── Endpoints ──────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse)
async def health():
    return teacher.check_services()


@app.post("/api/session", response_model=SessionResponse)
async def create_session():
    sid = teacher.create_session()
    return SessionResponse(session_id=sid, greeting=GREETING)


@app.get("/api/session/{session_id}", response_model=SessionHistoryResponse)
async def get_session(session_id: str):
    history = teacher.get_session_history(session_id)
    if history is None:
        raise HTTPException(404, "Session not found")
    return SessionHistoryResponse(session_id=session_id, history=history)


@app.post("/api/transcribe", response_model=TranscribeResponse)
async def transcribe(
    audio: UploadFile = File(...),
    session_id: str = Form(""),
):
    data = await audio.read()
    if not data:
        raise HTTPException(400, "Empty audio file")
    text = await asyncio.to_thread(teacher.transcribe, data)
    if not text:
        raise HTTPException(422, "No speech detected")
    return TranscribeResponse(text=text)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    reply = await asyncio.to_thread(teacher.get_response, req.text, req.session_id)
    return ChatResponse(reply=reply)


@app.post("/api/tts")
async def tts(req: TTSRequest):
    try:
        wav = await asyncio.to_thread(teacher.synthesize, req.text, req.voice, req.speed)
    except Exception as e:
        raise HTTPException(502, f"TTS error: {e}")
    return Response(content=wav, media_type="audio/wav")


@app.post("/api/converse")
async def converse(
    audio: UploadFile = File(...),
    session_id: str = Form(...),
    voice: Optional[str] = Form(None),
    speed: Optional[float] = Form(None),
):
    """Full pipeline: audio in → transcribe → LLM → TTS → audio + text out."""
    data = await audio.read()
    if not data:
        raise HTTPException(400, "Empty audio file")

    user_text = await asyncio.to_thread(teacher.transcribe, data)
    if not user_text:
        raise HTTPException(422, "No speech detected")

    reply = await asyncio.to_thread(teacher.get_response, user_text, session_id)

    try:
        wav = await asyncio.to_thread(teacher.synthesize, reply, voice, speed)
    except Exception as e:
        logger.error("TTS failed, returning text only: %s", e)
        wav = b""

    headers = {
        "X-User-Text": user_text,
        "X-Reply-Text": reply,
    }
    return Response(content=wav, media_type="audio/wav", headers=headers)
