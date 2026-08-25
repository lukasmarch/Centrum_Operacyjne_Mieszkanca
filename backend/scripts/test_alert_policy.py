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

from src.services import alert_policy, feed_policy, time_span

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
    (
        # Energa grupuje po REJONACH, nie po gminach, a lista ulic przekracza
        # granice gmin: Gralewo leży w gminie Rybno, choć wpis opisano Płośnicą.
        # Dlatego bramka miejsca czyta TREŚĆ, nie etykietę gminy w tytule.
        "wyłączenie opisane Płośnicą, ale obejmuje Gralewo z naszej gminy",
        "Wyłączenie awaryjne - Region Mława - Płośnica gmina wiejska",
        "ENERGA-OPERATOR — TRWA przerwa w dostawie energii elektrycznej "
        "(wyłączenie prądu), 22.08.2026 07:26–13:00.\n\n"
        "Płośnica gmina wiejska 22.08.2026 07:26-13:00 - Gralewo, Gruszka.",
        HOUR_AGO, NOW + timedelta(hours=3), "prad",
    ),
    # --- MUSI odpaść ----------------------------------------------------------
    (
        # 22.08.2026, 9:34 — TO POSZŁO NAPRAWDĘ. „Wyłączenie prądu — Rybno,
        # dziś 06:21-13:00" z gminy Rybno w powiecie SOCHACZEWSKIM. Nazwa
        # miejscowości jest dosłownie ta sama, więc rozstrzyga rejon Energi:
        # powiat działdowski to zawsze Region Mława.
        "cudze Rybno spod Sochaczewa (Region Gostynin) ← przypadek z 22.08",
        "Wyłączenie awaryjne - Region Gostynin - Rybno gmina wiejska",
        "ENERGA-OPERATOR — TRWA przerwa w dostawie energii elektrycznej "
        "(wyłączenie prądu), 22.08.2026 06:21–13:00.\n\n"
        "Rybno gmina wiejska 22.08.2026 06:21-13:00 - Antosin, Koszajec, "
        "Matyldów, Rybionek, Wężyki.",
        HOUR_AGO, NOW + timedelta(hours=3), None,
    ),
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


# ── Termin wyczytany z treści ────────────────────────────────────────────────
# Osobna lista, bo tu liczy się DOKŁADNY moment publikacji i oceny — a `CASES`
# ustawia je sztywno. Przypadek pierwszy poszedł naprawdę: 24.08.2026 o 6:08
# push obudził sześć telefonów alarmem o wyłączeniu, które skończyło się
# poprzedniego dnia o 19:00.
ZGK_TITLE = "Zakład Gospodarki Komunalnej w Rybnie Sp z o o"
ZGK_BODY = (
    "Drodzy mieszkańcy! W godzinach 16.00 - 19.00 na terenie całego Rybna, "
    "nastąpi wyłączenie prądu. Woda będzie dostarczana z hydroforni."
)
ZGK_PUB = datetime(2026, 8, 23, 11, 0)  # 13:00 czasu lokalnego

# (opis, tytuł, treść, published_at, now, oczekiwany rodzaj)
SPAN_CASES: List[Tuple[str, str, str, datetime, datetime, Optional[str]]] = [
    (
        "post ZGK nazajutrz o 6:08 — zdarzenie minęło ← TO POSZŁO 24.08",
        ZGK_TITLE, ZGK_BODY, ZGK_PUB, datetime(2026, 8, 24, 6, 8), None,
    ),
    (
        "ten sam post w trakcie wyłączenia (16:30 lokalnie)",
        ZGK_TITLE, ZGK_BODY, ZGK_PUB, datetime(2026, 8, 23, 14, 30), "prad",
    ),
    (
        "ten sam post dwie godziny przed wyłączeniem",
        ZGK_TITLE, ZGK_BODY, ZGK_PUB, datetime(2026, 8, 23, 12, 0), "prad",
    ),
    (
        # Bezpiecznik `span_from_text`: zakres kończący się przed publikacją nie
        # jest terminem zdarzenia. Chroni godziny urzędowania w treści ogłoszenia
        # — bez tego „zgłoszenia przyjmujemy 7:00–15:00" w poście z 16:00
        # zamykałoby push o TRWAJĄCEJ awarii.
        "awaria zgłoszona po 15:00, w treści godziny przyjmowania zgłoszeń",
        "Awaria sieci wodociągowej w Rybnie",
        "Trwa usuwanie awarii. Zgłoszenia przyjmujemy w godzinach 7:00 - 15:00.",
        datetime(2026, 8, 23, 14, 0),  # 16:00 lokalnie, po „godzinach"
        datetime(2026, 8, 23, 15, 0), "woda",
    ),
    (
        # Regresja: awaria bez godzin w treści musi działać jak dotąd.
        "awaria wody bez godzin — świeża, przechodzi jak dotąd",
        "Awaria sieci wodociągowej w Koszelewach",
        "ZGK informuje o braku wody do godzin wieczornych.",
        datetime(2026, 8, 23, 11, 0), datetime(2026, 8, 23, 12, 0), "woda",
    ),
]

