"""
Voice Transcription Endpoint (Whisper)
POST /api/voice/transcribe — transkrypcja audio przez OpenAI Whisper
Działa na wszystkich przeglądarkach (Chrome iOS, Firefox, Safari)
"""
import tempfile
import os
from collections import defaultdict
from datetime import date
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from openai import AsyncOpenAI

from src.api.endpoints.chat import _hash_ip
from src.services.time_span import local_now
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


# Limit kosztu Whispera (audyt 11.10.2026, F-025). Endpoint jest publiczny
# z wyboru — mikrofon w pasku pytania działa też bez konta — ale do tej pory
# nie miał ŻADNEJ granicy: pętla żądań po 10 MB mogła wypalić kredyty OpenAI,
# a bez kredytów staje cała kategoryzacja (precedens 2.09).
# Licznik w pamięci, nie w bazie: jeden worker (`--workers 1`), a restart
# zerujący liczniki to akceptowalna cena za brak migracji. Na sztywno, bez
# rozróżnienia zalogowanych: front wysyła nagranie bez tokenu.
# ⚠️ Działa per osoba dopiero z `--forwarded-allow-ips` w compose — bez tego
# każdy ma IP Caddy i pierwsze PER_IP nagrań gminy blokuje mikrofon wszystkim.
VOICE_PER_IP_DAILY = 20
VOICE_GLOBAL_DAILY = 300
_voice_day: Optional[date] = None
_voice_per_ip: dict = defaultdict(int)
_voice_total = 0


def _check_voice_limit(request: Request) -> None:
    global _voice_day, _voice_total
    today = local_now().date()
    if _voice_day != today:
        _voice_day = today
        _voice_per_ip.clear()
        _voice_total = 0
    key = _hash_ip(request.client.host if request.client else "unknown")
    if _voice_total >= VOICE_GLOBAL_DAILY:
        logger.warning(f"Whisper: dzienny sufit {VOICE_GLOBAL_DAILY} wyczerpany")
        raise HTTPException(status_code=429, detail="Dzienny limit nagrań wyczerpany — wpisz pytanie")
    if _voice_per_ip[key] >= VOICE_PER_IP_DAILY:
        raise HTTPException(status_code=429, detail="Dzienny limit nagrań wyczerpany — wpisz pytanie")
    _voice_per_ip[key] += 1
    _voice_total += 1


@router.post("/transcribe")
async def transcribe_audio(request: Request, audio: UploadFile = File(...)):
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

    # Po walidacji: odrzucone nagranie nie kosztuje nic, więc nie zjada limitu
    _check_voice_limit(request)

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
        # Bez treści: pytanie mieszkańca bywa daną osobową, a log żyje dłużej niż potrzeba
        logger.info(f"Whisper transcript ({len(data)} bytes → {len(transcript)} chars)")
        return {"transcript": transcript}
    except Exception as e:
        logger.error(f"Whisper error: {e}")
        raise HTTPException(status_code=502, detail="Błąd transkrypcji audio")
    finally:
        os.unlink(tmp_path)
# voice
