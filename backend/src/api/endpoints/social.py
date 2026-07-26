"""
Social media — API dla n8n. Backend przygotowuje gotowy post, n8n go tylko akceptuje.

Podział odpowiedzialności (świadomy, po rewizji 2026-07-25):
  • backend  — treść, prompt, generowanie grafiki w kie.ai, trwałe hostowanie plików
  • n8n      — cron, przycisk akceptacji na Telegramie, wywołanie Facebook Graph API

Dzięki temu każdy workflow w n8n to prosta linia ~7 nodów bez rozgałęzień, a zmiana
copy czy promptu to commit, nie klikanie po UI.

Endpointy (wszystkie wymagają nagłówka `X-Social-Token`):
  GET  /api/social/proposal?kind=text     → gotowy post tekstowy z dziennego podsumowania
  GET  /api/social/proposal?kind=photo    → post z grafiką AI (kie.ai → uploads/social/)
  GET  /api/social/campaign/due           → pozycja kampanii przypadająca na teraz
  POST /api/social/media                  → skopiuj grafikę z URL-a do uploads/social/
  GET  /api/social/media                  → lista grafik (weryfikacja)

Grafiki mają JEDNO miejsce: uploads/social/ → https://api.rybnolive.pl/uploads/social/…
(wolumen `uploads`, ten sam wzorzec co logo wizytówek i zdjęcia zgłoszeń — StaticFiles
zamontowane w main.py). Wcześniej leżały w dwóch: frontend/public/kampania/ → /kampania/
oraz nieudokumentowane /campaign/ wprost na wolumenie, co wymagało rebuildu frontendu
przy każdej nowej grafice i uniemożliwiało hostowanie grafik generowanych w locie.
"""
import hashlib
import ipaddress
import logging
import re
import socket
import uuid
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import select

from src.config import settings
from src.database import DailySummary
from src.database.connection import async_session
from src.services import social_card, social_content

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/social", tags=["social"])

SOCIAL_UPLOAD_DIR = Path(__file__).parent.parent.parent.parent / "uploads" / "social"
SOCIAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 8 * 1024 * 1024  # grafiki FB mają ~0,2-0,7MB, zapas na 4K
DOWNLOAD_TIMEOUT = 60.0

# Rozszerzenie z Content-Type, nie z URL-a — kie.ai zwraca linki bez .png
MIME_TO_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
}

SLUG_RE = re.compile(r"[^a-z0-9-]+")
SUBDIR_RE = re.compile(r"^[a-z0-9_-]{1,32}$")


class MediaFromUrl(BaseModel):
    source_url: str = Field(..., description="Publiczny https URL grafiki (np. wynik kie.ai)")
    slug: str = Field("post", max_length=60, description="Człon nazwy pliku, np. 'post-agenci'")
    subdir: Optional[str] = Field(None, description="Opcjonalny podkatalog, np. 'kampania'")


# ──────────────────────────────────────────────────────────────────────────────
# Autoryzacja i pomocnicze
# ──────────────────────────────────────────────────────────────────────────────

def _require_token(token: Optional[str]) -> None:
    """Współdzielony sekret dla n8n. Brak konfiguracji = endpointy wyłączone."""
    expected = settings.SOCIAL_MEDIA_TOKEN
    if not expected:
        raise HTTPException(status_code=503, detail="Endpoint nieskonfigurowany (SOCIAL_MEDIA_TOKEN)")
    if not token or not _constant_time_eq(token, expected):
        raise HTTPException(status_code=401, detail="Nieprawidłowy token")


def _constant_time_eq(a: str, b: str) -> bool:
    return hashlib.sha256(a.encode()).digest() == hashlib.sha256(b.encode()).digest()


def _slugify(value: str) -> str:
    slug = SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return slug[:60] or "post"


def _parse_iso_date(value: Optional[str]) -> date:
    """Data z podsumowania na kartę; gdy brak lub w innym formacie — dzisiejsza."""
    try:
        return date.fromisoformat((value or "")[:10])
    except ValueError:
        return date.today()