# Zapisy godzin, które parser MUSI rozumieć (dzień odniesienia = publikacja).
PARSE_CASES: List[Tuple[str, str, Optional[Tuple[int, int]]]] = [
    ("W godzinach 16.00 - 19.00 nastąpi wyłączenie", "kropka i spacje wokół myślnika", (14, 17)),
    ("Dziś, w godzinach 15:00–01:00", "dwukropek, półpauza, przez północ", (13, 23)),
    ("od godz. 8:00 do 14:00", "od…do", (6, 12)),
    ("Wyłączenie prądu w całym Rybnie", "brak godzin", None),
]


def run_span_cases() -> int:
    print()
    print("=" * 78)
    print("Termin wyczytany z treści komunikatu")
    print("=" * 78)

    failures = 0
    for text_in, label, expected in PARSE_CASES:
        start, end = time_span.parse_span(text_in, ZGK_PUB)
        got = (start.hour, end.hour) if start and end else None
        ok = got == expected
        failures += not ok
        print(f"{'✓' if ok else '✗'} parse: {label:.<50} "
              f"{got or '—'}{'' if ok else f' (oczekiwano {expected or chr(8212)})'}")

    for label, title, content, published, now, expected in SPAN_CASES:
        alert = alert_policy.evaluate(
            title=title, content=content,
            published_at=published, scraped_at=published,
            now=now,
        )
        got = alert.kind if alert else None
        ok = got == expected
        failures += not ok
        detail = f"{got or '—'}" + (f" (oczekiwano {expected or '—'})" if not ok else "")
        print(f"{'✓' if ok else '✗'} {label:.<58} {detail}")

    return failures


# ── Jeden komunikat = jedno powiadomienie ────────────────────────────────────
# 24.08.2026 o 6:08:30 i 6:08:31 poszły dwa pushe: post ZGK i jego przedruk
# na profilu Syli. Rozstrzyga sygnatura alertu (rodzaj + miejsca + termin),
# bo zwijanie po tekście tej pary nie łączy — kategoryzacja napisała im różne
# nagłówki, a to podobieństwo 0,43 przy progu 0,72.

# (opis, [(tytuł, treść, published_at)], ile RÓŻNYCH alertów)
SIGNATURE_GROUPS: List[Tuple[str, List[Tuple[str, str, datetime]], int]] = [
    (
        "komunikat ZGK i jego przedruk u Syli ← przypadek z 24.08",
        [
            (ZGK_TITLE, ZGK_BODY, ZGK_PUB),
            (
                "Serwis informacyjny Syla",
                "Zakład Gospodarki Komunalnej w Rybnie: w godzinach 16.00 - 19.00 "
                "na terenie Rybna wystąpi przerwa w dostawie prądu.",
                datetime(2026, 8, 23, 13, 8),
            ),
        ],
        1,
    ),
    (
        # 23.08 poszły o nich dwa powiadomienia (21:38 i 22:08). Ten sam dzień,
        # ta sama wieś, różne ulice — dla mieszkańca jedna wiadomość.
        "dwie zapowiedzi Energi na 25.08 w Rybnie — jeden alert",
        [
            (
                "Wyłączenie planowane - Region Mława - Rybno gmina wiejska",
                "Rybno gmina wiejska 25.08.2026 09:30-15:00 - Rybno ulica Wyzwolenia 90.",
                datetime(2026, 8, 21, 10, 19),
            ),
            (
                "Wyłączenie planowane - Region Mława - Rybno gmina wiejska",
                "Rybno gmina wiejska 25.08.2026 10:00-15:00 - Rybno ulice Kościelna 1, 3, 5.",
                datetime(2026, 8, 21, 10, 20),
            ),
        ],
        1,
    ),
    (
        # Miejscowość zostaje w kluczu — sąsiednia wieś to osobna sprawa.
        "wyłączenie w Rybnie i w Koszelewach tego samego dnia — dwa alerty",
        [
            (
                "Wyłączenie planowane - Region Mława - Rybno gmina wiejska",
                "Rybno gmina wiejska 25.08.2026 09:30-15:00 - Rybno ulica Wyzwolenia 90.",
                datetime(2026, 8, 21, 10, 19),
            ),
            (
                "Wyłączenie planowane - Region Mława - Rybno gmina wiejska",
                "Rybno gmina wiejska 25.08.2026 09:30-15:00 - Koszelewy, Koszelewki.",
                datetime(2026, 8, 21, 10, 21),
            ),
        ],
        2,
    ),
    (
        "awaria prądu i awaria wody tego samego dnia — dwa różne alerty",
        [
            ("Wyłączenie prądu w Rybnie", "W godzinach 16.00 - 19.00 nie będzie prądu.", ZGK_PUB),
            ("Awaria wodociągu w Rybnie", "W godzinach 16.00 - 19.00 nie będzie wody.", ZGK_PUB),
        ],
        2,
    ),
]

