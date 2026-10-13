"""
Kontrola dostępu i limity tras publicznych — strażnik po audycie 11.10.2026.

Audyt znalazł klasę błędów, nie pojedynczy błąd: trasa sama pilnowała dostępu
albo nie pilnowała wcale, a brak kontroli nie był widoczny w żadnym teście.
- F-001  anonim czytał historię czatu WSZYSTKICH (`None == None` w kontroli własności)
- F-024  klient planu „Firma” rozsyłał dowolny push do wszystkich subskrybentów
- H-004  anonimowe ręczne odświeżanie pogody i powietrza (limity OpenWeather/Airly)
- F-025  Whisper bez żadnego limitu
- H-001  metadane embeddingu wklejane w SQL dollar-quotingiem
- Swagger publiczny na produkcji — spis tras dla każdego

Sekcja 7 to strażnik: KAŻDA trasa POST/PUT/PATCH/DELETE ma zależność logowania
albo stoi na jawnej liście `PUBLIC_WRITE_ROUTES` z powodem. Nowa trasa bez
jednego i drugiego czerwieni test — decyzja o publiczności ma być świadoma.

Bez modelu i bez wysyłek (push i Whisper podmienione). Baza lokalna: konta
`@test-dostep.rybnolive.pl` i rozmowy z tytułem `QA-DOSTEP` są kasowane na końcu.
`--no-db` (CI w GitHub Actions) uruchamia wyłącznie sekcje bez bazy: Whisper,
Swagger/compose i strażnika tras — schematu produkcji nie da się dziś zbudować
z modeli (ręczne migracje, audyt F-034), więc bazy w CI nie ma.

    cd backend && python -m scripts.test_access_control [--no-db]
"""
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# Przed importem aplikacji: sprawdzamy konfigurację produkcyjną Swaggera
os.environ["API_DOCS_ENABLED"] = "false"

import httpx
from sqlalchemy import text
from sqlmodel import select

from src.auth.jwt import create_access_token
from src.database.connection import async_session
from src.database.schema import User, UserTier
from src.database.vectors import ChatMessage, Conversation

TEST_DOMAIN = "@test-dostep.rybnolive.pl"
CONV_TITLE = "QA-DOSTEP"
EMB_SOURCE = "qa_dostep"
results: list[bool] = []

# Trasy zapisujące BEZ zależności logowania — każda z powodem.
PUBLIC_WRITE_ROUTES = {
    ("POST", "/api/auth/register"): "zakładanie konta",
    ("POST", "/api/auth/login"): "logowanie",
    ("POST", "/api/auth/logout"): "kasuje własne ciasteczka",
    ("POST", "/api/auth/refresh"): "refresh token w treści/ciasteczku",
    ("POST", "/api/auth/forgot-password"): "reset hasła — limit IP i adresu, odpowiedź nie zdradza konta",
    ("POST", "/api/auth/reset-password"): "token resetu z maila (1 h, jednorazowy)",
    ("POST", "/api/newsletter/confirm"): "token z maila (32 B)",
    ("POST", "/api/newsletter/unsubscribe"): "token z maila (32 B)",
    ("PUT", "/api/newsletter/preferences"): "token z maila (32 B)",
    ("POST", "/api/newsletter/webhook/resend"): "podpis Svix",
    ("POST", "/api/payments/webhook"): "weryfikacja transakcji w P24",
    ("POST", "/api/csp-report"): "raport CSP wysyłany przez przeglądarkę bez tokenu — limit IP i globalny, "
                                 "zapis zagregowany bez IP/UA i bez parametrów adresu, zawsze 204",
    ("POST", "/api/cinema/ingest"): "Bearer z konfiguracji (n8n)",
    ("POST", "/api/social/media"): "X-Social-Token (n8n)",
    ("POST", "/api/council/review/{token}"): "jednorazowy token akceptacji",
    ("DELETE", "/api/push/subscribe"): "wypis po endpoincie, który zna tylko przeglądarka",
    ("POST", "/api/business/{business_id}/view"): "licznik wyświetleń wizytówki",
    ("POST", "/api/voice/transcribe"): "mikrofon bez konta — limit per IP w kodzie",
}
AUTH_DEPENDENCIES = {
    "get_current_user", "get_current_active_user", "get_admin_user",
    "get_business_user", "get_optional_user",
}


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + str(detail)) if detail else ''}")
    results.append(bool(ok))
    return ok


