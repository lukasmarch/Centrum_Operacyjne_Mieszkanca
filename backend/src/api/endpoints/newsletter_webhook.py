"""
Webhook Resend — jedyne źródło `newsletter_logs.opened_at` i `clicked_at`.

Skąd potrzeba: obie kolumny istnieją w schemacie od początku projektu i **nic
w całym repozytorium do nich nie pisało**. Stan na 30.08.2026: 91 wysłanych
newsletterów, 0 zapisanych otwarć. To nie był wynik — to był brak mechanizmu.
Bez tego nie wiadomo, czy Premium w ogóle dostaje to, za co zapłacił.

Dopasowanie idzie po `newsletter_logs.provider_message_id`, czyli identyfikatorze,
który Resend zwraca przy wysyłce (`email_service.send_email` już go oddaje w polu
`id`, tylko do 30.08 go wyrzucaliśmy).

Podpis liczymy sami, bez paczki `svix`. Powód jest twardy: 189 z 202 zależności
projektu nie ma przypiętej wersji, więc dołożenie pakietu oznacza świeży resolve
przy najbliższej przebudowie obrazu — a to już raz położyło produkcję na 20 minut.
Algorytm jest krótki i stabilny (Svix nie zmienił go od lat).

Odpowiedź to ZAWSZE 200. Resend, tak jak Przelewy24, ponawia webhooka przy każdym
innym kodzie — a nam nie zależy, żeby ponawiał zdarzenie, którego i tak nie umiemy
przypisać. Powody odrzucenia idą do logu.

Konfiguracja (po wdrożeniu, ręcznie):
  1. panel Resend → Webhooks → adres `https://api.rybnolive.pl/api/newsletter/webhook/resend`
  2. zdarzenia: `email.opened`, `email.clicked`
  3. sekret `whsec_…` → `RESEND_WEBHOOK_SECRET` w `/opt/centrum/backend/.env.production`
  4. `docker compose -f docker-compose.prod.yml up -d --force-recreate backend`
     (samo `up -d` NIE przeładowuje zmiennych środowiskowych)
"""
import base64
import hashlib
import hmac
import logging
import time
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlmodel import select

from src.config import settings
from src.database.connection import async_session
from src.database.schema import NewsletterLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/newsletter", tags=["newsletter"])

# Svix odrzuca ładunki starsze niż 5 minut — zabezpieczenie przed powtórzeniem
# przechwyconego żądania.
TOLERANCE_S = 5 * 60


def _verify(secret: str, svix_id: str, svix_ts: str, svix_sig: str, body: bytes) -> bool:
    """
    Weryfikacja podpisu Svix (tego używa Resend).

    Podpisywana treść to `{id}.{timestamp}.{body}`, klucz to część sekretu po
    `whsec_`, zdekodowana z base64. Nagłówek `svix-signature` niesie listę
    podpisów rozdzieloną spacjami, każdy w formie `v1,<base64>` — przy rotacji
    sekretu przez chwilę ważne są dwa naraz, więc sprawdzamy wszystkie.
    """
    if not secret or not svix_id or not svix_ts or not svix_sig:
        return False

    try:
        ts = int(svix_ts)
    except ValueError:
        return False
    if abs(time.time() - ts) > TOLERANCE_S:
        return False

    try:
        key = base64.b64decode(secret.split("_", 1)[1] if secret.startswith("whsec_") else secret)
    except Exception:
        return False

    signed = b"%s.%s." % (svix_id.encode(), svix_ts.encode()) + body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()

    for part in svix_sig.split(" "):
        version, _, value = part.partition(",")
        if version == "v1" and hmac.compare_digest(value, expected):
            return True
    return False


@router.post("/webhook/resend")
async def resend_webhook(request: Request):
    """Odbierz zdarzenie o otwarciu lub kliknięciu w newsletterze."""
    body = await request.body()

    if not _verify(
        settings.RESEND_WEBHOOK_SECRET,
        request.headers.get("svix-id", ""),
        request.headers.get("svix-timestamp", ""),
        request.headers.get("svix-signature", ""),
        body,
    ):
        logger.warning("Webhook Resend: zły podpis albo brak RESEND_WEBHOOK_SECRET")
        return JSONResponse({"status": "ignored"}, status_code=200)

    try:
        payload = await request.json()
    except Exception:
        logger.warning("Webhook Resend: ładunek nie jest JSON-em")
        return JSONResponse({"status": "ignored"}, status_code=200)

    kind = payload.get("type")
    message_id = (payload.get("data") or {}).get("email_id")

    if kind not in ("email.opened", "email.clicked") or not message_id:
        return JSONResponse({"status": "ignored"}, status_code=200)

    try:
        async with async_session() as session:
            result = await session.execute(
                select(NewsletterLog).where(NewsletterLog.provider_message_id == message_id)
            )
            log = result.scalars().first()
            if not log:
                # Zwykle: mail spoza newslettera (powitalny, potwierdzenie płatności),
                # dla którego nie zakładamy wiersza w `newsletter_logs`.
                logger.info("Webhook Resend: brak wpisu dla %s (%s)", message_id, kind)
                return JSONResponse({"status": "ignored"}, status_code=200)

            now = datetime.utcnow()
            # Pierwsze otwarcie, nie ostatnie — inaczej „kiedy przeczytał" zamienia
            # się w „kiedy ostatni raz zajrzał", a to inne pytanie.
            if kind == "email.opened" and log.opened_at is None:
                log.opened_at = now
                if log.status == "sent":
                    log.status = "opened"
            elif kind == "email.clicked":
                if log.clicked_at is None:
                    log.clicked_at = now
                # Klik bez zarejestrowanego otwarcia zdarza się często: część
                # klientów pocztowych blokuje obrazek śledzący, a link klika.
                if log.opened_at is None:
                    log.opened_at = now
                log.status = "clicked"

            session.add(log)
            await session.commit()
    except Exception as exc:
        logger.error("Webhook Resend: nie zapisano %s dla %s: %s", kind, message_id, exc)

    return JSONResponse({"status": "ok"}, status_code=200)