def _validate_source_url(url: str) -> None:
    """Tylko https + blokada sieci prywatnych (pobieramy URL podany z zewnątrz)."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(status_code=400, detail="Dozwolone tylko adresy https")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="Nieprawidłowy adres URL")

    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        raise HTTPException(status_code=400, detail="Nie można rozwiązać nazwy hosta")

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise HTTPException(status_code=400, detail="Adres wskazuje na sieć prywatną")


def _target_dir(subdir: Optional[str]) -> Path:
    if not subdir:
        return SOCIAL_UPLOAD_DIR
    if not SUBDIR_RE.match(subdir):
        raise HTTPException(status_code=400, detail="Nieprawidłowa nazwa podkatalogu")
    target = SOCIAL_UPLOAD_DIR / subdir
    target.mkdir(parents=True, exist_ok=True)
    return target


def _public_url(relative: str) -> str:
    return f"{settings.API_URL.rstrip('/')}/uploads/social/{relative}"


async def store_image_from_url(source_url: str, slug: str, subdir: Optional[str] = None) -> dict:
    """
    Pobierz grafikę i zapisz na stałe w uploads/social/. Zwraca {url, path, bytes}.

    Wołane z endpointu /media (ręcznie, z n8n) oraz wewnętrznie po generowaniu w kie.ai,
    którego linki wygasają po ~24h.
    """
    _validate_source_url(source_url)
    target_dir = _target_dir(subdir)

    try:
        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
            async with client.stream("GET", source_url) as response:
                if response.status_code != 200:
                    raise HTTPException(status_code=502, detail=f"Źródło zwróciło HTTP {response.status_code}")

                content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
                ext = MIME_TO_EXT.get(content_type)
                if not ext:
                    raise HTTPException(status_code=400, detail=f"Nieobsługiwany typ treści: {content_type or 'brak'}")

                chunks = bytearray()
                async for chunk in response.aiter_bytes(64 * 1024):
                    chunks.extend(chunk)
                    if len(chunks) > MAX_FILE_SIZE:
                        raise HTTPException(status_code=400, detail="Grafika jest za duża (limit 8MB)")
    except httpx.HTTPError as exc:
        logger.warning(f"[social] Nie udało się pobrać {source_url[:100]}: {exc}")
        raise HTTPException(status_code=502, detail="Nie udało się pobrać grafiki ze źródła")

    if not chunks:
        raise HTTPException(status_code=502, detail="Źródło zwróciło pusty plik")

    filename = f"{date.today().isoformat()}_{_slugify(slug)}_{uuid.uuid4().hex[:6]}{ext}"
    (target_dir / filename).write_bytes(bytes(chunks))

    relative = f"{subdir}/{filename}" if subdir else filename
    logger.info(f"[social] Zapisano {relative} ({len(chunks)} B)")
    return {"url": _public_url(relative), "path": f"/uploads/social/{relative}", "bytes": len(chunks)}


def store_image_bytes(content: bytes, slug: str, ext: str = ".jpg", subdir: Optional[str] = None) -> dict:
    """
    Zapisz grafikę wygenerowaną lokalnie (karta dnia) w tym samym miejscu co pobrane z kie.ai.

    Osobna funkcja od store_image_from_url, bo tamta cały wysiłek wkłada w bezpieczne
    pobranie z obcego hosta — tutaj bajty pochodzą z naszego procesu.
    """
    target_dir = _target_dir(subdir)
    filename = f"{date.today().isoformat()}_{_slugify(slug)}_{uuid.uuid4().hex[:6]}{ext}"
    (target_dir / filename).write_bytes(content)

    relative = f"{subdir}/{filename}" if subdir else filename
    logger.info(f"[social] Zapisano kartę {relative} ({len(content)} B)")
    return {"url": _public_url(relative), "path": f"/uploads/social/{relative}", "bytes": len(content)}


async def _latest_summary() -> dict:
    """Najnowsze dzienne podsumowanie — to samo źródło co GET /api/summary/daily."""
    async with async_session() as session:
        result = await session.execute(
            select(DailySummary).order_by(DailySummary.date.desc()).limit(1)
        )
        summary = result.scalar_one_or_none()

    if not summary:
        raise HTTPException(status_code=404, detail="Brak dziennego podsumowania w bazie")

    return {
        "date": summary.date.strftime("%Y-%m-%d"),
        "headline": summary.headline,
        "content": summary.content,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Propozycje postów dla n8n
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/proposal")
async def get_proposal(
    kind: str = Query("text", pattern="^(text|photo)$"),
    x_social_token: Optional[str] = Header(None, alias="X-Social-Token"),
):
    """
    Gotowa propozycja posta — n8n wysyła `message` na Telegram i po akceptacji na FB.

    kind=text   → podsumowanie dnia + karta typograficzna składana lokalnie (szybkie, 0 zł)
    kind=photo  → wywołuje kie.ai i czeka na grafikę (zwykle 20-60 s, limit 180 s),
                  więc node HTTP w n8n musi mieć podniesiony timeout

    Oba rodzaje zwracają `image_url` — n8n publikuje je tym samym wywołaniem /photos.
    Post ze zdjęciem bije w feedzie post z kartą linku, a przy okazji znika problem
    pustej miniatury OG, który obserwowaliśmy na fanpage'u.
    """
    _require_token(x_social_token)
    summary = await _latest_summary()

    if kind == "text":
        proposal = social_content.build_text_post(summary)
        try:
            card = social_card.render_daily_card(
                proposal["headline"],
                day=_parse_iso_date(proposal.get("date")),
            )
        except Exception as exc:
            # Świadomie fail-closed: awaria renderu to brak fontu lub błąd deployu, więc
            # jest trwała, nie chwilowa. Cichy fallback do posta bez grafiki kosztowałby
            # rozgałęzienie w każdym przebiegu n8n, a wada i tak zostałaby niezauważona.
            logger.error(f"[social] Nie udało się złożyć karty dnia: {exc}", exc_info=True)
            raise HTTPException(status_code=502, detail=f"Nie udało się złożyć karty dnia: {exc}")

        stored = store_image_bytes(
            card, slug=social_content.slugify_pl(proposal["headline"] or "karta-dnia")
        )
        proposal["image_url"] = stored["url"]
        return proposal

    proposal = await social_content.build_photo_post(summary)
    try:
        temporary_url = await social_content.generate_image(proposal["prompt"])
    except RuntimeError as exc:
        logger.error(f"[social] kie.ai: {exc}")
        raise HTTPException(status_code=502, detail=f"Nie udało się wygenerować grafiki: {exc}")

    stored = await store_image_from_url(
        temporary_url,
        slug=social_content.slugify_pl(proposal["claim"] or "post"),
    )
    proposal["image_url"] = stored["url"]
    return proposal


@router.get("/campaign/due")
async def get_campaign_due(
    x_social_token: Optional[str] = Header(None, alias="X-Social-Token"),
):
    """
    Pozycja kampanii „Twoja gmina. Na żywo.” przypadająca na teraz (okno 20 min).

    Zwraca `{"due": false}`, gdy nic nie przypada — wtedy workflow w n8n kończy się
    po pierwszym IF-ie. Kalendarz siedzi w services/social_content.py, więc zmiana
    dat nie wymaga dotykania n8n.
    """
    _require_token(x_social_token)
    item = social_content.find_due_campaign_item()

    if not item:
        return {"due": False}

    payload = {
        "due": True,
        "kind": item["kind"],
        "title": item["title"],
        "message": item["message"],
        "note": item.get("note") or "",
        "at": item["at"],
    }
    if item.get("image"):
        payload["image_url"] = _public_url(f"{social_content.CAMPAIGN_IMAGE_DIR}/{item['image']}")
    return payload


# ──────────────────────────────────────────────────────────────────────────────
# Magazyn grafik
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/media")
async def store_media(
    payload: MediaFromUrl,
    x_social_token: Optional[str] = Header(None, alias="X-Social-Token"),
):
    """Skopiuj grafikę z zewnętrznego URL-a do uploads/social/ i zwróć stały adres."""
    _require_token(x_social_token)
    return await store_image_from_url(payload.source_url, payload.slug, payload.subdir)


@router.get("/media")
async def list_media(
    subdir: Optional[str] = Query(None, description="Podkatalog, np. 'kampania'"),
    x_social_token: Optional[str] = Header(None, alias="X-Social-Token"),
):
    """Lista grafik — do sprawdzenia, że n8n widzi to, co ma publikować."""
    _require_token(x_social_token)
    target_dir = _target_dir(subdir)

    items = []
    for path in sorted(target_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            relative = f"{subdir}/{path.name}" if subdir else path.name
            items.append({"name": path.name, "url": _public_url(relative), "bytes": path.stat().st_size})

    return {"count": len(items), "items": items}
