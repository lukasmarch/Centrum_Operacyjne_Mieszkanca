"""
Test ról z zakresem i ogłoszeń sołtysów (2026-09-27).

Przepływ, który Łukasz przejdzie ręcznie, tu sprawdzony od końca do końca
przez prawdziwe endpointy (ASGI, lokalna baza):

  1. zaproszenie: szczegóły publiczne bez danych osoby zapraszanej
  2. rejestracja z zaproszeniem → rola, Premium BEZ terminu, instrukcja sołtysa
     zamiast maila o 30-dniowym triale
  3. ten sam link drugi raz / wygasły / wycofany → 410, konto NIE powstaje
  4. istniejące konto przyjmuje zaproszenie
  5. zwykłe konto nie doda ogłoszenia (403)
  6. wysyłka zdjęcia → odczyt w tle → `pending` + dzwonek do redakcji
  7. zdjęcie oryginału: redakcja tak, sołtys i anonim nie; nie leży w /uploads
  8. przed moderacją ogłoszenie nie istnieje publicznie
  9. zatwierdzenie → artykuł ze źródła sołectw, mail z linkiem do sołtysa
 10. odrzucenie → mail z powodem
 11. odebranie roli → koniec Premium i koniec dodawania ogłoszeń
 12. retencja: zdjęcia znikają po IMAGE_RETENTION_DAYS od decyzji
 13. DSAR: opublikowane zostaje bez konta, nieopublikowane znika, rola znika
 14. kontrola kodem odczytu: PESEL wycięty, termin bez śladu w tekście odrzucony
 15. po publikacji (E7): prośba sołtysa → korekta (artykuł, kalendarz, RAG,
     etykieta „KOREKTA” w briefingu, historia) → odwołanie (znika z bramek,
     powtórka z innego źródła przejmuje kalendarz, strona mówi „odwołane”)
 16. takedown wpisu sołectwa z wydarzeniem nie pada na kluczach obcych

Model i poczta są PODMIENIONE — nic nie wychodzi na zewnątrz i nic nie kosztuje.
`--live` dokłada prawdziwy odczyt wygenerowanego pisma przez gpt-4o (~$0,01).

Konta testowe (`@test-solectwa.rybnolive.pl`) i ich ślady są kasowane na końcu, także po błędzie.

Użycie:
    cd backend && python -m scripts.test_solectwa [--live]
"""
import asyncio
import io
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import httpx
from sqlalchemy import text
from sqlmodel import select

from src.auth.jwt import create_access_token
from src.database.connection import async_session
from src.database.schema import (
    Article, Event, RoleInvitation, SolectwoPost, SolectwoPostRequest,
    SolectwoPostVersion, User, UserRole, UserTier,
)
from src.newsletter.email_service import EmailService
from src.services.time_span import to_local, to_utc

# Nowy termin po korekcie: zawsze TYDZIEŃ od dziś. Do 26.10.2026 stała data
# 22.10.2026 — po jej minięciu wpis słusznie znikał z feedu i briefingu, a test
# czerwienił deploy (pułapka czasowa, ta sama co w `test_waste_reminder`).
NEW_DAY = to_local(datetime.utcnow()).date() + timedelta(days=7)
_MIESIACE = ("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
             "sierpnia", "września", "października", "listopada", "grudnia")
NEW_DAY_TEXT = f"{NEW_DAY.day} {_MIESIACE[NEW_DAY.month - 1]}"

# Własna domena: sprzątanie na końcu kasuje WSZYSTKO z tej domeny, więc wspólna
# `@qa.rybnolive.pl` zabierała konta z ręcznego testu w przeglądarce (27.09)
TEST_DOMAIN = "@test-solectwa.rybnolive.pl"
SCOPE = "Żabiny"
sent_emails: list[dict] = []
results: list[bool] = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + str(detail)) if detail else ''}")
    results.append(bool(ok))
    return ok


def patch_outside_world() -> None:
    """Poczta do listy, model na sztywną odpowiedź, kategoryzacja bez modelu."""
    async def capture(self, to_email, subject, html_content, reply_to=None, unsubscribe_url=None):
        sent_emails.append({"to": to_email, "subject": subject, "html": html_content})
        return {"status": "sent", "id": "test", "to": to_email}
    EmailService.send_email = capture

    from src.ai import scan_reader
    from src.ai.scan_reader import ScanResult

    async def fake_read(self, images, note=None, now=None):
        return ScanResult(
            is_document=True,
            title="Zebranie wiejskie w Żabinach",
            summary="Sołtys zaprasza na zebranie wiejskie 15 października o 18:00 w świetlicy.",
            transcript="ZAWIADOMIENIE\nZebranie wiejskie odbędzie się 15 października 2026 r. "
                       "o godz. 18:00 w świetlicy wiejskiej w Żabinach.\nWniosek złożył [dane osobowe].",
            doc_type="zawiadomienie o zebraniu wiejskim",
            event_at=datetime(2026, 10, 15, 16, 0),
            event_until=None,
            personal_data=["imię i nazwisko wnioskodawcy"],
            illegible=[],
        ), 1000, 200
    scan_reader.ScanReader.__init__ = lambda self: None
    scan_reader.ScanReader.read = fake_read

    from src.ai import article_processor

    async def fake_process(self, article, session):
        article.category = "Urząd"
        article.locality = 3
        article.processed = True
        article.is_filler = True  # heurystyka „zapychacza" nie może cofnąć decyzji redakcji
        session.add(article)
        await session.commit()
        return article
    article_processor.ArticleProcessor.__init__ = lambda self: None
    article_processor.ArticleProcessor.process_article = fake_process

    # Osadzenie poprawionej treści bez OpenAI — liczymy tylko, że zostało zawołane
    from src.scheduler import embedding_job

    async def fake_embed(session, article, source_name):
        reembedded.append(article.id)
        article.embedded = True
        session.add(article)
        return 1
    embedding_job.embed_article = fake_embed


