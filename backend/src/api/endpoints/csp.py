"""
Raporty naruszeń Content-Security-Policy — `POST /api/csp-report` (audyt 11.10.2026, E8).

Strona dostaje politykę CSP w trybie RAPORTOWANIA (`Content-Security-Policy-Report-Only`
w Caddy): przeglądarka niczego nie blokuje, tylko wysyła tu zgłoszenie, co by zablokowała.
Przez około dwa tygodnie zbieramy zgłoszenia i na ich podstawie dopuszczamy to, co strona
naprawdę ładuje, zanim polityka zacznie blokować. Odczyt: `python -m scripts.csp_report`.

Decyzje, które trzeba znać przed zmianą tego pliku (te same, co w `analytics.py`):

  * **Endpoint jest publiczny i bez uwierzytelnienia** — przeglądarka wysyła raport sama,
    bez tokenu. Dlatego: limit na IP i globalny (w pamięci procesu), ciało nie większe niż
    16 kB, zamknięta lista kształtów (dyrektywa to `[a-z-]{1,40}`), twardy sufit liczby
    RÓŻNYCH wpisów w tabeli. Bez tego to otwarty zapis do bazy.
  * **Do bazy trafia tylko agregat**: (dyrektywa, ZABLOKOWANE ŹRÓDŁO jako samo `schemat://host`,
    ścieżka strony) i licznik. Nie IP, nie User-Agent, nie pełny adres.
  * **Parametry zapytania i fragment adresu strony są odcinane.** W linkach bywają tokeny
    resetu hasła i zaproszeń sołtysów (`?kod=…`) — raport CSP niesie `document-uri` w całości,
    więc zapisanie go wprost zrobiłoby z tej tabeli zbiór kluczy do kont.
  * **Cisza przy błędzie.** Zawsze 204, także gdy wsad jest do wyrzucenia — przeglądarka
    odpowiedzi nie czyta, a raportowanie nie ma prawa niczego popsuć.

Dwa formaty, bo przeglądarki wysyłają różne: starszy `report-uri` (`application/csp-report`,
`{"csp-report": {…}}`) i Reporting API (`application/reports+json`, lista
`[{"type": "csp-violation", "body": {…}}]`).

RODO: brak danych osobowych; wiersze starsze niż 30 dni od ostatniego wystąpienia kasuje
`scheduler/retention_job.py`.
"""
import json
import re
import time
from collections import defaultdict
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Response
from sqlalchemy import text

from src.database.connection import async_session
from src.utils.logger import setup_logger

logger = setup_logger("CspReport")

router = APIRouter(prefix="/api/csp-report", tags=["csp"])

MAX_BODY_BYTES = 16 * 1024
MAX_REPORTS_PER_REQUEST = 10
# Sufit RÓŻNYCH wpisów (dyrektywa × źródło × strona). Powyżej nowe klucze przepadają,
# a istniejące dalej rosną — tabela nie może urosnąć od ruchu, który ktoś wygenerował.
MAX_DISTINCT = 500

# Limit w pamięci procesu (jeden worker). Raport przychodzi od przeglądarki za KAŻDYM
# zablokowanym zasobem strony, więc jedna wizyta potrafi wysłać ich kilkanaście.
RATE_LIMIT_PER_IP_PER_MIN = 30
RATE_LIMIT_GLOBAL_PER_MIN = 300
_hits: dict = defaultdict(list)

_DIRECTIVE = re.compile(r"^[a-z][a-z-]{0,39}$")
# Słowa kluczowe, które przeglądarka wpisuje w `blocked-uri` zamiast adresu
_KEYWORDS = {"inline", "eval", "data", "blob", "wasm-eval", "self", "trusted-types-policy", "trusted-types-sink"}


def _rate_limited(ip: str) -> bool:
    now = time.time()
    for key, limit in ((ip, RATE_LIMIT_PER_IP_PER_MIN), ("*", RATE_LIMIT_GLOBAL_PER_MIN)):
        window = _hits[key] = [t for t in _hits[key] if now - t < 60]
        if len(window) >= limit:
            return True
    _hits[ip].append(now)
    _hits["*"].append(now)
    if len(_hits) > 5000:
        for k in [k for k, v in _hits.items() if not v and k != "*"]:
            del _hits[k]
    return False


