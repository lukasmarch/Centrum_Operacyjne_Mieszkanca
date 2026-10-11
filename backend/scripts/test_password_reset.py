"""
Reset hasła i sesje związane z hasłem (audyt 11.10.2026, F-028).

Bez bazy, bez sieci i bez modelu — dlatego idzie do CI. Trasy kont działają na
małej aplikacji z atrapą sesji bazy (`FakeSession`), a mail resetu jest
przechwytywany zamiast wysyłany.

  1. token resetu: ważny 1 h, podpisany, tylko swojego typu,
  2. odcisk hasła w tokenach: nowe hasło unieważnia stare sesje, token sprzed
     wdrożenia (bez `pwv`) przechodzi,
  3. /forgot-password: TA SAMA odpowiedź dla istniejącego i obcego adresu,
     mail tylko do istniejącego, limit próśb,
  4. /reset-password: ustawia hasło, link działa RAZ, stara sesja odpada,
  5. /login: limit nieudanych prób per IP+adres, nie per sam adres,
  6. zmiana hasła w profilu oddaje nowe tokeny, stare odpadają.

    cd backend && python -m scripts.test_password_reset
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio

import httpx
from fastapi import FastAPI

from src.auth import routes as auth_routes
from src.auth.jwt import (
    create_access_token, create_password_reset_token, get_password_hash,
    read_password_reset_token, session_claims, token_matches_password, verify_password,
)
from src.database import get_session
from src.database.schema import User
from src.users.routes import router as users_router

results: list[bool] = []


def check(label: str, ok: bool, detail="") -> None:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + str(detail)) if detail else ''}")
    results.append(bool(ok))


# --------------------------------------------------------------------------- atrapy

def make_user(email: str = "jan@example.pl", password: str = "Haslo1234") -> User:
    return User(
        id=7, email=email, full_name="Jan Testowy", location="Rybno R1",
        tier="free", is_active=True, password_hash=get_password_hash(password),
    )


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def first(self):
        return self._value


class FakeSession:
    """Zna jedno konto. Każde zapytanie o użytkownika zwraca je, gdy pasuje adres."""

    def __init__(self, user):
        self.user = user

    async def execute(self, stmt):
        params = stmt.compile().params
        email = next((v for v in params.values() if isinstance(v, str) and "@" in v), None)
        found = self.user if self.user is not None and (email is None or email == self.user.email) else None
        return _Result(found)

    async def get(self, model, pk):
        return self.user if self.user is not None and self.user.id == pk else None

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    def add(self, obj):
        pass


def make_client(user):
    app = FastAPI()
    app.include_router(auth_routes.router)
    app.include_router(users_router)
    fake = FakeSession(user)

    async def _session():
        yield fake

    app.dependency_overrides[get_session] = _session
    return Client(app)


class Client:
    """Synchroniczna otoczka na `httpx.ASGITransport` — `TestClient` ze starlette 0.35
    nie działa z httpx 0.28 (ten sam wzorzec co `test_access_control`)."""

    def __init__(self, app, ip: str = "127.0.0.1"):
        self.app = app
        self.ip = ip

    def _call(self, method, url, **kw):
        async def run():
            transport = httpx.ASGITransport(app=self.app, client=(self.ip, 50000))
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
                return await c.request(method, url, **kw)
        return asyncio.run(run())

    def get(self, url, **kw):
        return self._call("GET", url, **kw)

    def post(self, url, **kw):
        return self._call("POST", url, **kw)


sent_mails: list = []


async def _capture_mail(email, full_name, reset_url):
    sent_mails.append((email, reset_url))


auth_routes._send_password_reset = _capture_mail


def reset_limits():
    for limit in (auth_routes.LOGIN_FAILS_PAIR, auth_routes.LOGIN_FAILS_IP,
                  auth_routes.RESET_BY_IP, auth_routes.RESET_BY_EMAIL):
        limit.reset()


# --------------------------------------------------------------------------- sekcje

def section_reset_token() -> None:
    print("\n1️⃣  Token resetu")
    user = make_user()
    token = create_password_reset_token(user)
    check("świeży token czyta się poprawnie", read_password_reset_token(token) is not None)
    old = create_password_reset_token(user, now=datetime.utcnow() - timedelta(hours=2))
    check("token sprzed 2 h jest martwy (ważność 1 h)", read_password_reset_token(old) is None)
    check("podmieniony podpis odrzucony", read_password_reset_token(token[:-3] + "abc") is None)
    access = create_access_token(session_claims(user))
    check("token logowania nie działa jako token resetu", read_password_reset_token(access) is None)


def section_fingerprint() -> None:
    print("\n2️⃣  Odcisk hasła w sesji")
    user = make_user()
    payload = session_claims(user)
    check("token sesji niesie odcisk hasła", "pwv" in payload)
    check("pasuje do bieżącego hasła", token_matches_password(payload, user))
    user.password_hash = get_password_hash("Haslo1234")  # to samo hasło, nowa sól
    check("po ponownym ustawieniu hasła stara sesja odpada", not token_matches_password(payload, user))
    legacy = {"sub": user.email, "user_id": user.id}
    check("token sprzed wdrożenia (bez pwv) przechodzi — nikt nie zostaje wylogowany",
          token_matches_password(legacy, user))


def section_forgot() -> None:
    print("\n3️⃣  /forgot-password")
    reset_limits()
    sent_mails.clear()
    user = make_user()
    client = make_client(user)
    known = client.post("/api/auth/forgot-password", json={"email": user.email})
    unknown = client.post("/api/auth/forgot-password", json={"email": "obcy@example.pl"})
    check("istniejący adres: 200", known.status_code == 200, known.status_code)
    check("ta sama odpowiedź dla istniejącego i obcego adresu",
          known.status_code == unknown.status_code and known.json() == unknown.json())
    check("mail poszedł wyłącznie do istniejącego konta",
          [m[0] for m in sent_mails] == [user.email], sent_mails)
    check("link prowadzi na /nowe-haslo z tokenem",
          bool(sent_mails) and "/nowe-haslo?token=" in sent_mails[0][1])

    reset_limits()
    codes = [client.post("/api/auth/forgot-password", json={"email": user.email}).status_code for _ in range(4)]
    check("4. prośba o ten sam adres tego dnia → 429", codes == [200, 200, 200, 429], codes)


def section_reset() -> None:
    print("\n4️⃣  /reset-password")
    reset_limits()
    user = make_user()
    client = make_client(user)
    old_session = create_access_token(session_claims(user))
    token = create_password_reset_token(user)

    weak = client.post("/api/auth/reset-password", json={"token": token, "new_password": "slabe"})
    check("słabe hasło odrzucone walidacją (422)", weak.status_code == 422, weak.status_code)

    ok = client.post("/api/auth/reset-password", json={"token": token, "new_password": "NoweHaslo9"})
    check("poprawny link ustawia hasło", ok.status_code == 200 and verify_password("NoweHaslo9", user.password_hash),
          ok.status_code)
    check("odpowiedź loguje od razu (tokeny w treści)", "tokens" in ok.json())

    again = client.post("/api/auth/reset-password", json={"token": token, "new_password": "InneHaslo7"})
    check("ten sam link drugi raz → 400 (jednorazowy)", again.status_code == 400, again.status_code)
    check("drugie użycie NIE zmieniło hasła", verify_password("NoweHaslo9", user.password_hash))

    me_old = client.get("/api/users/me", headers={"Authorization": f"Bearer {old_session}"})
    check("sesja sprzed resetu odrzucona (401)", me_old.status_code == 401, me_old.status_code)
    new_access = ok.json()["tokens"]["access_token"]
    me_new = client.get("/api/users/me", headers={"Authorization": f"Bearer {new_access}"})
    check("nowa sesja działa", me_new.status_code == 200, me_new.status_code)

    refresh_old = auth_routes.create_refresh_token({**session_claims(make_user()), "sub": user.email})
    r = client.post("/api/auth/refresh", json={"refresh_token": refresh_old})
    check("token odświeżania sprzed zmiany hasła nie odnawia sesji", r.status_code == 401, r.status_code)

    garbage = client.post("/api/auth/reset-password", json={"token": "x" * 40, "new_password": "NoweHaslo9"})
    check("śmieciowy token → 400", garbage.status_code == 400, garbage.status_code)


def section_login_limit() -> None:
    print("\n5️⃣  Limit nieudanych logowań")
    reset_limits()
    user = make_user()
    client = make_client(user)
    bad = [client.post("/api/auth/login", json={"email": user.email, "password": "Zle12345"}).status_code
           for _ in range(10)]
    check("10 złych haseł → 401 za każdym razem", bad == [401] * 10, bad)
    check("komunikat po polsku", "Nieprawidłowy" in client.post(
        "/api/auth/login", json={"email": "inny@example.pl", "password": "Zle12345"}).json().get("detail", ""))
    blocked = client.post("/api/auth/login", json={"email": user.email, "password": "Haslo1234"})
    check("11. próba z tego IP na ten adres → 429 nawet z dobrym hasłem", blocked.status_code == 429,
          blocked.status_code)
    other_ip = Client(client.app, ip="10.0.0.2")
    elsewhere = other_ip.post("/api/auth/login", json={"email": user.email, "password": "Haslo1234"})
    check("właściciel z innego IP loguje się mimo blokady (brak licznika per sam adres)",
          elsewhere.status_code == 200, elsewhere.status_code)
    reset_limits()
    good = client.post("/api/auth/login", json={"email": user.email, "password": "Haslo1234"})
    check("po wyzerowaniu dobre hasło loguje", good.status_code == 200, good.status_code)


def section_change_password() -> None:
    print("\n6️⃣  Zmiana hasła w profilu")
    reset_limits()
    user = make_user()
    client = make_client(user)
    old_access = create_access_token(session_claims(user))
    r = client.post("/api/users/me/change-password",
                    headers={"Authorization": f"Bearer {old_access}"},
                    json={"current_password": "Haslo1234", "new_password": "NoweHaslo9"})
    check("zmiana hasła oddaje nowe tokeny", r.status_code == 200 and "access_token" in r.json(), r.status_code)
    me_old = client.get("/api/users/me", headers={"Authorization": f"Bearer {old_access}"})
    check("stara sesja (np. na innym urządzeniu) odpada", me_old.status_code == 401, me_old.status_code)
    if r.status_code == 200:
        me_new = client.get("/api/users/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
        check("urządzenie, na którym zmieniono hasło, zostaje zalogowane", me_new.status_code == 200)


if __name__ == "__main__":
    section_reset_token()
    section_fingerprint()
    section_forgot()
    section_reset()
    section_login_limit()
    section_change_password()
    passed = sum(results)
    print(f"\n{'✅' if passed == len(results) else '❌'} {passed}/{len(results)} sprawdzeń")
    sys.exit(0 if passed == len(results) else 1)
