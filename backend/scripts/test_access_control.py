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

    cd backend && python -m scripts.test_access_control
"""
import asyncio
import os
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# Przed importem aplikacji: sprawdzamy konfigurację produkcyjną Swaggera
os.environ["API_DOCS_ENABLED"] = "false"

import httpx
from sqlalchemy import text

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
    ("POST", "/api/newsletter/confirm"): "token z maila (32 B)",
    ("POST", "/api/newsletter/unsubscribe"): "token z maila (32 B)",
    ("PUT", "/api/newsletter/preferences"): "token z maila (32 B)",
    ("POST", "/api/newsletter/webhook/resend"): "podpis Svix",
    ("POST", "/api/payments/webhook"): "weryfikacja transakcji w P24",
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
    voice._get_client = lambda: FakeClient()
    voice._voice_day = None  # wymusza świeży dzień

    audio = {"audio": ("a.webm", b"\x00" * 2000, "audio/webm")}

    async def post_from(ip: str) -> int:
        transport = httpx.ASGITransport(app=app, client=(ip, 5000))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            return (await c.post("/api/voice/transcribe", files=audio)).status_code

    codes = [await post_from("10.0.0.1") for _ in range(voice.VOICE_PER_IP_DAILY)]
    check(f"{voice.VOICE_PER_IP_DAILY} nagrań z jednego IP przechodzi", set(codes) == {200}, set(codes))
    check("kolejne z tego IP → 429", await post_from("10.0.0.1") == 429)
    check("inne IP ma własny licznik", await post_from("10.0.0.2") == 200)
    transport = httpx.ASGITransport(app=app, client=("10.0.0.3", 5000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/voice/transcribe", files={"audio": ("a.webm", b"\x00" * 10, "audio/webm")})
    check("za krótkie nagranie → 400, bez zjadania limitu",
          r.status_code == 400 and voice._voice_per_ip[voice._hash_ip("10.0.0.3")] == 0, r.status_code)
    voice._voice_total = voice.VOICE_GLOBAL_DAILY
    check("dzienny sufit globalny → 429", await post_from("10.0.0.4") == 429)
    voice._voice_day = None


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


async def cleanup() -> None:
    async with async_session() as session:
        await session.execute(text(
            "DELETE FROM chat_messages WHERE conversation_id IN "
            "(SELECT id FROM conversations WHERE title = :t)"), {"t": CONV_TITLE})
        await session.execute(text("DELETE FROM conversations WHERE title = :t"), {"t": CONV_TITLE})
        await session.execute(text("DELETE FROM document_embeddings WHERE source_type = :s"), {"s": EMB_SOURCE})
        await session.execute(text("DELETE FROM users WHERE email LIKE :d"), {"d": f"%{TEST_DOMAIN}"})
        await session.commit()


async def main() -> int:
    await cleanup()
    from src.api.main import app
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await section_history(client)
            await section_push(client)
            await section_weather(client)
            await section_voice(app)
            await section_embedding()
            await section_docs(client)
            section_route_guard(app)
    finally:
        await cleanup()
    failed = results.count(False)
    print(f"\n{'✅' if not failed else '❌'} {len(results) - failed}/{len(results)} sprawdzeń")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
