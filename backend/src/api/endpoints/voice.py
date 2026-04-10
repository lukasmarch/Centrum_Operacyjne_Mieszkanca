"""
Voice Transcription Endpoint
POST /api/voice/transcribe — transkrypcja audio przez OpenAI Whisper
Działa na wszystkich przeglądarkach (Chrome iOS, Firefox, Safari)
"""
import tempfile
import os
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException
from openai import AsyncOpenAI

from src.utils.logger import setup_logger

router = APIRouter(prefix="/api/voice", tags=["voice"])
logger = setup_logger("VoiceAPI")

_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="OpenAI API key not configured")
        _client = AsyncOpenAI(api_key=api_key)
    return _client


ALLOWED_MIME_TYPES = {
    "audio/webm", "audio/webm;codecs=opus", "audio/ogg", "audio/ogg;codecs=opus",
    "audio/mp4", "audio/mpeg", "audio/wav", "audio/x-wav",
    "video/webm",  # niektóre przeglądarki wysyłają webm jako video/
}

EXTENSION_MAP = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".mp4",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "video/webm": ".webm",
}


@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Transkrybuje nagranie audio na tekst (pl-PL) przez OpenAI Whisper.
    Przyjmuje webm/ogg/mp4/wav z MediaRecorder API przeglądarki.
    """
    content_type = (audio.content_type or "").split(";")[0].strip()

    # Fallback jeśli przeglądarka nie wyśle content-type
    ext = EXTENSION_MAP.get(content_type, ".webm")

    data = await audio.read()
    if len(data) < 1000:
        raise HTTPException(status_code=400, detail="Plik audio zbyt krótki")
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Plik audio zbyt duży (max 10MB)")

    client = _get_client()

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            response = await client.audio.transcriptions.create(
                model="whisper-1",
                file=(f"audio{ext}", f, f"audio/{ext.lstrip('.')}"),
                language="pl",
                response_format="text",
            )
        transcript = response.strip() if isinstance(response, str) else str(response).strip()
        logger.info(f"Whisper transcript ({len(data)} bytes): '{transcript[:60]}'")
        return {"transcript": transcript}
    except Exception as e:
        logger.error(f"Whisper error: {e}")
        raise HTTPException(status_code=502, detail="Błąd transkrypcji audio")
    finally:
        os.unlink(tmp_path)