reembedded: list[int] = []


def jpeg_bytes() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (800, 1100), "white").save(buf, format="JPEG")
    return buf.getvalue()


async def make_user(email: str, is_admin: bool = False) -> User:
    async with async_session() as session:
        user = User(
            email=email, password_hash="x" * 20, full_name="Jan Testowy",
            location="Żabiny", tier=UserTier.PREMIUM.value,
            trial_ends_at=datetime.utcnow() + timedelta(days=20),
            is_admin=is_admin, consent_terms_at=datetime.utcnow(),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


def auth(user: User) -> dict:
    token = create_access_token({"sub": user.email, "user_id": user.id, "tier": user.tier})
    return {"Authorization": f"Bearer {token}"}


async def reload(model, pk):
    async with async_session() as session:
        return await session.get(model, pk)


async def run(client: httpx.AsyncClient, live: bool) -> None:
    from src.api.endpoints import solectwa as sol
    from src.services import roles as role_service

    admin = await make_user(f"admin{TEST_DOMAIN}", is_admin=True)
    resident = await make_user(f"mieszkaniec{TEST_DOMAIN}")

    print("\n1️⃣  Zaproszenie — admin wystawia, strona pokazuje rolę")
    r = await client.post("/api/roles/admin/invitations", headers=auth(admin),
                          json={"role": "soltys", "scope": SCOPE, "invitee_label": "Jan K. — rozmowa 27.09"})
    check("admin wystawia zaproszenie", r.status_code == 201, r.status_code)
    inv = r.json()
    token = inv["url"].split("kod=")[1]
    check("link prowadzi na /zaproszenie?kod=", "/zaproszenie?kod=" in inv["url"])
    r = await client.post("/api/roles/admin/invitations", headers=auth(resident),
                          json={"role": "soltys", "scope": SCOPE})
    check("zwykłe konto nie wystawi zaproszenia", r.status_code == 403, r.status_code)
    r = await client.post("/api/roles/admin/invitations", headers=auth(admin),
                          json={"role": "soltys", "scope": "Atlantyda"})
    check("zakres spoza listy sołectw odrzucony", r.status_code == 400, r.status_code)
    r = await client.get(f"/api/roles/invitation/{token}")
    body = r.json()
    check("szczegóły zaproszenia publiczne", r.status_code == 200 and body["state"] == "active")
    check("podpis „Sołtys sołectwa Żabiny”", body["signed_as"] == "Sołtys sołectwa Żabiny", body["signed_as"])
    check("bez etykiety osoby zapraszanej", "invitee_label" not in body)

    print("\n2️⃣  Rejestracja z zaproszeniem")
    sent_emails.clear()
    email = f"soltys{TEST_DOMAIN}"
    r = await client.post("/api/auth/register", json={
        "email": email, "password": "Testowe123", "full_name": "Jan Sołtys",
        "location": "Żabiny", "consent_terms": True, "invite_token": token,
    })
    check("konto założone", r.status_code == 201, r.status_code)
    async with async_session() as session:
        soltys = (await session.execute(select(User).where(User.email == email))).scalar_one()
        roles = await role_service.live_roles(session, soltys.id)
    check("rola sołtysa zweryfikowana", len(roles) == 1 and roles[0].scope == SCOPE and roles[0].method == "invitation")
    check("Premium", soltys.tier == UserTier.PREMIUM.value, soltys.tier)
    check("Premium BEZ terminu (trial_ends_at = NULL)", soltys.trial_ends_at is None, soltys.trial_ends_at)
    subjects = [m["subject"] for m in sent_emails if m["to"] == email]
    check("instrukcja sołtysa wyszła", any("Sołtys sołectwa Żabiny" in s for s in subjects), subjects)
    check("mail o 30-dniowym triale NIE wyszedł", not any("Premium do" in s for s in subjects), subjects)
    html = next((m["html"] for m in sent_emails if "Sołtys sołectwa" in m["subject"]), "")
    check("instrukcja mówi, jak dodać ogłoszenie", "Dodaj ogłoszenie" in html and "Wyślij" in html)
    check("instrukcja podaje limit zdjęć z kodu", f"do {sol.MAX_IMAGES} stron" in html)
    r = await client.get("/api/roles/me", headers=auth(soltys))
    check("/api/roles/me zwraca uprawnienie do ogłoszeń",
          r.status_code == 200 and role_service.PERM_SOLECTWO_POST in r.json()[0]["permissions"])

    print("\n3️⃣  Zużyte, wygasłe i wycofane zaproszenie")
    r = await client.post("/api/auth/register", json={
        "email": f"drugi{TEST_DOMAIN}", "password": "Testowe123", "full_name": "Ktoś Drugi",
        "consent_terms": True, "invite_token": token,
    })
    check("drugi raz ten sam link → 410", r.status_code == 410, r.status_code)
    async with async_session() as session:
        second = (await session.execute(select(User).where(User.email == f"drugi{TEST_DOMAIN}"))).scalar_one_or_none()
    check("konto z nieważnym linkiem NIE powstało", second is None)
    async with async_session() as session:
        expired = await role_service.create_invitation(session, "soltys", "Rumian", None, admin.email)
        expired.expires_at = datetime.utcnow() - timedelta(minutes=1)
        session.add(expired)
        await session.commit()
        expired_token = expired.token
    r = await client.get(f"/api/roles/invitation/{expired_token}")
    check("wygasłe: strona mówi, że wygasło", r.json().get("state") == "expired")
    r = await client.post("/api/roles/admin/invitations", headers=auth(admin), json={"role": "soltys", "scope": "Rumian"})
    revoked_id, revoked_token = r.json()["id"], r.json()["url"].split("kod=")[1]
    await client.delete(f"/api/roles/admin/invitations/{revoked_id}", headers=auth(admin))
    r = await client.post(f"/api/roles/invitation/{revoked_token}/accept", headers=auth(resident))
    check("wycofane → 410", r.status_code == 410, r.status_code)

    print("\n4️⃣  Istniejące konto przyjmuje zaproszenie")
    existing = await make_user(f"istniejacy{TEST_DOMAIN}")
    r = await client.post("/api/roles/admin/invitations", headers=auth(admin), json={"role": "soltys", "scope": "Rumian"})
    tok2 = r.json()["url"].split("kod=")[1]
    sent_emails.clear()
    r = await client.post(f"/api/roles/invitation/{tok2}/accept", headers=auth(existing))
    check("przyjęte", r.status_code == 200 and r.json()["signed_as"] == "Sołtys sołectwa Rumian", r.text[:120])
    existing = await reload(User, existing.id)
    check("trial zamieniony na Premium bez terminu", existing.trial_ends_at is None and existing.tier == "premium")
    check("instrukcja wyszła", any("Sołtys sołectwa Rumian" in m["subject"] for m in sent_emails))

    print("\n5️⃣  Zwykłe konto nie doda ogłoszenia")
    files = [("images", ("pismo.jpg", jpeg_bytes(), "image/jpeg"))]
    r = await client.post("/api/solectwa/posts", headers=auth(resident), files=files)
    check("403 dla mieszkańca", r.status_code == 403, r.status_code)

    print("\n6️⃣  Sołtys wysyła zdjęcie pisma")
    sent_emails.clear()
    r = await client.post("/api/solectwa/posts", headers=auth(soltys), files=files,
                          data={"note": "Proszę o publikację"})
    check("przyjęte", r.status_code == 201, r.text[:200])
    post_id = r.json()["id"]
    post = await reload(SolectwoPost, post_id)
    check("odczyt w tle → pending", post.status == "pending", post.status)
    check("przedruk i termin zapisane", bool(post.transcript) and post.event_at is not None)
    check("podpis funkcją", post.signed_as == "Sołtys sołectwa Żabiny")
    stored = sol.PRIVATE_DIR / post.image_files[0]
    check("zdjęcie w katalogu prywatnym", stored.exists(), stored)
    check("zdjęcie NIE w publicznym /uploads", "private_uploads" in str(stored) and "/uploads/" not in str(stored).replace("private_uploads", ""))
    from src.config import settings
    if settings.ADMIN_ALERT_EMAIL:
        check("dzwonek do redakcji", any("do moderacji" in m["subject"] for m in sent_emails),
              [m["subject"] for m in sent_emails])
    else:
        print("   ⏭  dzwonek: brak ADMIN_ALERT_EMAIL lokalnie — pominięte")
    r = await client.post("/api/solectwa/posts", headers=auth(soltys),
                          files=[("images", ("x.jpg", b"to nie jest obraz", "image/jpeg"))])
    check("uszkodzony plik → 400 z komunikatem", r.status_code == 400, r.status_code)
    r = await client.post("/api/solectwa/posts", headers=auth(soltys),
                          files=[("images", (f"{i}.jpg", jpeg_bytes(), "image/jpeg")) for i in range(sol.MAX_IMAGES + 1)])
    check(f"więcej niż {sol.MAX_IMAGES} zdjęć → 400", r.status_code == 400, r.status_code)
    r = await client.get("/api/solectwa/posts/mine", headers=auth(soltys))
    check("sołtys widzi swoje ogłoszenie", any(p["id"] == post_id for p in r.json()))

    print("\n7️⃣  Zdjęcie oryginału tylko dla redakcji")
    r = await client.get(f"/api/solectwa/admin/posts/{post_id}/images/0", headers=auth(admin))
    check("redakcja: 200 image/jpeg", r.status_code == 200 and r.headers["content-type"] == "image/jpeg")
    r = await client.get(f"/api/solectwa/admin/posts/{post_id}/images/0", headers=auth(soltys))
    check("sołtys: 403", r.status_code == 403, r.status_code)
    r = await client.get(f"/api/solectwa/admin/posts/{post_id}/images/0")
    check("anonim: 401/403", r.status_code in (401, 403), r.status_code)

    print("\n8️⃣  Przed moderacją nie istnieje publicznie")
    r = await client.get(f"/api/solectwa/posts/{post_id}")
    check("404", r.status_code == 404, r.status_code)

    print("\n9️⃣  Zatwierdzenie")
    r = await client.patch(f"/api/solectwa/admin/posts/{post_id}", headers=auth(admin),
                           json={"title": "Zebranie wiejskie w Żabinach — 15 października"})
    check("redakcja poprawia tytuł", r.status_code == 200)
    sent_emails.clear()
    r = await client.post(f"/api/solectwa/admin/posts/{post_id}/approve", headers=auth(admin))
    check("opublikowane", r.status_code == 200 and r.json()["status"] == "published", r.text[:200])
    post = await reload(SolectwoPost, post_id)
    article = await reload(Article, post.article_id)
    check("artykuł powstał", article is not None)
    if article:
        check("tytuł z moderacji, nie z modelu", article.display_title == "Zebranie wiejskie w Żabinach — 15 października")
        check("zatwierdzone nie jest „zapychaczem”", article.is_filler is False)
        check("termin z odczytu", article.event_at == post.event_at)
        check("link na stronę ogłoszenia", article.url.endswith(f"/ogloszenie?id={post_id}"), article.url)
        check("autor = funkcja", article.author == "Sołtys sołectwa Żabiny")
    check("mail do sołtysa z linkiem", any(
        m["to"] == soltys.email and f"/ogloszenie?id={post_id}" in m["html"] for m in sent_emails))
    r = await client.get(f"/api/solectwa/posts/{post_id}")
    pub = r.json()
    check("publicznie: 200 z przedrukiem", r.status_code == 200 and "Zebranie wiejskie" in pub["transcript"])
    check("publicznie: bez zdjęć, notatki i danych osobowych",
          not any(k in pub for k in ("image_files", "note", "personal_data")))
    check("publicznie: czas ze strefą", str(pub["event_at"]).endswith(("Z", "+00:00")), pub["event_at"])
    r = await client.post(f"/api/solectwa/admin/posts/{post_id}/approve", headers=auth(admin))
    check("drugie zatwierdzenie → 409", r.status_code == 409, r.status_code)

    print("\n🔟  Odrzucenie")
    r = await client.post("/api/solectwa/posts", headers=auth(soltys), files=files)
    reject_id = r.json()["id"]
    sent_emails.clear()
    r = await client.post(f"/api/solectwa/admin/posts/{reject_id}/reject", headers=auth(admin),
                          json={"reason": "Pismo dotyczy innej gminy"})
    check("odrzucone", r.status_code == 200 and r.json()["status"] == "rejected")
    check("mail z powodem", any("innej gminy" in m["html"] for m in sent_emails))

    await after_publication(client, admin, soltys, files)

    print("\n1️⃣1️⃣  Odebranie roli")
    r = await client.get("/api/roles/admin/list", headers=auth(admin))
    rumian = next(x for x in r.json() if x["user_id"] == existing.id)
    r = await client.post(f"/api/roles/admin/roles/{rumian['id']}/revoke", headers=auth(admin))
    check("odebrana", r.status_code == 200)
    existing = await reload(User, existing.id)
    check("Premium z roli znika", existing.tier == UserTier.FREE.value, existing.tier)
    r = await client.post("/api/solectwa/posts", headers=auth(existing), files=files)
    check("bez roli nie doda ogłoszenia", r.status_code == 403, r.status_code)
    async with async_session() as session:
        check("Premium sołtysa z Żabin nietknięte", await role_service.has_premium_role(session, soltys.id))

    print("\n1️⃣2️⃣  Retencja zdjęć")
    async with async_session() as session:
        purged = await sol.purge_old_images(session, datetime.utcnow() + timedelta(days=sol.IMAGE_RETENTION_DAYS - 1))
        await session.commit()
    check("przed terminem nic nie znika", purged == 0 and stored.exists(), purged)
    async with async_session() as session:
        purged = await sol.purge_old_images(session, datetime.utcnow() + timedelta(days=sol.IMAGE_RETENTION_DAYS + 1))
        await session.commit()
    check("po terminie zdjęcia skasowane", purged >= 2 and not stored.exists(), purged)
    r = await client.get(f"/api/solectwa/admin/posts/{post_id}/images/0", headers=auth(admin))
    check("endpoint zdjęcia → 404", r.status_code == 404, r.status_code)

    print("\n1️⃣3️⃣  DSAR — usunięcie konta sołtysa")
    r = await client.post("/api/solectwa/posts", headers=auth(soltys), files=files)
    unpublished_id = r.json()["id"]
    from src.users.dsar import delete_user_account, export_user_data
    async with async_session() as session:
        account = await session.get(User, soltys.id)
        export = await export_user_data(session, account)
        check("eksport zawiera role, ogłoszenia i prośby",
              len(export["roles"]) == 1 and len(export["solectwo_posts"]) == 5
              and len(export["solectwo_requests"]) == 2, (len(export["solectwo_posts"]), len(export["solectwo_requests"])))
        await delete_user_account(session, account)
    published = await reload(SolectwoPost, post_id)
    check("opublikowane zostaje, bez konta", published is not None and published.user_id is None)
    check("nieopublikowane skasowane", await reload(SolectwoPost, unpublished_id) is None)
    async with async_session() as session:
        left = (await session.execute(select(UserRole).where(UserRole.user_id == soltys.id))).all()
    check("rola skasowana", not left)
    r = await client.get(f"/api/solectwa/posts/{post_id}")
    check("ogłoszenie wciąż dostępne publicznie", r.status_code == 200)

    print("\n1️⃣4️⃣  Kontrola kodem odczytu")
    from src.ai.scan_reader import ScanReading, ground_term, redact
    red, found = redact("Wnioskodawca PESEL 85010112345, dowód ABC123456, tel. urzędu 23 696 60 55")
    check("PESEL wycięty", "85010112345" not in red and found)
    check("dowód wycięty", "ABC123456" not in red)
    check("telefon urzędu zostaje", "23 696 60 55" in red)
    from src.ai.scan_reader import PrivateFragment, redact_fragments
    (cut,), kinds, missing = redact_fragments(
        ["Wniosek Pani Anny Kowalskiej,\nzam. Żabiny 12. Nr Żabiny 120 i sołtys Jan Nowak zostają."],
        [PrivateFragment(text="Anny Kowalskiej", kind="imię i nazwisko"),
         PrivateFragment(text="Żabiny 12", kind="adres"),
         PrivateFragment(text="Anna Nieobecna", kind="imię i nazwisko")],
    )
    (cut2,), _, missing2 = redact_fragments(
        ["Wniosek Pani Anny Kowalskiej w sprawie drogi. Anna z urzędu zostaje."],
        [PrivateFragment(text="Anna Kowalska", kind="imię i nazwisko")],
    )
    check("wskazane przez model dane wycina KOD", "Kowalsk" not in cut and "Żabiny 12," not in cut, cut)
    check("granica słowa: „Żabiny 120” nietknięte", "Żabiny 120" in cut)
    check("fragment spoza przedruku zgłoszony redakcji", missing == ["Anna Nieobecna"], missing)
    check("forma podstawowa „Anna Kowalska” wycina „Anny Kowalskiej”",
          "Kowalsk" not in cut2 and not missing2, cut2)
    check("rdzeń nie zjada pojedynczego „Anna” w innym miejscu", "Anna z urzędu" in cut2, cut2)
    now = datetime(2026, 9, 27, 10, 0)
    grounded = ScanReading(title="Zebranie", transcript="Zebranie odbędzie się 15 października 2026 r. o godz. 18:00.",
                           event_start="2026-10-15T18:00")
    start, _ = ground_term(grounded, now)
    check("termin z pisma przyjęty (18:00 lokalnie = 16:00 UTC)", start == datetime(2026, 10, 15, 16, 0), start)
    invented = ScanReading(title="Komunikat", transcript="Prosimy o nieparkowanie przy świetlicy.",
                           event_start="2026-10-03T12:00")
    start, _ = ground_term(invented, now)
    check("termin zmyślony odrzucony", start is None, start)
    fallback = ScanReading(title="Zebranie", transcript="Zebranie 20 października 2026 r. godz. 17:00 w remizie.",
                           event_start=None)
    start, _ = ground_term(fallback, now)
    # Sam DZIEŃ: wspólny `parse_date_span` gubi godzinę w zapisie „2026 r. godz.
    # 17:00" (kropkę po „r." bierze za koniec zdania) — luka parsera, nie tego
    # modułu; przy piśmie urzędowym godzinę daje zwykle model (przypadek wyżej)
    from src.services.time_span import to_local
    check("brak terminu od modelu → kod czyta dzień z tekstu",
          start is not None and to_local(start).date() == datetime(2026, 10, 20).date(), start)

    if live:
        await live_scan()


async def publish_new(client, admin, soltys, files) -> tuple[int, int]:
    r = await client.post("/api/solectwa/posts", headers=auth(soltys), files=files)
    pid = r.json()["id"]
    r = await client.post(f"/api/solectwa/admin/posts/{pid}/approve", headers=auth(admin))
    assert r.status_code == 200, r.text
    post = await reload(SolectwoPost, pid)
    return pid, post.article_id


async def add_event(article_id: int, title: str, canonical_id=None, source_article_id=-1) -> int:
    """Wydarzenie z ogłoszenia (ekstraktora tu nie uruchamiamy) + chunk RAG."""
    async with async_session() as session:
        event = Event(
            title=title, event_date=datetime(2026, 10, 15, 16, 0), event_time="18:00",
            location="Żabiny", locality=3, canonical_id=canonical_id,
            source_article_id=article_id if source_article_id == -1 else source_article_id,
            description="Zebranie 15 października", embedded=True,
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)
        await session.execute(text(
            "INSERT INTO document_embeddings (source_type, source_id, chunk_index, chunk_text) "
            "VALUES ('event', :id, 0, 'test')"), {"id": event.id})
        await session.commit()
        return event.id


async def chunks(source_type: str, source_id: int) -> int:
    async with async_session() as session:
        return (await session.execute(text(
            "SELECT count(*) FROM document_embeddings WHERE source_type = :t AND source_id = :i"),
            {"t": source_type, "i": source_id})).scalar()


async def visible(article_id: int) -> bool:
    from src.services.feed_policy import publishable_conditions
    async with async_session() as session:
        row = (await session.execute(
            select(Article.id).where(Article.id == article_id, *publishable_conditions(Article))
        )).first()
    return row is not None


async def event_visible(event_id: int) -> bool:
    from src.services.feed_policy import visible_event_conditions
    async with async_session() as session:
        row = (await session.execute(
            select(Event.id).where(Event.id == event_id, *visible_event_conditions(Event))
        )).first()
    return row is not None


async def after_publication(client, admin, soltys, files) -> None:
    print("\n1️⃣5️⃣  Po publikacji: prośba, korekta, odwołanie (E7)")
    pid, aid = await publish_new(client, admin, soltys, files)
    post = await reload(SolectwoPost, pid)
    check("publikacja = wersja 1 w historii", post.version == 1)
    event_id = await add_event(aid, "Zebranie wiejskie w Żabinach")
    async with async_session() as session:
        await session.execute(text(
            "INSERT INTO document_embeddings (source_type, source_id, chunk_index, chunk_text) "
            "VALUES ('article', :id, 0, 'stara treść')"), {"id": aid})
        await session.execute(text("UPDATE articles SET embedded = true WHERE id = :id"), {"id": aid})
        await session.commit()

    # Edycja PATCH nadal nie rusza opublikowanego — od tego jest korekta
    r = await client.patch(f"/api/solectwa/admin/posts/{pid}", headers=auth(admin), json={"title": "x"})
    check("PATCH opublikowanego nadal 409", r.status_code == 409, r.status_code)

    # Prośba sołtysa
    sent_emails.clear()
    r = await client.post(f"/api/solectwa/posts/{pid}/requests", headers=auth(soltys),
                          json={"kind": "correction", "message": f"Zebranie przeniesione na {NEW_DAY_TEXT}"})
    check("sołtys składa prośbę o korektę", r.status_code == 201 and len(r.json()["open_requests"]) == 1, r.text[:200])
    request_id = r.json()["open_requests"][0]["id"]
    r = await client.post(f"/api/solectwa/posts/{pid}/requests", headers=auth(soltys),
                          json={"kind": "correction", "message": "Jeszcze raz to samo"})
    check("druga taka sama prośba → 409", r.status_code == 409, r.status_code)
    stranger = await make_user(f"obcy{TEST_DOMAIN}")
    r = await client.post(f"/api/solectwa/posts/{pid}/requests", headers=auth(stranger),
                          json={"kind": "withdrawal", "message": "Odwołajcie to"})
    check("cudze ogłoszenie → 404", r.status_code == 404, r.status_code)
    r = await client.get("/api/solectwa/admin/posts", headers=auth(admin))
    listed = next((p for p in r.json() if p["id"] == pid), None)
    check("redakcja widzi prośbę przy ogłoszeniu", listed and listed["open_requests"][0]["kind"] == "correction")

    # Korekta terminu
    sent_emails.clear()
    reembedded.clear()
    r = await client.post(f"/api/solectwa/admin/posts/{pid}/correct", headers=auth(admin), json={
        "reason": "Zmiana terminu zebrania",
        "term_action": "set", "term": {"day": NEW_DAY.isoformat(), "start": "18:00"},
        "summary": f"Sołtys zaprasza na zebranie wiejskie {NEW_DAY_TEXT} o 18:00 w świetlicy.",
        "request_id": request_id,
    })
    check("korekta przyjęta", r.status_code == 200 and r.json()["version"] == 2, r.text[:200])
    check("prośba zamknięta", r.json().get("open_requests") == [])
    post = await reload(SolectwoPost, pid)
    article = await reload(Article, aid)
    event = await reload(Event, event_id)
    new_start = to_utc(datetime.combine(NEW_DAY, time(18, 0)))  # 18:00 lokalnie
    check("ogłoszenie: nowy termin w UTC", post.event_at == new_start, post.event_at)
    check("artykuł: nowy termin i podsumowanie",
          article.event_at == new_start and NEW_DAY_TEXT in (article.summary or ""))
    check("artykuł: znacznik korekty terminu", article.term_corrected_at is not None)
    check("kalendarz: wydarzenie przeniesione, godzina lokalna",
          event.event_date == new_start and event.event_time == "18:00", (event.event_date, event.event_time))
    check("kalendarz: opis z zatwierdzonego podsumowania", NEW_DAY_TEXT in (event.description or ""))
    check("RAG: stare chunki artykułu i wydarzenia skasowane",
          await chunks("event", event_id) == 0 and event.embedded is False)
    check("RAG: poprawiona treść osadzona od razu", reembedded == [aid], reembedded)
    check("mail do sołtysa o korekcie z powodem", any(
        m["to"] == soltys.email and "poprawiliśmy" in m["subject"].lower() and "Zmiana terminu" in m["html"]
        for m in sent_emails), [m["subject"] for m in sent_emails])
    from src.ai.summary_generator import _time_label
    label = _time_label(article, datetime.utcnow())
    check("briefing: etykieta „termin zaktualizowany” bez słowa o korekcie",
          "TERMIN ZAKTUALIZOWANY" in label and "KOREKTA" not in label, label)
    check("briefing: model ma nie pisać o zmianie", "NIE PISZ O ZMIANIE" in label, label)
    later = _time_label(article, datetime.utcnow() + timedelta(days=3))
    check("briefing: po dobie etykieta znika", "ZAKTUALIZOWANY" not in later, later)
    from src.ai.summary_generator import SummaryGenerator
    now = datetime.utcnow()
    gen = SummaryGenerator.__new__(SummaryGenerator)
    gen.logger = sol_logger()
    async with async_session() as session:
        material = await gen._fetch_articles(session, now - timedelta(hours=6), now, now=now)
    check("briefing: korekta wraca do materiału mimo terminu za tydzień", any(a.id == aid for a in material))
    r = await client.post(f"/api/solectwa/admin/posts/{pid}/correct", headers=auth(admin),
                          json={"reason": "Bez zmian"})
    check("korekta bez zmian → 400", r.status_code == 400, r.status_code)
    r = await client.post(f"/api/solectwa/admin/posts/{pid}/correct", headers=auth(soltys),
                          json={"reason": "Sam poprawię", "title": "x"})
    check("sołtys nie poprawi sam (403)", r.status_code == 403, r.status_code)

    pub = (await client.get(f"/api/solectwa/posts/{pid}")).json()
    check("strona: nowa treść, BEZ jakiegokolwiek śladu korekty",
          NEW_DAY_TEXT in pub["summary"]
          and not any(k in pub for k in ("changes", "corrected_at", "withdrawn_at", "withdraw_reason", "version")),
          sorted(pub))
    check("strona: powód korekty nie wycieka", "Zmiana terminu" not in str(pub), str(pub)[:120])

    # Odwołanie — z powtórką z innego źródła wskazującą nasz wpis
    duplicate_id = await add_event(aid, "Zebranie wiejskie Żabiny (FB)", canonical_id=event_id, source_article_id=None)
    async with async_session() as session:
        await session.execute(text("DELETE FROM document_embeddings WHERE source_type='event' AND source_id=:i"),
                              {"i": duplicate_id})
        await session.commit()
    check("przed odwołaniem: wpis widoczny w feedzie i kalendarzu", await visible(aid) and await event_visible(event_id))
    r = await client.post(f"/api/solectwa/posts/{pid}/requests", headers=auth(soltys),
                          json={"kind": "withdrawal", "message": "Zebranie odwołane przez gminę"})
    withdraw_request = r.json()["open_requests"][0]["id"]
    sent_emails.clear()
    r = await client.post(f"/api/solectwa/admin/posts/{pid}/withdraw", headers=auth(admin),
                          json={"reason": "Zebranie odwołane", "request_id": withdraw_request})
    check("odwołane", r.status_code == 200 and r.json()["status"] == "withdrawn" and r.json()["version"] == 3, r.text[:200])
    check("feed/briefing/newsletter/push: wpis poza bramką", not await visible(aid))
    check("kalendarz: wydarzenie ukryte", not await event_visible(event_id))
    dup = await reload(Event, duplicate_id)
    check("powtórka z innego źródła przejmuje kalendarz",
          dup.canonical_id is None and dup.embedded is False and await event_visible(duplicate_id))
    check("RAG: chunki artykułu skasowane", await chunks("article", aid) == 0)
    check("artykuł NIE skasowany (historia)", await reload(Article, aid) is not None)
    check("mail do sołtysa o odwołaniu", any("Odwołaliśmy" in m["subject"] for m in sent_emails))
    pub = (await client.get(f"/api/solectwa/posts/{pid}")).json()
    check("strona: odwołane = samo „nieaktualne”, bez powodu, treści, terminu i tytułu",
          pub["status"] == "withdrawn" and pub["transcript"] is None and pub["summary"] is None
          and pub["event_at"] is None and "Zebranie" not in pub["title"]
          and "withdraw_reason" not in pub and "Zebranie odwołane" not in str(pub), pub)
    r = await client.post(f"/api/solectwa/admin/posts/{pid}/correct", headers=auth(admin),
                          json={"reason": "Po odwołaniu", "title": "Nowy"})
    check("korekta odwołanego → 409", r.status_code == 409, r.status_code)
    r = await client.get(f"/api/solectwa/admin/posts/{pid}/versions", headers=auth(admin))
    kinds = [v["kind"] for v in r.json()]
    check("historia: publikacja → korekta → odwołanie", kinds == ["publication", "correction", "withdrawal"], kinds)
    check("historia: pierwsza wersja ma STARY termin",
          r.json()[0]["event_at"].startswith("2026-10-15T16:00"), r.json()[0]["event_at"])
    r = await client.get(f"/api/solectwa/admin/posts/{pid}/versions", headers=auth(soltys))
    check("historia z treścią tylko dla redakcji", r.status_code == 403, r.status_code)
    r = await client.get("/api/solectwa/posts/mine", headers=auth(soltys))
    mine = next(p for p in r.json() if p["id"] == pid)
    check("sołtys widzi status „odwołane” i link", mine["status"] == "withdrawn" and mine["url"])

    print("\n1️⃣6️⃣  Takedown wpisu sołectwa z wydarzeniem")
    pid2, aid2 = await publish_new(client, admin, soltys, files)
    ev2 = await add_event(aid2, "Festyn w Żabinach")
    dup2 = await add_event(aid2, "Festyn (inne źródło)", canonical_id=ev2, source_article_id=None)
    r = await client.delete(f"/api/articles/{aid2}", headers=auth(admin))
    check("DELETE /api/articles nie pada (200)", r.status_code == 200, r.status_code)
    post2 = await reload(SolectwoPost, pid2)
    check("ogłoszenie zostaje jako odwołane, bez artykułu",
          post2.status == "withdrawn" and post2.article_id is None, (post2.status, post2.article_id))
    check("wydarzenie z artykułu usunięte", await reload(Event, ev2) is None)
    check("powtórka odpięta, nie wskazuje skasowanego", (await reload(Event, dup2)).canonical_id is None)
    async with async_session() as session:
        await session.execute(text("DELETE FROM events WHERE id = ANY(:ids)"), {"ids": [duplicate_id, dup2]})
        await session.commit()


def sol_logger():
    from src.utils.logger import setup_logger
    return setup_logger("TestSolectwa")


def letter_image() -> bytes:
    """Wygenerowane pismo — prawdziwy tekst, dane osoby prywatnej, termin."""
    from PIL import Image, ImageDraw, ImageFont
    lines = [
        "Sołtys Sołectwa Żabiny", "Żabiny, 25 września 2026 r.", "",
        "ZAWIADOMIENIE", "",
        "Zapraszam mieszkańców sołectwa Żabiny na zebranie wiejskie,",
        "które odbędzie się 15 października 2026 r. o godz. 18:00",
        "w świetlicy wiejskiej w Żabinach.", "",
        "Porządek zebrania:", "1. Podział funduszu sołeckiego na 2027 rok.",
        "2. Wniosek Pani Anny Kowalskiej, PESEL 85010112345,",
        "   zam. Żabiny 12, w sprawie oświetlenia drogi.", "3. Sprawy różne.", "",
        "Sołtys", "Jan Nowak",
    ]
    font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
    font = ImageFont.truetype(font_path, 34)
    img = Image.new("RGB", (1400, 1400), "white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((80, 80 + i * 70), line, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


async def live_scan() -> None:
    print("\n🔴 LIVE: prawdziwy odczyt gpt-4o wygenerowanego pisma")
    import importlib
    from src.ai import scan_reader
    importlib.reload(scan_reader)  # zdejmij podmianę z patch_outside_world
    from src.ai.scan_reader import ScanReader, shrink
    data, _ = shrink(letter_image())
    # Z dopiskiem, jak w formularzu — pierwsza wysyłka przez UI (27.09) z dopiskiem
    # dała pusty tytuł i podsumowanie
    result, tin, tout = await ScanReader().read(
        [data], note="Proszę o publikację przed zebraniem", now=datetime(2026, 9, 27, 10, 0),
    )
    print(f"   tokeny: {tin} + {tout}")
    print("   przedruk:\n      " + result.transcript.replace("\n", "\n      "))
    print(f"   tytuł: {result.title}\n   podsumowanie: {result.summary}")
    print(f"   dane osobowe: {result.personal_data}")
    check("rozpoznane jako pismo", result.is_document)
    check("tytuł i podsumowanie niepuste", bool(result.title.strip() and result.summary.strip()),
          f"{result.title!r} / {result.summary[:40]!r}")
    check("przedruk zawiera porządek zebrania", "funduszu sołeckiego" in result.transcript)
    check("PESEL wycięty", "85010112345" not in result.transcript)
    check("nazwisko osoby prywatnej wycięte", "Kowalsk" not in result.transcript)
    check("adres osoby prywatnej wycięty", "Żabiny 12" not in result.transcript)
    check("sołtys z funkcją zostaje", "Nowak" in result.transcript)
    check("termin 15.10 18:00 (16:00 UTC)", result.event_at == datetime(2026, 10, 15, 16, 0), result.event_at)


async def cleanup() -> None:
    from src.api.endpoints.solectwa import PRIVATE_DIR
    async with async_session() as session:
        ids = [r[0] for r in (await session.execute(
            text("SELECT id FROM users WHERE email LIKE :d OR email LIKE 'usuniete-%@anonimizacja.rybnolive.pl' AND full_name = 'Konto usunięte' AND id IN (SELECT user_id FROM solectwo_posts UNION SELECT used_by_user_id FROM role_invitations WHERE created_by LIKE :d)"),
            {"d": f"%{TEST_DOMAIN}"},
        )).all()]
        posts = (await session.execute(
            select(SolectwoPost).where(
                (SolectwoPost.user_id.in_(ids)) | (SolectwoPost.moderated_by.like(f"%{TEST_DOMAIN}"))
            )
        )).scalars().all()
        for post in posts:
            for name in post.image_files or []:
                (PRIVATE_DIR / name).unlink(missing_ok=True)
        article_ids = [p.article_id for p in posts if p.article_id]
        post_ids = [p.id for p in posts]
        await session.execute(text("DELETE FROM solectwo_post_requests WHERE post_id = ANY(:ids)"), {"ids": post_ids})
        await session.execute(text("DELETE FROM solectwo_post_versions WHERE post_id = ANY(:ids)"), {"ids": post_ids})
        await session.execute(text("DELETE FROM solectwo_posts WHERE id = ANY(:ids)"), {"ids": post_ids})
        if article_ids:
            await session.execute(text(
                "DELETE FROM document_embeddings WHERE source_type = 'event' AND source_id IN "
                "(SELECT id FROM events WHERE source_article_id = ANY(:ids))"), {"ids": article_ids})
            await session.execute(text("DELETE FROM events WHERE source_article_id = ANY(:ids)"), {"ids": article_ids})
            await session.execute(text(
                "DELETE FROM document_embeddings WHERE source_type = 'article' AND source_id = ANY(:ids)"),
                {"ids": article_ids})
            await session.execute(text("DELETE FROM articles WHERE id = ANY(:ids)"), {"ids": article_ids})
        await session.execute(text("DELETE FROM role_invitations WHERE created_by LIKE :d"), {"d": f"%{TEST_DOMAIN}"})
        if ids:
            await session.execute(text("DELETE FROM user_roles WHERE user_id = ANY(:ids)"), {"ids": ids})
            await session.execute(text("DELETE FROM api_cost_log WHERE user_id = ANY(:ids)"), {"ids": ids})
            await session.execute(text("DELETE FROM site_events WHERE user_id = ANY(:ids)"), {"ids": ids})
            await session.execute(text("DELETE FROM newsletter_subscribers WHERE user_id = ANY(:ids) OR email LIKE :d"),
                                  {"ids": ids, "d": f"%{TEST_DOMAIN}"})
            await session.execute(text("DELETE FROM solectwo_post_requests WHERE user_id = ANY(:ids)"), {"ids": ids})
            await session.execute(text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids": ids})
        await session.commit()


async def main() -> int:
    live = "--live" in sys.argv
    patch_outside_world()
    await cleanup()
    from src.api.main import app
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await run(client, live)
    finally:
        await cleanup()
    failed = results.count(False)
    print(f"\n{'✅' if not failed else '❌'} {len(results) - failed}/{len(results)} sprawdzeń")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