# Wyłączenia Energi mają termin z bazy (parsuje go `services/energa.py` przy
# scrapowaniu) — bez niego obie zapowiedzi na 25.08 miałyby ten sam klucz.
ENERGA_EVENTS = {
    "09:30-15:00": datetime(2026, 8, 25, 7, 30),
    "10:00-15:00": datetime(2026, 8, 25, 8, 0),
}


def run_signature_cases() -> int:
    print()
    print("=" * 78)
    print("Sygnatura alertu — co jest tym samym zdarzeniem")
    print("=" * 78)

    failures = 0
    for label, entries, expected in SIGNATURE_GROUPS:
        signatures = set()
        for title, content, published in entries:
            event_at = next(
                (dt for marker, dt in ENERGA_EVENTS.items() if marker in content), None
            )
            sig = alert_policy.signature(
                title=title, content=content,
                published_at=published, event_at=event_at,
            )
            if sig:
                signatures.add(sig)
        ok = len(signatures) == expected
        failures += not ok
        detail = f"{len(signatures)} z {len(entries)}"
        if not ok:
            detail += f" (oczekiwano {expected})"
        print(f"{'✓' if ok else '✗'} {label:.<58} {detail}")

    return failures


# (opis, lokalizacja konta, tytuł, treść, czy ma dotyczyć)
#
# Bramka miejsca dla KARTY ALERTU na stronie głównej (25.08.2026). Push miał ją
# od 24.08, strona nie miała jej wcale: mieszkaniec Żabin dostawał czerwoną ramkę
# o czterech adresach przy ulicy Wyzwolenia w Rybnie.
CONCERN_CASES = [
    (
        "wyłączenie w Rybnie a mieszkaniec Żabin",
        "Żabiny",
        "Wyłączenie planowe - Region Mława - Rybno gmina wiejska",
        "Rybno gmina wiejska 25.08.2026 09:30-15:00 - Rybno ulica Wyzwolenia 90.",
        False,
    ),
    (
        "wyłączenie w Rybnie a mieszkaniec Rybna",
        "Rybno",
        "Wyłączenie planowe - Region Mława - Rybno gmina wiejska",
        "Rybno gmina wiejska 25.08.2026 09:30-15:00 - Rybno ulica Wyzwolenia 90.",
        True,
    ),
    (
        'konto z rejonem wywozu „Rybno R2” to nadal Rybno',
        "Rybno R2",
        "Wyłączenie planowe - Region Mława - Rybno gmina wiejska",
        "Rybno gmina wiejska 25.08.2026 09:30-15:00 - Rybno ulica Wyzwolenia 90.",
        True,
    ),
    (
        "wyłączenie obejmujące kilka wsi — liczy się każda z nich",
        "Truszczyny",
        "Wyłączenie awaryjne - Region Mława - Rybno gmina wiejska",
        "Rybno gmina wiejska 19.08.2026 05:42-08:15 - Dębień, Hartowiec, Truszczyny.",
        True,
    ),
    (
        "ostrzeżenie meteo bez nazwy wsi dotyczy wszystkich",
        "Żabiny",
        "Ostrzeżenie meteorologiczne — burze z gradem",
        "IMGW-PIB wydał ostrzeżenie 1. stopnia dla powiatu działdowskiego.",
        True,
    ),
    (
        "gość bez konta widzi wszystko",
        None,
        "Wyłączenie planowe - Region Mława - Rybno gmina wiejska",
        "Rybno gmina wiejska 25.08.2026 09:30-15:00 - Rybno ulica Wyzwolenia 90.",
        True,
    ),
]


def run_concern_cases() -> int:
    print()
    print("=" * 78)
    print("Bramka miejsca karty alertu — czy to dotyczy MOJEJ wsi")
    print("=" * 78)

    failures = 0
    for label, location, title, content, expected in CONCERN_CASES:
        got = alert_policy.concerns(location, title, content)
        ok = got == expected
        failures += not ok
        detail = "dotyczy" if got else "nie dotyczy"
        if not ok:
            detail += f" (oczekiwano {'dotyczy' if expected else 'nie dotyczy'})"
        print(f"{'✓' if ok else '✗'} {label:.<58} {detail}")

    return failures


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
    failed += run_span_cases()
    failed += run_signature_cases()
    failed += run_concern_cases()
    if "--db" in sys.argv:
        asyncio.run(run_db())
    sys.exit(1 if failed else 0)
