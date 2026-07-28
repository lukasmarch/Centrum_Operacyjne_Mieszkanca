"""
Weryfikacja polityki alertów push (`services/alert_policy.py`).

Dwie części:
  1. przypadki brzegowe — to, co MUSI przejść, i to, co MUSI odpaść;
  2. przebieg po realnych wpisach z bazy — pokazuje decyzję dla każdego,
     żeby dało się zobaczyć fałszywe trafienia zanim job ruszy na prodzie.

Użycie:
    cd backend && python -m scripts.test_alert_policy          # same przypadki
    cd backend && python -m scripts.test_alert_policy --db     # + realne wpisy
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from src.services import alert_policy

NOW = datetime(2026, 7, 27, 12, 0)
HOUR_AGO = NOW - timedelta(hours=1)

# (opis, tytuł, treść, event_at, event_until, oczekiwany rodzaj albo None)
CASES: List[Tuple[str, str, str, Optional[datetime], Optional[datetime], Optional[str]]] = [
    # --- MUSI przejść ---------------------------------------------------------
    (
        "wyłączenie prądu w Rybnie dziś po południu",
        "Wyłączenie planowe - Region Mława - Rybno gmina wiejska",
        "Rybno gmina wiejska 27.07.2026 14:00-18:00 - Rybno ulice Kolonia",
        NOW + timedelta(hours=2), NOW + timedelta(hours=6), "prad",
    ),
    (
        "wyłączenie zapowiedziane na jutro rano",
        "Wyłączenie planowane - Region Mława - Rybno gmina wiejska",
        "Tuczki 28.07.2026 08:00-12:00",
        NOW + timedelta(hours=20), NOW + timedelta(hours=24), "prad",
    ),
    (
        "awaria wodociągu w Koszelewach",
        "Awaria sieci wodociągowej w Koszelewach",
        "ZGK informuje o braku wody do godzin wieczornych.",
        None, None, "woda",
    ),
    (
        "pożar budynku w Żabinach",
        "Pożar budynku gospodarczego w Żabinach",
        "Na miejscu cztery zastępy straży pożarnej.",
        None, None, "pozar",
    ),
    (
        "wypadek z dzieckiem — trafiło do szpitala",
        "Wypadek na drodze w Rumianie",
        "Potrącone dziecko zostało przewiezione do szpitala w Działdowie.",
        None, None, "wypadek",
    ),
    (
        "trwające wyłączenie (zaczęło się godzinę temu)",
        "Wyłączenie bieżące - Region Mława - Rybno gmina wiejska",
        "Hartowiec 27.07.2026 11:00-15:00",
        HOUR_AGO, NOW + timedelta(hours=3), "prad",
    ),
    # --- MUSI odpaść ----------------------------------------------------------
    (
        "wyłączenie prądu w Płośnicy (obca gmina) ← przypadek z 27.07",
        "Wyłączenie planowane - Region Mława - Płośnica gmina wiejska",
        "Płośnica 27.07.2026 09:00-14:00 - Płośnica ulice Wiejska",
        NOW + timedelta(hours=1), NOW + timedelta(hours=4), None,
    ),
    (
        "wyłączenie w Działdowie",
        "Wyłączenie planowane - Region Mława - Działdowo gmina wiejska",
        "Działdowo 27.07.2026 09:00-14:00",
        NOW + timedelta(hours=1), NOW + timedelta(hours=4), None,
    ),
    (
        "zapowiedź wyłączenia za pięć dni — jeszcze nie budzimy",
        "Wyłączenie planowane - Region Mława - Rybno gmina wiejska",
        "Rybno 01.08.2026 08:00-14:00",
        NOW + timedelta(days=5), NOW + timedelta(days=5, hours=6), None,
    ),
    (
        "wyłączenie, które się skończyło",
        "Wyłączenie bieżące - Region Mława - Rybno gmina wiejska",
        "Rybno 27.07.2026 06:00-09:00",
        NOW - timedelta(hours=6), NOW - timedelta(hours=3), None,
    ),
    (
        "post OSP Rybno — nie jest zgłoszeniem pożaru",
        "Ochotnicza Straż Pożarna w Rybnie 💪🔥",
        "Nasza jednostka wzięła udział w zawodach sportowo-pożarniczych.",
        None, None, None,
    ),
    (
        "profilaktyka — 'Bezpieczna woda, bezpieczne wakacje'",
        "Bezpieczna woda - Bezpieczne wakacje",
        "Policjanci z Rybna przypominają o zasadach bezpieczeństwa nad wodą.",
        None, None, None,
    ),
    (
        "policyjne podsumowanie weekendu — powiat, nie gmina",
        "Weekend na drogach powiatu działdowskiego",
        "Doszło do trzech wypadków i dwunastu kolizji.",
        None, None, None,
    ),
    (
        "pożar sprzed trzech dni — relacja, nie ostrzeżenie",
        "Pożar stodoły w Rumianie",
        "W nocy z soboty na niedzielę spłonęła stodoła.",
        None, None, None,
    ),
    (
        "zgubione okulary na plaży w Hartowcu",
        "🔎 ZAGINĘŁY OKULARY – PROSZĘ O POMOC!",
        "Na plaży w Hartowcu zgubiłem okulary przeciwsłoneczne.",
        None, None, None,
    ),
    (
        "konkurs plastyczny o tematyce pożarowej",
        "Konkurs plastyczny dla dzieci z gminy Rybno",
        "Temat przewodni: zapobieganie pożarom w gospodarstwie.",
        None, None, None,
    ),
]


def run_cases() -> int:
    print("=" * 78)
    print("Przypadki brzegowe polityki alertów")
    print("=" * 78)

    failures = 0
    for label, title, content, event_at, event_until, expected in CASES:
        # Wpis „sprzed trzech dni" musi mieć starą publikację, reszta jest świeża
        published = NOW - timedelta(days=3) if "sprzed trzech dni" in label else HOUR_AGO
        alert = alert_policy.evaluate(
            title=title,
            content=content,
            published_at=published,
            scraped_at=HOUR_AGO,
            event_at=event_at,
            event_until=event_until,
            now=NOW,
        )
        got = alert.kind if alert else None
        ok = got == expected
        failures += not ok
        mark = "✓" if ok else "✗"
        detail = f"{got or '—'}" + (f" (oczekiwano {expected or '—'})" if not ok else "")
        places = f" [{', '.join(alert.places)}]" if alert else ""
        print(f"{mark} {label:.<58} {detail}{places}")

    print("-" * 78)
    print(f"{len(CASES) - failures}/{len(CASES)} zgodnych z oczekiwaniem")
    return failures


async def run_db():
    """Przepuszcza realne wpisy z bazy przez politykę — szuka fałszywych trafień."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    from src.config import settings

    print()
    print("=" * 78)
    print("Realne wpisy z bazy (ostatnie 7 dni)")
    print("=" * 78)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    now = datetime.utcnow()

    async with engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT a.id, a.title, a.content, a.summary, a.category,
                   a.published_at, a.scraped_at, a.event_at, a.event_until
            FROM articles a
            WHERE a.scraped_at > NOW() - INTERVAL '7 days'
              AND a.is_filler = false AND a.is_promotional = false
            ORDER BY a.scraped_at DESC
        """))).fetchall()

    hits = []
    for row in rows:
        alert = alert_policy.evaluate(
            title=row.title,
            content=row.content or row.summary,
            published_at=row.published_at,
            scraped_at=row.scraped_at,
            event_at=row.event_at,
            event_until=row.event_until,
            now=now,
        )
        if alert:
            hits.append((row, alert))

    print(f"Przejrzano {len(rows)} wpisów → alertów: {len(hits)}\n")
    for row, alert in hits:
        print(f"  [{alert.kind}] id={row.id} kat={row.category or '—'} "
              f"miejsca={', '.join(alert.places)}")
        print(f"      {(row.title or '')[:100]}")

    # Kontrola drugiej strony: awarie, których NIE wysyłamy — czy słusznie
    skipped = [r for r in rows if (r.category or "").lower().startswith("awari")
               and r.id not in {h[0].id for h in hits}]
    if skipped:
        print(f"\n  Kategoria 'Awaria' bez pusha ({len(skipped)}) — sprawdź, czy słusznie:")
        for row in skipped[:15]:
            print(f"      id={row.id} {(row.title or '')[:88]}")

    await engine.dispose()


if __name__ == "__main__":
    failed = run_cases()
    if "--db" in sys.argv:
        asyncio.run(run_db())
    sys.exit(1 if failed else 0)
