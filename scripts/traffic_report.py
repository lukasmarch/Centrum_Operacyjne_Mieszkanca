#!/usr/bin/env python3
"""Raport ruchu na rybnolive.pl z logu dostępu Caddy.

Po co: do 29.07.2026 nie istniał żaden zapis ruchu na stronie — ani w Caddy,
ani w uvicornie — więc pytanie „ile osób przyszło z kampanii na Facebooku"
nie miało źródła odpowiedzi. Log dostępu włączony w `Caddyfile` (blok `log`
piszący do `/data/access.log` w wolumenie `caddy_data`, retencja 7 dni) daje
komplet potrzebnych danych bez ciasteczek, bez GA4 i bez banera zgody.

Użycie:
    python3 scripts/traffic_report.py                # dziś
    python3 scripts/traffic_report.py --days 3       # ostatnie 3 dni, z podziałem
    python3 scripts/traffic_report.py --local plik   # gotowy log z dysku

Wejście na stronę = jedno żądanie zwrócone jako `text/html`. SPA ładuje
`index.html` raz na wejście, więc to jest najbliższy odpowiednik „sesji";
osobne żądania o assety, API i ikony są pomijane.

Kluczowa uwaga o tym, czego log NIE powie: dopóki `index.html` leciał
z `Cache-Control: immutable` (naprawione 29.07), powracający ludzie nie
odpytywali serwera wcale. Liczby z wcześniejszych dni byłyby zaniżone —
dlatego raport startuje od dnia naprawy.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

DEFAULT_HOST = "91.99.142.30"
LOG_PATH = "/data/access.log"
COMPOSE = "/opt/centrum/docker-compose.prod.yml"

# Roboty i podglądy linków. `facebookexternalhit` to nie odwiedzający — to
# Facebook pobierający og:image w chwili wklejenia linku. Liczony osobno, bo
# jego obecność potwierdza, że post z linkiem faktycznie powstał.
BOT_MARKERS = (
    "bot",
    "spider",
    "crawl",
    "curl/",
    "wget",
    "python-requests",
    "httpx",
    "headlesschrome",
    "lighthouse",
    "monitoring",
    "uptime",
)
LINK_PREVIEW_MARKERS = ("facebookexternalhit", "facebookcatalog", "whatsapp", "twitterbot")


def fetch_log(host: str) -> list[str]:
    """Czyta log z wolumenu Caddy przez SSH. Kontener nie ma pythona, więc
    parsowanie robimy lokalnie — serwer tylko wypisuje plik."""
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        f"root@{host}",
        f"docker compose -f {COMPOSE} exec -T caddy cat {LOG_PATH}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"Nie udało się odczytać logu: {proc.stderr.strip()}")
    return proc.stdout.splitlines()


def classify_source(referer: str) -> str:
    """Grupuje `Referer` do nazw, które da się porównać ze statystykami Mety.

    Facebook przepuszcza kliknięcia przez `l.facebook.com` (interstycjał
    ostrzeżeń) i `m.facebook.com` (aplikacja mobilna) — dla nas to jedno
    źródło. Puste `Referer` to wejście bezpośrednie, ale UWAGA: aplikacja
    Facebooka na iOS często nie przekazuje `Referer` wcale, więc część
    „bezpośrednich" to w rzeczywistości Facebook. Dlatego linki kampanijne
    dostają `utm_source` — to jedyny wiarygodny znacznik pochodzenia.
    """
    if not referer:
        return "bezpośrednie / bez Referera"
    netloc = urlparse(referer).netloc.lower().removeprefix("www.")
    if "facebook" in netloc or netloc == "fb.me":
        return "Facebook"
    if "instagram" in netloc:
        return "Instagram"
    if "google" in netloc:
        return "Google"
    if netloc.endswith("rybnolive.pl"):
        return "nawigacja wewnątrz strony"
    return netloc or "nieznane"


def is_page_view(entry: dict) -> bool:
    ctype = entry.get("resp_headers", {}).get("Content-Type", [""])[0]
    return entry.get("status") == 200 and ctype.startswith("text/html")


def main() -> None:
    ap = argparse.ArgumentParser(description="Raport ruchu na rybnolive.pl")
    ap.add_argument("--days", type=int, default=1, help="ile dni wstecz (domyślnie dziś)")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--local", help="ścieżka do pobranego logu zamiast SSH")
    args = ap.parse_args()

    if args.local:
        with open(args.local, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    else:
        lines = fetch_log(args.host)

    since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        days=args.days - 1
    )

    views: list[dict] = []
    previews = 0
    bots = 0

    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        when = datetime.fromtimestamp(entry.get("ts", 0))
        if when < since:
            continue

        req = entry.get("request", {})
        if req.get("host") != "rybnolive.pl":
            continue

        ua = (req.get("headers", {}).get("User-Agent") or [""])[0].lower()
        if any(m in ua for m in LINK_PREVIEW_MARKERS):
            previews += 1
            continue
        if any(m in ua for m in BOT_MARKERS):
            bots += 1
            continue
        if not is_page_view(entry):
            continue

        # keep_blank_values, bo `?alerty` nie ma wartości — bez tego parse_qs
        # wyrzuca go w całości i znacznik kampanijny nie liczy się nigdy
        query = parse_qs(urlparse(req.get("uri", "")).query, keep_blank_values=True)
        views.append(
            {
                "when": when,
                "ip": req.get("client_ip") or req.get("remote_ip", ""),
                "source": classify_source((req.get("headers", {}).get("Referer") or [""])[0]),
                "campaign": "alerty" in query,
                "utm_source": (query.get("utm_source") or [""])[0],
                "utm_medium": (query.get("utm_medium") or [""])[0],
                "utm_campaign": (query.get("utm_campaign") or [""])[0],
            }
        )

    okres = f"{since:%d.%m}–{datetime.now():%d.%m.%Y}" if args.days > 1 else f"{since:%d.%m.%Y}"
    print(f"\n  RUCH NA rybnolive.pl · {okres}")
    print("  " + "─" * 52)

    if not views:
        print("\n  Brak wejść w tym okresie.")
        if previews:
            print(f"  ({previews} × podgląd linku z Facebooka — post istnieje, ludzi brak)")
        if bots:
            print(f"  ({bots} × robot / monitoring)")
        print()
        return

    unikalne = len({v["ip"] for v in views})
    print(f"\n  Wejścia:            {len(views)}")
    print(f"  Unikalne urządzenia:{unikalne:>4}   (po IP — jedno IP może być całym domem)")
    print(f"  Z linku ?alerty:    {sum(1 for v in views if v['campaign']):>4}")
    if previews:
        print(f"  Podglądy linku FB:  {previews:>4}   (nie odwiedzający — bot pobierający og:image)")
    if bots:
        print(f"  Roboty pominięte:   {bots:>4}")

    print("\n  Skąd przyszli")
    for src, n in Counter(v["source"] for v in views).most_common():
        print(f"    {n:>4} · {src}")

    utm = Counter(
        f"{v['utm_source']}/{v['utm_medium']}" + (f"/{v['utm_campaign']}" if v["utm_campaign"] else "")
        for v in views
        if v["utm_source"]
    )
    if utm:
        print("\n  Znaczniki kampanijne (utm_source/medium)")
        for tag, n in utm.most_common():
            print(f"    {n:>4} · {tag}")
    else:
        print("\n  Brak wejść ze znacznikiem utm_* — bez nich nie odróżnisz")
        print("  posta ze strony od wgrania pliku do grupy.")

    if args.days > 1:
        print("\n  Po dniach")
        per_day = Counter(f"{v['when']:%d.%m}" for v in views)
        for day in sorted(per_day, key=lambda d: (d.split(".")[1], d.split(".")[0])):
            print(f"    {per_day[day]:>4} · {day}")

    print("\n  Godziny (dziś)")
    per_hour = Counter(v["when"].hour for v in views if v["when"].date() == datetime.now().date())
    for hour in sorted(per_hour):
        print(f"    {hour:02d}:00  {'█' * min(per_hour[hour], 40)} {per_hour[hour]}")

    print(
        "\n  Konwersja liczy się z bazy, nie z logu:\n"
        "    ssh root@%s \"docker compose -f %s exec -T db \\\n"
        "      psql -U centrum_user -d centrum_operacyjne -c \\\n"
        "      \\\"SELECT created_at, active FROM push_subscriptions ORDER BY created_at DESC LIMIT 10;\\\"\"\n"
        % (args.host, COMPOSE)
    )


if __name__ == "__main__":
    main()