async def make_user(email: str, tier: str = UserTier.FREE.value, is_admin: bool = False) -> User:
    async with async_session() as session:
        user = User(email=email, password_hash="x" * 20, full_name="Test Dostępu",
                    tier=tier, is_admin=is_admin)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


def auth(user: User) -> dict:
    token = create_access_token({"sub": user.email, "user_id": user.id, "tier": user.tier})
    return {"Authorization": f"Bearer {token}"}


async def make_conversation(user_id) -> int:
    async with async_session() as session:
        conv = Conversation(user_id=user_id, title=CONV_TITLE)
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        session.add(ChatMessage(conversation_id=conv.id, role="user", content="pytanie testowe"))
        await session.commit()
        return conv.id


async def section_history(client: httpx.AsyncClient) -> None:
    print("\n1️⃣  Historia czatu (F-001)")
    a = await make_user(f"a{TEST_DOMAIN}")
    b = await make_user(f"b{TEST_DOMAIN}")
    anon_conv = await make_conversation(None)
    a_conv = await make_conversation(a.id)
    b_conv = await make_conversation(b.id)

    r = await client.get("/api/chat/history")
    check("anonim: lista pusta", r.status_code == 200 and r.json() == {"conversations": []}, r.text[:120])
    r = await client.get(f"/api/chat/history?conversation_id={anon_conv}")
    check("anonim: rozmowa anonimowa → 404", r.status_code == 404, r.status_code)
    r = await client.get(f"/api/chat/history?conversation_id={a_conv}")
    check("anonim: rozmowa konta → 404", r.status_code == 404, r.status_code)

    r = await client.get("/api/chat/history?limit=50", headers=auth(a))
    ids = {c["id"] for c in r.json().get("conversations", [])}
    check("A widzi swoją rozmowę", a_conv in ids, ids)
    check("A nie widzi rozmowy B ani anonimowej", not ids & {b_conv, anon_conv}, ids)
    r = await client.get(f"/api/chat/history?conversation_id={a_conv}", headers=auth(a))
    check("A czyta swoją rozmowę", r.status_code == 200 and len(r.json()["messages"]) == 1, r.status_code)
    r = await client.get(f"/api/chat/history?conversation_id={b_conv}", headers=auth(a))
    check("A nie czyta rozmowy B (404)", r.status_code == 404, r.status_code)
    r = await client.get(f"/api/chat/history?conversation_id={anon_conv}", headers=auth(a))
    check("A nie czyta rozmowy anonimowej (404)", r.status_code == 404, r.status_code)


async def section_push(client: httpx.AsyncClient) -> None:
    print("\n2️⃣  Push „test” (F-024)")
    from src.services.push_service import push_service
    calls: list[str] = []

    async def fake_send_push(**kw):
        calls.append(kw["endpoint"])
        return True

    async def fake_category(**kw):
        calls.append("BROADCAST")
        return 999
    push_service.send_push = fake_send_push
    push_service.send_to_category = fake_category

    business = await make_user(f"firma{TEST_DOMAIN}", tier="business")
    admin = await make_user(f"admin{TEST_DOMAIN}", is_admin=True)
    payload = {"endpoint": "https://push.example/qa-dostep", "title": "x", "body": "y"}

    r = await client.post("/api/push/test", json=payload)
    check("anonim → 401", r.status_code == 401, r.status_code)
    r = await client.post("/api/push/test", json=payload, headers=auth(business))
    check("plan business → 403", r.status_code == 403, r.status_code)
    r = await client.post("/api/push/test", json={"title": "x"}, headers=auth(admin))
    check("admin bez endpointu → 422", r.status_code == 422, r.status_code)
    r = await client.post("/api/push/test", json=payload, headers=auth(admin))
    check("admin z nieznaną subskrypcją → 404", r.status_code == 404, r.status_code)
    check("żadnej wysyłki do wszystkich", "BROADCAST" not in calls, calls)
    r = await client.get("/api/push/subscriptions/count", headers=auth(business))
    check("liczba subskrypcji: business → 403", r.status_code == 403, r.status_code)