def normalize_blocked(raw) -> str:
    """Zablokowane źródło → samo `schemat://host[:port]` albo słowo kluczowe. Ścieżka i zapytanie
    zdradzają za dużo (identyfikatory, tokeny), a do decyzji „co dopuścić" wystarczy host."""
    value = str(raw or "").strip()[:500]
    if not value:
        return "(brak)"
    lowered = value.lower()
    if lowered in _KEYWORDS:
        return lowered
    scheme = lowered.split(":", 1)[0]
    if scheme in ("data", "blob", "about", "javascript", "filesystem"):
        return scheme
    if "://" in value:
        try:
            parsed = urlparse(value)
            host = parsed.hostname
            if host:
                port = f":{parsed.port}" if parsed.port else ""
                return f"{parsed.scheme}://{host}{port}"[:120]
        except ValueError:
            pass
        return "(nieczytelne)"
    return (lowered.split()[0] if lowered.split() else "(brak)")[:120]


def normalize_page(raw) -> str:
    """Adres strony → sama ścieżka. Zapytanie i fragment nie wychodzą poza tę funkcję."""
    value = str(raw or "").strip()[:2000]
    if not value:
        return "/"
    try:
        path = urlparse(value).path or "/"
    except ValueError:
        return "/"
    return path[:200]


def normalize_directive(*candidates) -> str:
    for candidate in candidates:
        first = str(candidate or "").strip().lower().split(" ")[0]
        if _DIRECTIVE.match(first):
            return first
    return "inne"


def parse_reports(payload) -> list[dict]:
    """Wsad w obu formatach → lista `{directive, blocked, page, disposition}`; śmieci znikają."""
    raw_reports: list[dict] = []
    if isinstance(payload, dict) and isinstance(payload.get("csp-report"), dict):
        r = payload["csp-report"]
        raw_reports.append({
            "directive": normalize_directive(r.get("effective-directive"), r.get("violated-directive")),
            "blocked": r.get("blocked-uri"),
            "page": r.get("document-uri"),
            "disposition": r.get("disposition"),
        })
    elif isinstance(payload, list):
        for item in payload[:MAX_REPORTS_PER_REQUEST]:
            body = item.get("body") if isinstance(item, dict) and item.get("type") == "csp-violation" else None
            if isinstance(body, dict):
                raw_reports.append({
                    "directive": normalize_directive(body.get("effectiveDirective"), body.get("violatedDirective")),
                    "blocked": body.get("blockedURL") or body.get("blockedURI"),
                    "page": body.get("documentURL") or body.get("documentURI"),
                    "disposition": body.get("disposition"),
                })
    return [
        {
            "directive": r["directive"],
            "blocked": normalize_blocked(r["blocked"]),
            "page": normalize_page(r["page"]),
            "disposition": "enforce" if str(r.get("disposition") or "").lower() == "enforce" else "report",
        }
        for r in raw_reports[:MAX_REPORTS_PER_REQUEST]
    ]


async def store(session, report: dict, now: datetime) -> bool:
    """Zwiększa licznik istniejącego wpisu albo dodaje nowy — o ile nie przekroczono sufitu.
    Zwraca, czy raport został zapisany."""
    updated = await session.execute(
        text("""
            UPDATE csp_violations SET hits = hits + 1, last_seen = :now
            WHERE directive = :directive AND blocked = :blocked AND page = :page
        """),
        {**report, "now": now},
    )
    if updated.rowcount:
        return True
    distinct = (await session.execute(text("SELECT count(*) FROM csp_violations"))).scalar()
    if distinct >= MAX_DISTINCT:
        return False
    await session.execute(
        text("""
            INSERT INTO csp_violations (directive, blocked, page, disposition, hits, first_seen, last_seen)
            VALUES (:directive, :blocked, :page, :disposition, 1, :now, :now)
            ON CONFLICT (directive, blocked, page) DO UPDATE SET hits = csp_violations.hits + 1, last_seen = :now
        """),
        {**report, "now": now},
    )
    return True


@router.post("", status_code=204)
async def collect(request: Request):
    """Przyjmij raport(y) CSP z przeglądarki. Zawsze 204."""
    ip = request.client.host if request.client else "?"
    if _rate_limited(ip):
        return Response(status_code=204)

    try:
        declared = int(request.headers.get("content-length") or 0)
    except ValueError:
        declared = 0
    if declared > MAX_BODY_BYTES:
        return Response(status_code=204)
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        return Response(status_code=204)

    try:
        reports = parse_reports(json.loads(body))
    except (ValueError, UnicodeDecodeError):
        return Response(status_code=204)
    if not reports:
        return Response(status_code=204)

    try:
        now = datetime.utcnow()
        async with async_session() as session:
            for report in reports:
                await store(session, report, now)
            await session.commit()
    except Exception as exc:  # noqa: BLE001 — raportowanie nie może przewrócić żądania
        logger.warning("Nie zapisano raportu CSP (%d szt.): %s", len(reports), exc)

    return Response(status_code=204)
