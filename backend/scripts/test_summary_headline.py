"""
Weryfikacja wyboru nagłówka briefingu (`ai/summary_generator.SummaryGenerator`).

Nagłówek nie jest wyborem modelu — wskazuje go kod, a AI dostaje ten artykuł
jako „WYMAGANY ARTYKUŁ NAGŁÓWKA". Reguły są krótkie, ale zazębiają się z polityką
feedu (lokalność wpisu, próg „awaria jest sprawą teraz"), więc łatwo je zepsuć
niepozorną zmianą — stąd ten test.

Dwie części:
  1. przypadki brzegowe — kto MUSI wygrać nagłówek w danym układzie materiału;
  2. przebieg po realnym materiale z bazy (`--db`) — pokazuje ranking kandydatów
     na dziś, żeby zobaczyć decyzję, zanim job ruszy o 7:00.

Użycie:
    cd backend && python -m scripts.test_summary_headline          # same przypadki
    cd backend && python -m scripts.test_summary_headline --db     # + realny materiał
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional, Tuple

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from src.ai.summary_generator import SummaryGenerator
from src.services.feed_policy import is_local_article, topic_signature

NOW = datetime(2026, 7, 29, 12, 0)

ENERGA = "Energa - wyłączenia planowane (RSS)"
RYBNO = "Facebook - Rybno"
OLSZTYN = "Radio Olsztyn (RSS)"
RADIO7 = "Radio 7 Działdowo (RSS)"
KPP = "KPP Działdowo (RSS)"


def article(
    id: int,
    category: str,
    title: str,
    source: str = RYBNO,
    published_h: Optional[float] = None,
    event_h: Optional[float] = None,
    until_h: Optional[float] = None,
    locality: Optional[int] = None,
) -> SimpleNamespace:
    """Wpis w postaci, jakiej potrzebuje wybór nagłówka. Godziny względem NOW."""
    return SimpleNamespace(
        id=id,
        source_id=id,
        source_name=source,
        category=category,
        title=title,
        content="",
        summary=None,
        published_at=NOW - timedelta(hours=published_h) if published_h is not None else None,
        scraped_at=NOW - timedelta(hours=published_h or 0),
        event_at=NOW + timedelta(hours=event_h) if event_h is not None else None,
        event_until=NOW + timedelta(hours=until_h) if until_h is not None else None,
        # Od 21.08.2026 `_headline_priority` pyta o ocenę lokalności z kategoryzacji
        # (`articles.locality`). Domyślne None znaczy „wpis sprzed migracji" —
        # wtedy o miejscu rozstrzyga treść, dokładnie jak w produkcji.
        locality=locality,
    )


# (opis, materiał, tytuły nagłówków ostatnich briefingów, ID, które ma wygrać)
#
# Pamięć jest po TEMACIE, nie po ID — kolejne odświeżenie tego samego
# wyłączenia Energi dostaje nowy wiersz i nowe ID.
CASES: List[Tuple[str, List[SimpleNamespace], List[str], int]] = [
    (
        "awaria dziś (za 4 h) bije lokalną kulturę",
        [article(1, "Awaria", "Wyłączenie planowane w Rybnie", ENERGA, 20, 4, 9),
         article(2, "Kultura", "Koncert w świetlicy", published_h=2)],
        [], 1,
    ),
    (
        "awaria za dziewięć dni przegrywa z dzisiejszym transportem",
        [article(1, "Awaria", "Wyłączenie w Rybnie 7 sierpnia", ENERGA, 26, 216, 221),
         article(2, "Transport", "Zamknięcie drogi Tuczki – Koszelewy", published_h=3)],
        [], 2,
    ),
    (
        "awaria za dziewięć dni wygrywa, gdy nie ma nic innego",
        [article(1, "Awaria", "Wyłączenie w Rybnie 7 sierpnia", ENERGA, 26, 216, 221)],
        [], 1,
    ),
    (
        "zakończone wyłączenie nie jest nagłówkiem",
        [article(1, "Awaria", "Wyłączenie planowane w Rybnie", ENERGA, 30, -8, -2),
         article(2, "Sport", "Turniej w Rumianie", published_h=5)],
        [], 2,
    ),
    (
        "wyłączenie trwające od dwóch godzin wygrywa",
        [article(1, "Awaria", "Wyłączenie planowane w Rybnie", ENERGA, 30, -2, 3),
         article(2, "Transport", "Zamknięcie drogi", published_h=1)],
        [], 1,
    ),
    (
        "pożar bez terminu, sprzed dwóch godzin, wygrywa",
        [article(1, "Awaria", "Pożar stodoły w Naguszewie", published_h=2),
         article(2, "Zdrowie", "Dyżur apteki", published_h=1)],
        [], 1,
    ),
    (
        "wyłączenie w Płośnicy (feed powiatowy) przegrywa z lokalnym sportem",
        [article(1, "Awaria", "Wyłączenie - Region Mława - Płośnica gmina wiejska", ENERGA, 20, 4, 9),
         article(2, "Sport", "Turniej w Rumianie", published_h=6)],
        [], 2,
    ),
    (
        "wczorajszy nagłówek ustępuje innemu lokalnemu kandydatowi",
        [article(1, "Transport", "Zamknięcie drogi Tuczki – Koszelewy", published_h=1),
         article(2, "Urząd", "Nabór wniosków w gminie", published_h=6)],
        ["Zamknięcie drogi Tuczki – Koszelewy"], 2,
    ),
    (
        "wczorajszy nagłówek wraca, gdy alternatywą jest tylko regionalny",
        [article(1, "Transport", "Zamknięcie drogi Tuczki – Koszelewy", published_h=1),
         article(2, "Urząd", "Sesja rady w Olsztynie", OLSZTYN, published_h=2)],
        ["Zamknięcie drogi Tuczki – Koszelewy"], 1,
    ),
    (
        "trwająca awaria zostaje nagłówkiem, choć była nim wczoraj",
        [article(1, "Awaria", "Brak wody w Rybnie", ENERGA, 26, -20, 6),
         article(2, "Transport", "Zamknięcie drogi", published_h=1)],
        ["Brak wody w Rybnie"], 1,
    ),
    (
        "bez wpisów lokalnych wygrywa regionalny o wyższym priorytecie",
        [article(1, "Kultura", "Festyn w Mławie", OLSZTYN, published_h=2),
         article(2, "Zdrowie", "Nowy oddział szpitala", OLSZTYN, published_h=8)],
        [], 2,
    ),
    # Radio 7 i KPP obsługują cały powiat — od 11.08.2026 są w COUNTY_WIDE_SOURCES,
    # więc o lokalności wpisu rozstrzyga treść, nie nazwa źródła (audyt: 20 z 29
    # wpisów Radia 7 nie dotyczyło gminy, a briefing otwierał się nimi)
    (
        "wiadomość Radia 7 o Żurominie przegrywa z lokalnym wydarzeniem",
        [article(1, "Urząd", "Powiat żuromiński pozyskał 40 tys. zł dla seniorów",
                 RADIO7, published_h=1),
         article(2, "Kultura", "Festyn w Rumianie", published_h=8)],
        [], 2,
    ),
    (
        "wiadomość Radia 7 o gminie Rybno zostaje lokalna i wygrywa",
        [article(1, "Urząd", "Nowy chodnik w Rybnie oddany do użytku",
                 RADIO7, published_h=1),
         article(2, "Kultura", "Festyn w Mławie", OLSZTYN, published_h=2)],
        [], 1,
    ),
    (
        "komunikat KPP bez nazwy miejscowości przegrywa z lokalnym",
        [article(1, "Transport", "Zasady korzystania z hulajnóg elektrycznych",
                 KPP, published_h=1),
         article(2, "Urząd", "Nabór wniosków w gminie Rybno", published_h=9)],
        [], 2,
    ),
    # Energa odświeża zapowiedź co kilka godzin i każde odświeżenie to nowy wiersz.
    # Pamięć po ID tego nie widziała — to samo wyłączenie otwierało briefing
    # 7, 10 i 11.08.2026 (audyt: 43% nagłówków tygodnia to awarie)
    (
        "odświeżona zapowiedź wyłączenia (nowe ID, ten sam temat) nie wraca na nagłówek",
        [article(1, "Awaria", "Wyłączenie planowane - Region Mława - Rybno gmina wiejska",
                 ENERGA, 26, 120, 126),
         article(2, "Kultura", "Festyn w Rumianie", published_h=6)],
        ["Wyłączenie planowane - Region Mława - Rybno gmina wiejska - ul. Sportowa"], 2,
    ),
    (
        "temat sprzed trzech dni też blokuje, nie tylko wczorajszy",
        [article(1, "Urząd", "Nabór wniosków na fundusz sołecki w Rybnie", published_h=1),
         article(2, "Sport", "Turniej w Rumianie", published_h=10)],
        ["Koncert w świetlicy",
         "Nabór wniosków na fundusz sołecki w Rybnie"], 2,
    ),
    # 25.08.2026: briefing otworzył się zapowiedzianym wyłączeniem na czterech
    # adresach przy ul. Wyzwolenia, a konsultacje w sprawie skanalizowania trzech
    # wsi — tego samego dnia o 19:00 — wylądowały w bloku „Edukacja". Czwarty raz
    # w sześć dni. Zapowiedź ma odtąd `PLANNED_OUTAGE_PRIORITY`.
    (
        "zapowiedziane wyłączenie ustępuje sprawie, na którą trzeba dziś przyjść",
        [article(1, "Awaria", "Wyłączenie planowe - Region Mława - Rybno gmina wiejska",
                 ENERGA, 96, 4, 9),
         article(2, "Edukacja", "Konsultacje ws. skanalizowania Rumiana i Naguszewa",
                 published_h=300, event_h=12)],
        [], 2,
    ),
    (
        "wyłączenie AWARYJNE nie ustępuje niczemu — prąd zniknął sam",
        [article(1, "Awaria", "Wyłączenie awaryjne - Region Mława - Rybno gmina wiejska",
                 "Energa - wyłączenia bieżące (RSS)", 1, 4, 9),
         article(2, "Edukacja", "Konsultacje ws. skanalizowania Rumiana i Naguszewa",
                 published_h=300, event_h=12)],
        [], 1,
    ),
    (
        "zapowiedź, która właśnie TRWA, wraca na priorytet awarii",
        [article(1, "Awaria", "Wyłączenie planowe - Region Mława - Rybno gmina wiejska",
                 ENERGA, 96, -2, 3),
         article(2, "Edukacja", "Konsultacje ws. skanalizowania Rumiana i Naguszewa",
                 published_h=300, event_h=12)],
        [], 1,
    ),
    # Tytuł źródłowy Energi jest co dzień ten sam, więc dwie zapowiedzi pod rząd
    # `same_topic` widzi jako jedną sprawę. Do 25.08.2026 awaria była z tej reguły
    # zwolniona bez wyjątku i wygrywała nagłówek 4 dni z 6.
    (
        "zapowiedziane wyłączenie drugi dzień z rzędu schodzi z nagłówka",
        [article(1, "Awaria", "Wyłączenie planowe - Region Mława - Rybno gmina wiejska",
                 ENERGA, 96, 4, 9),
         article(2, "Kultura", "Dożynki w Rybnie z korowodem", published_h=6)],
        ["Wyłączenie planowe - Region Mława - Rybno gmina wiejska"], 2,
    ),
]


def _generator(source_names: dict) -> SummaryGenerator:
    """
    Generator gotowy do samego wyboru nagłówka.

    `__new__` zamiast `SummaryGenerator()` — konstruktor stawia klienta OpenAI,
    a wybór nagłówka jest czystą arytmetyką na wpisach i o model nie pyta.
    """
    generator = SummaryGenerator.__new__(SummaryGenerator)
    generator._source_names = source_names
    return generator


def _mark_local(generator: SummaryGenerator, articles: List) -> None:
    """To samo, co briefing robi po zebraniu materiału."""
    generator._local_article_ids = {
        a.id for a in articles
        if is_local_article(generator._source_names.get(a.source_id), a.title, a.content)
    }


def _by_category(articles: List) -> dict:
    grouped: dict = {}
    for item in articles:
        grouped.setdefault(item.category or "Inne", []).append(item)
    return grouped


def run_cases() -> int:
    print("=" * 78)
    print("Przypadki brzegowe wyboru nagłówka")
    print("=" * 78)

    failures = 0
    for label, articles, previous_headlines, expected in CASES:
        generator = _generator({a.source_id: a.source_name for a in articles})
        _mark_local(generator, articles)
        recent_topics = [topic_signature(title) for title in previous_headlines]
        chosen = generator._select_top_article(
            _by_category(articles), NOW, recent_topics
        )
        got = chosen.id if chosen else None
        ok = got == expected
        failures += not ok
        detail = f"ID:{got}" + (f" (oczekiwano ID:{expected})" if not ok else "")
        print(f"{'✓' if ok else '✗'} {label:.<62} {detail}")

    print("-" * 78)
    print(f"{len(CASES) - failures}/{len(CASES)} zgodnych z oczekiwaniem")
    return failures


async def run_db():
    """Ranking kandydatów na nagłówek z materiału, który briefing ma dziś na stole."""
    from src.database.connection import async_session

    print()
    print("=" * 78)
    print("Realny materiał z bazy")
    print("=" * 78)

    now = datetime.utcnow()
    date_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    async with async_session() as session:
        from sqlmodel import select
        from src.database.schema import Source

        rows = (await session.execute(select(Source.id, Source.name))).all()
        generator = _generator({row.id: row.name for row in rows})

        articles = await generator._fetch_articles(session, date_start, now)
        if len(articles) < 10:  # ten sam fallback co w briefingu
            articles = await generator._fetch_articles(
                session, date_start - timedelta(days=1), now
            )
        recent_topics = await generator._recent_headline_topics(session, date_start)

    if not articles:
        print("Brak materiału — briefing nie powstałby.")
        return

    _mark_local(generator, articles)

    grouped = _by_category(articles)
    print(f"Materiał: {len(articles)} wpisów w {len(grouped)} kategoriach")
    print(f"Tematy nagłówków z ostatnich {generator.HEADLINE_MEMORY_DAYS} dni: "
          f"{len(recent_topics)}\n")

    ranking = sorted(
        (
            (
                0 if generator._is_local(a) else 1,
                1 if generator._repeats_recent_headline(a, recent_topics) else 0,
                generator._headline_priority(category, a, now),
                generator._time_distance_h(a, now),
                category,
                # ID przed obiektem: dwa wyłączenia Energi o tym samym terminie
                # dawały remis na wszystkich polach, a wtedy sortowanie próbowało
                # porównać modele SQLModel i wywracało się na AttributeError
                a.id,
                a,
            )
            for category, arts in grouped.items()
            for a in arts
        )
    )

    print("  lokalny powtórka priorytet  dystans  kategoria")
    for locality, repeat, priority, distance, category, _id, item in ranking[:8]:
        print(f"  {'lok' if not locality else 'reg':>7} {repeat:>9} {priority:>9} "
              f"{distance:>7.1f}h  {category:<12} ID:{item.id} {(item.title or '')[:44]}")

    top = generator._select_top_article(grouped, now, recent_topics)
    print(f"\n→ NAGŁÓWEK: [ID:{top.id}] "
          f"[{'LOKALNY' if generator._is_local(top) else 'REGIONALNY'}] "
          f"kat={top.category}\n  {(top.title or '')[:100]}")


if __name__ == "__main__":
    failed = run_cases()
    if "--db" in sys.argv:
        asyncio.run(run_db())
    sys.exit(1 if failed else 0)