async def section_weather(client: httpx.AsyncClient) -> None:
    print("\n3️⃣  Ręczne odświeżenie pogody i powietrza (H-004)")
    user = await make_user(f"mieszkaniec{TEST_DOMAIN}")
    for path in ("/api/weather/update", "/api/weather/air-quality/update"):
        r = await client.post(path)
        check(f"{path}: anonim → 401", r.status_code == 401, r.status_code)
        r = await client.post(path, headers=auth(user))
        check(f"{path}: zwykłe konto → 403", r.status_code == 403, r.status_code)


async def section_voice(app) -> None:
    print("\n4️⃣  Whisper: limit per IP i sufit dzienny (F-025)")
    from src.api.endpoints import voice

    class FakeTranscriptions:
        async def create(self, **kw):
            return "dzień dobry"

    class FakeClient:
        audio = type("A", (), {"transcriptions": FakeTranscriptions()})()
    from src.api.endpoints.chat import _hash_ip
    voice._get_client = lambda: FakeClient()
    limit = voice.VOICE_LIMIT
    limit.reset()  # wymusza świeży dzień

    audio = {"audio": ("a.webm", b"\x00" * 2000, "audio/webm")}

    async def post_from(ip: str) -> int:
        transport = httpx.ASGITransport(app=app, client=(ip, 5000))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            return (await c.post("/api/voice/transcribe", files=audio)).status_code

    codes = [await post_from("10.0.0.1") for _ in range(limit.per_key)]
    check(f"{limit.per_key} nagrań z jednego IP przechodzi", set(codes) == {200}, set(codes))
    check("kolejne z tego IP → 429", await post_from("10.0.0.1") == 429)
    check("inne IP ma własny licznik", await post_from("10.0.0.2") == 200)
    transport = httpx.ASGITransport(app=app, client=("10.0.0.3", 5000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/voice/transcribe", files={"audio": ("a.webm", b"\x00" * 10, "audio/webm")})
    check("za krótkie nagranie → 400, bez zjadania limitu",
          r.status_code == 400 and limit.used(_hash_ip("10.0.0.3")) == 0, r.status_code)
    limit._total = limit.total
    check("dzienny sufit globalny → 429", await post_from("10.0.0.4") == 429)
    limit.reset()


async def section_embedding() -> None:
    print("\n5️⃣  Metadane embeddingu jako parametr (H-001)")
    from src.ai.embeddings import EmbeddingService
    evil = "Tytuł $meta$ ); DROP TABLE qa_nie_istnieje; -- ' \" \\"
    async with async_session() as session:
        await EmbeddingService().store_embedding(
            session, EMB_SOURCE, 1, 0, "fragment", [0.0] * 1536, {"title": evil})
        await session.commit()
        row = (await session.execute(text(
            "SELECT metadata->>'title' FROM document_embeddings WHERE source_type = :s"),
            {"s": EMB_SOURCE})).scalar_one_or_none()
    check("tytuł z `$meta$` zapisany dosłownie", row == evil, row)


async def section_docs(client: httpx.AsyncClient) -> None:
    print("\n6️⃣  Swagger na produkcji + konfiguracja compose")
    for path in ("/docs", "/redoc", "/openapi.json"):
        r = await client.get(path)
        check(f"{path} wyłączony przy API_DOCS_ENABLED=false", r.status_code == 404, r.status_code)
    compose = (backend_path.parent / "docker-compose.prod.yml").read_text()
    check("compose: uvicorn z --forwarded-allow-ips (F-026)", "--forwarded-allow-ips" in compose)
    check("compose: API_DOCS_ENABLED=false", 'API_DOCS_ENABLED: "false"' in compose)


def section_route_guard(app) -> None:
    print("\n7️⃣  Strażnik: każda trasa zapisująca ma jawną politykę dostępu")
    from fastapi.routing import APIRoute

    def dep_names(dependant, acc):
        for d in dependant.dependencies:
            if d.call is not None:
                acc.add(getattr(d.call, "__name__", ""))
            dep_names(d, acc)
        return acc

    seen = set()
    unguarded = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods & {"POST", "PUT", "PATCH", "DELETE"}:
            key = (method, route.path)
            seen.add(key)
            if key in PUBLIC_WRITE_ROUTES:
                continue
            if not dep_names(route.dependant, set()) & AUTH_DEPENDENCIES:
                unguarded.append(f"{method} {route.path}")
    check("brak tras zapisujących bez polityki", not unguarded, unguarded)
    stale = [f"{m} {p}" for (m, p) in PUBLIC_WRITE_ROUTES if (m, p) not in seen]
    check("lista wyjątków bez martwych wpisów", not stale, stale)


async def section_newsletter(client: httpx.AsyncClient) -> None:
    print("\n8️⃣  Ponowny zapis na newsletter wymaga potwierdzenia (F-027)")
    from src.database.schema import NewsletterSubscriber
    from src.newsletter.email_service import EmailService
    sent: list[str] = []

    async def fake_confirm(self, to_email, confirmation_token):
        sent.append(to_email)
        return {"status": "sent"}
    EmailService.send_confirmation_email = fake_confirm

    gone, active = f"wypisany{TEST_DOMAIN}", f"aktywny{TEST_DOMAIN}"
    async with async_session() as session:
        session.add(NewsletterSubscriber(
            email=gone, frequency="weekly", status="unsubscribed", unsubscribe_token="qa-dostep-1",
            confirmed_at=datetime.utcnow(), unsubscribed_at=datetime.utcnow()))
        session.add(NewsletterSubscriber(
            email=active, frequency="weekly", status="active", unsubscribe_token="qa-dostep-2",
            confirmed_at=datetime.utcnow()))
        await session.commit()

    async def row(email):
        async with async_session() as session:
            return (await session.execute(
                select(NewsletterSubscriber).where(NewsletterSubscriber.email == email))).scalar_one()

    r1 = await client.post("/api/newsletter/subscribe", json={"email": gone, "frequency": "weekly"})
    sub = await row(gone)
    check("wypisany: confirmed_at = NULL do kliknięcia w link",
          sub.confirmed_at is None and sub.confirmation_token, sub.confirmed_at)
    check("wypisany: poszedł mail z potwierdzeniem", gone in sent, sent)
    r2 = await client.post("/api/newsletter/subscribe", json={"email": active, "frequency": "weekly"})
    check("aktywny: bez maila (formularz nie zasypie cudzej skrzynki)", active not in sent, sent)
    r3 = await client.post("/api/newsletter/subscribe", json={"email": f"nowy{TEST_DOMAIN}", "frequency": "weekly"})
    check("ta sama odpowiedź dla wypisanego, aktywnego i nowego (bez zgadywania listy)",
          r1.status_code == r2.status_code == r3.status_code == 201 and r1.json() == r2.json() == r3.json(),
          [r1.status_code, r2.status_code, r3.status_code])
    sent.clear()
    r = await client.post("/api/newsletter/subscribe", json={"email": gone, "frequency": "daily"})
    check("daily bez Premium → 403, zanim ruszy istniejący wpis", r.status_code == 403 and not sent, r.status_code)


def tiny_jpeg_with_gps() -> bytes:
    import io
    from PIL import Image
    img = Image.new("RGB", (64, 48), "white")
    exif = Image.Exif()
    exif[0x8825] = {1: "N", 2: (53.0, 23.0, 0.0), 3: "E", 4: (19.0, 55.0, 0.0)}  # GPSInfo
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


async def section_reports(app) -> None:
    print("\n9️⃣  Zgłoszenia 24: limit, EXIF, HTML w mailu (F-010, F-030)")
    import io
    from PIL import Image
    from src.ai import report_analyzer
    from src.api.endpoints import reports
    from src.api.endpoints.chat import _hash_ip
    from src.newsletter.email_service import EmailService

    async def fake_analyze(**kw):
        return {"category": "other", "summary": "qa", "severity": "low", "is_spam": False,
                "spam_reason": None, "detected_objects": [], "condition": "", "suggested_title": ""}
    report_analyzer.analyze_report = fake_analyze

    async def fake_geocode(address, location_name=None):
        return None, None
    reports.geocode_address = fake_geocode
    mails: list[str] = []

    async def capture(self, to_email, subject, html_content, **kw):
        mails.append(html_content)
        return {"status": "sent"}
    EmailService.send_email = capture
    reports.REPORT_LIMIT.reset()
    from src.config import settings
    settings.ADMIN_ALERT_EMAIL = settings.ADMIN_ALERT_EMAIL or f"redakcja{TEST_DOMAIN}"

    gps = tiny_jpeg_with_gps()
    check("plik testowy ma GPS w EXIF", 0x8825 in Image.open(io.BytesIO(gps)).getexif())

    async def post(ip, title="QA-DOSTEP zgłoszenie", with_image=False):
        transport = httpx.ASGITransport(app=app, client=(ip, 5000))
        files = {"image": ("x.jpg", gps, "image/jpeg")} if with_image else None
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.post("/api/reports", data={"title": title, "description": "<b>opis</b>"}, files=files)

    r = await post("10.1.0.1", title="QA-DOSTEP <script>x</script>", with_image=True)
    check("zgłoszenie ze zdjęciem przyjęte", r.status_code == 201, r.status_code)
    url = r.json().get("image_url") if r.status_code == 201 else None
    saved = reports.UPLOAD_DIR / url.rsplit("/", 1)[-1] if url else None
    if saved and saved.exists():
        check("zapisane zdjęcie BEZ GPS/EXIF", 0x8825 not in Image.open(saved).getexif())
        saved.unlink()
    else:
        check("zapisane zdjęcie istnieje", False, url)
    html_mail = mails[-1] if mails else ""
    check("mail do redakcji: tytuł escapowany", "&lt;script&gt;" in html_mail and "<script>" not in html_mail)

    for _ in range(reports.REPORT_LIMIT.per_key - 1):
        await post("10.1.0.1")
    r = await post("10.1.0.1")
    check(f"{reports.REPORT_LIMIT.per_key + 1}. zgłoszenie z tego IP → 429", r.status_code == 429, r.status_code)
    r = await post("10.1.0.2")
    check("inne IP zgłasza dalej", r.status_code == 201, r.status_code)
    transport = httpx.ASGITransport(app=app, client=("10.1.0.3", 5000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/reports", data={"title": "QA-DOSTEP", "description": "x"},
                         files={"image": ("x.jpg", b"to nie jest obraz", "image/jpeg")})
    check("plik, który nie jest zdjęciem → 400 bez zjadania limitu",
          r.status_code == 400 and reports.REPORT_LIMIT.used(_hash_ip("10.1.0.3")) == 0, r.status_code)
    reports.REPORT_LIMIT.reset()


def section_static() -> None:
    print("\n🔟 Logo i Caddy — sprawdzenia bez bazy (F-029, F-026, F-030)")
    from src.api.endpoints.business import ProfileUpdateRequest
    check("edycja wizytówki nie przyjmuje `logo_url`", "logo_url" not in ProfileUpdateRequest.model_fields)
    caddy = (backend_path.parent / "Caddyfile").read_text()
    check("Caddyfile bez `trusted_proxies` (Caddy nadpisuje podrobiony X-Forwarded-For)",
          "trusted_proxies" not in caddy)
    check("HSTS w obu blokach header", caddy.count("Strict-Transport-Security") == 2)


async def cleanup() -> None:
    async with async_session() as session:
        await session.execute(text(
            "DELETE FROM chat_messages WHERE conversation_id IN "
            "(SELECT id FROM conversations WHERE title = :t)"), {"t": CONV_TITLE})
        await session.execute(text("DELETE FROM conversations WHERE title = :t"), {"t": CONV_TITLE})
        await session.execute(text("DELETE FROM document_embeddings WHERE source_type = :s"), {"s": EMB_SOURCE})
        await session.execute(text("DELETE FROM newsletter_subscribers WHERE email LIKE :d"), {"d": f"%{TEST_DOMAIN}"})
        await session.execute(text("DELETE FROM reports WHERE title LIKE 'QA-DOSTEP%'"))
        await session.execute(text("DELETE FROM users WHERE email LIKE :d"), {"d": f"%{TEST_DOMAIN}"})
        await session.commit()


async def main() -> int:
    with_db = "--no-db" not in sys.argv
    if with_db:
        await cleanup()
    from src.api.main import app
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            if with_db:
                await section_history(client)
                await section_push(client)
                await section_weather(client)
            await section_voice(app)
            if with_db:
                await section_embedding()
            await section_docs(client)
            section_route_guard(app)
            section_static()
            if with_db:
                await section_newsletter(client)
                await section_reports(app)
    finally:
        if with_db:
            await cleanup()
    failed = results.count(False)
    print(f"\n{'✅' if not failed else '❌'} {len(results) - failed}/{len(results)} sprawdzeń")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
