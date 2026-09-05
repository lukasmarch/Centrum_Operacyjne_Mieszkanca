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

from src.ai.summary_generator import SummaryGenerator, _event_is_over, _time_label
from src.services.feed_policy import is_local_article, topic_signature

NOW = datetime(2026, 7, 29, 12, 0)

ENERGA = "Energa - wyłączenia planowane (RSS)"
RYBNO = "Facebook - Rybno"
OLSZTYN = "Radio Olsztyn (RSS)"
SYLA = "Facebook - Syla"
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
    # 25.08.2026: „Urząd" trzymał 28% całej treści — kronikę policyjną, zbiórki
    # i zguby — i konkurował z sesją rady o nagłówek dnia.
    (
        "kronika policyjna nie wygrywa z sesją Rady Gminy",
        [article(1, "Bezpieczeństwo", "Zatrzymanie złodzieja roweru w Działdowie",
                 KPP, published_h=2),
         article(2, "Urząd", "XXIV sesja Rady Gminy Rybno zaplanowana na 27 sierpnia",
                 published_h=8)],
        [], 2,
    ),
    (
        "zguba w Hartowcu nie wygrywa z posiedzeniem komisji",
        [article(1, "Społeczność", "Zgubione okulary w Hartowcu", published_h=1),
         article(2, "Urząd", "Posiedzenie Komisji Budżetu i Finansów w Rybnie",
                 published_h=20)],
        [], 2,
    ),
    (
        "apel prewencyjny policji nadal bije relację sportową",
        # KPP to źródło POWIATOWE — bez nazwy wsi wpis nie jest lokalny
        # i przegrywa lokalnością, zanim ktokolwiek spojrzy na priorytet
        [article(1, "Bezpieczeństwo", "Ostrzeżenie przed oszustami metodą na wnuczka w Rybnie",
                 KPP, published_h=4),
         article(2, "Sport", "Delfin Rybno przegrywa z MKS Działdowo", published_h=3)],
        [], 1,
    ),
    (
        "zapowiedziane wyłączenie drugi dzień z rzędu schodzi z nagłówka",
        [article(1, "Awaria", "Wyłączenie planowe - Region Mława - Rybno gmina wiejska",
                 ENERGA, 96, 4, 9),
         article(2, "Kultura", "Dożynki w Rybnie z korowodem", published_h=6)],
        ["Wyłączenie planowe - Region Mława - Rybno gmina wiejska"], 2,
    ),
    # 26.08.2026: odświeżenie o 13:30 otworzyło briefing zdaniem „Posiedzenie
    # Komisji Rozwoju Gospodarczego — już dziś o 12:00" (art. 5488, termin
    # półtorej godziny wcześniej), mając w materiale XXIV sesję Rady nazajutrz.
    # Dystans liczony bez kierunku robił z minionego terminu najbliższy punkt dnia.
    (
        "posiedzenie sprzed półtorej godziny ustępuje jutrzejszej sesji Rady",
        [article(1, "Urząd", "Posiedzenie Komisji Rozwoju Gospodarczego w Rybnie",
                 published_h=120, event_h=-1.5),
         article(2, "Urząd", "XXIV sesja Rady Gminy Rybno", published_h=120, event_h=20)],
        [], 2,
    ),
    (
        "minione posiedzenie ustępuje nawet lżejszej kategorii, byle nadchodzącej",
        [article(1, "Urząd", "Posiedzenie Komisji Rozwoju Gospodarczego w Rybnie",
                 published_h=120, event_h=-1.5),
         article(2, "Kultura", "Dożynki w Rybnie z korowodem",
                 published_h=48, event_h=80)],
        [], 2,
    ),
    (
        "minione posiedzenie wraca na nagłówek, gdy nic nie zostało przed nami",
        [article(1, "Urząd", "Posiedzenie Komisji Rozwoju Gospodarczego w Rybnie",
                 published_h=120, event_h=-1.5)],
        [], 1,
    ),
    # Oba przypadki celowo w JEDNEJ kategorii: inaczej o wyniku rozstrzyga
    # priorytet, a sprawdzamy tu wyłącznie, czy wpis dostał degradację „po terminie”.
    (
        "impreza trwająca (znany koniec) nie jest jeszcze „po”",
        [article(1, "Kultura", "Dożynki w Rybnie z korowodem",
                 published_h=48, event_h=-2, until_h=4),
         article(2, "Kultura", "Kiermasz w Rumianie", published_h=48, event_h=30)],
        [], 1,
    ),
    (
        "zapowiedź całodniowa trwa do końca swojej doby",
        # NOW to 29.07 12:00 UTC = 14:00 lokalnie; wpis bez godziny stoi w bazie
        # jako 28.07 22:00 UTC, czyli lokalna północ dnia dzisiejszego (−14 h).
        # Start jest za nami, ale dożynki dopiero trwają.
        [article(1, "Kultura", "Dożynki Gminne w Rybnie", published_h=48, event_h=-14),
         article(2, "Kultura", "Kiermasz w Rumianie", published_h=48, event_h=30)],
        [], 1,
    ),
    (
        "zapowiedź całodniowa z wczoraj jest już „po”",
        [article(1, "Kultura", "Dożynki Gminne w Rybnie", published_h=72, event_h=-38),
         article(2, "Kultura", "Kiermasz w Rumianie", published_h=48, event_h=90)],
        [], 2,
    ),
    (
        "trwające wyłączenie nie schodzi z nagłówka mimo minionego startu",
        [article(1, "Awaria", "Wyłączenie awaryjne - Region Mława - Rybno gmina wiejska",
                 "Energa - wyłączenia bieżące (RSS)", 3, -2, 3),
         article(2, "Urząd", "XXIV sesja Rady Gminy Rybno", published_h=120, event_h=20)],
        [], 1,
    ),

    # --- powtórka nagłówka przez awarię (3.09.2026) --------------------------
    # Briefingi 2 i 3.09 otworzyły się TĄ SAMĄ awarią wodociągową ZGK
    # (art. 5755, ogłoszoną 2.09 o 9:07 i nigdy nie odwołaną). Zwolnienie
    # z reguły powtórki przysługiwało wtedy każdej awarii, którą
    # `is_pinned_alert` uznawał za sprawę teraz — a bez godzin w treści
    # znaczyło to „przez cały AWARIA_PIN_HOURS od ogłoszenia".
    (
        "awaria bez dowodu trwania nie otwiera dnia drugi raz",
        [article(1, "Awaria", "Awaria sieci wodociągowej w Rybnie",
                 "Facebook - ZakladGospodarkiKomunalnej", published_h=20, locality=3),
         article(2, "Społeczność", "Pobór krwi w Rybnie", published_h=6, locality=3)],
        ["Awaria sieci wodociągowej w Rybnie"], 2,
    ),
    (
        "ta sama awaria, ale ze znanym terminem — trwa, więc zostaje",
        [article(1, "Awaria", "Awaria sieci wodociągowej w Rybnie",
                 "Facebook - ZakladGospodarkiKomunalnej",
                 published_h=20, event_h=-3, until_h=4, locality=3),
         article(2, "Społeczność", "Pobór krwi w Rybnie", published_h=6, locality=3)],
        ["Awaria sieci wodociągowej w Rybnie"], 1,
    ),
    (
        "świeża awaria bez terminu zostaje nagłówkiem mimo powtórki tematu",
        [article(1, "Awaria", "Awaria sieci wodociągowej w Rybnie",
                 "Facebook - ZakladGospodarkiKomunalnej", published_h=2, locality=3),
         article(2, "Społeczność", "Pobór krwi w Rybnie", published_h=1, locality=3)],
        ["Awaria sieci wodociągowej w Rybnie"], 1,
    ),
    (
        "awaria sprzed doby wraca, gdy dzień jest chudy i nie ma alternatywy",
        [article(1, "Awaria", "Awaria sieci wodociągowej w Rybnie",
                 "Facebook - ZakladGospodarkiKomunalnej", published_h=20, locality=3)],
        ["Awaria sieci wodociągowej w Rybnie"], 1,
    ),

    # --- lokalność nagłówka czyta ocenę kategoryzacji (3.09.2026) ------------
    # Po naprawie samego rankingu feedu briefing wciąż wybrał „Mieszkanki gminy
    # Rybno wspierają akcję zdrowotną w LUBAWIE" (art. 5774, locality=1, powiat
    # iławski), mając w materiale pobór krwi w Rybnie. `is_local_article`
    # przepuszcza każdy wpis Syli bez patrzenia w treść.
    (
        "wpis z locality=1 nie jest lokalny, choćby źródło było gminne",
        [article(1, "Zdrowie", "Mieszkanki gminy Rybno w akcji zdrowotnej w Lubawie",
                 SYLA, published_h=26, locality=1),
         article(2, "Społeczność", "Pobór krwi w Rybnie 16 września",
                 SYLA, published_h=20, locality=3)],
        [], 2,
    ),
    (
        "brak oceny — rozstrzyga źródło i nazwa w treści, jak dotąd",
        [article(1, "Zdrowie", "Akcja zdrowotna w Lubawie", SYLA, published_h=26),
         article(2, "Społeczność", "Piknik w Działdowie", "Moje Działdowo", published_h=20)],
        [], 1,
    ),
]


# (opis, artykuł, oczekiwana etykieta) — model czyta znacznik czasu przy wpisie
# i to on decyduje o czasie gramatycznym w briefingu
LABEL_CASES = [
    ("termin minął — model musi to wiedzieć",
     article(1, "Urząd", "Posiedzenie komisji", published_h=120, event_h=-1.5),
     "[ZDARZENIE dziś 12:30 — JUŻ PO]"),
    ("zdarzenie trwa",
     article(2, "Awaria", "Wyłączenie", ENERGA, 3, -2, 3),
     "[ZDARZENIE dziś 12:00–17:00 — TRWA TERAZ]"),
    ("zdarzenie przed nami",
     article(3, "Urząd", "Sesja Rady", published_h=120, event_h=20),
     "[ZDARZENIE jutro 10:00]"),
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
    """
    Dokładnie to, co briefing robi po zebraniu materiału — jego własną metodą.

    ⚠️ Do 3.09.2026 stała tu KOPIA reguły. Kopia rozjechała się z produkcją
    w dniu, w którym reguła zaczęła czytać `articles.locality`, i test
    sprawdzałby wtedy własną atrapę zamiast kodu, który idzie na serwer.
    """
    generator._mark_local_articles(articles)


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

    print()
    print("=" * 78)
    print("Znacznik czasu, który dostaje model")
    print("=" * 78)
    for label, item, expected in LABEL_CASES:
        got = _time_label(item, NOW)
        ok = got == expected
        failures += not ok
        detail = got + (f" (oczekiwano {expected})" if not ok else "")
        print(f"{'✓' if ok else '✗'} {label:.<48} {detail}")

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
                1 if _event_is_over(a, now) else 0,
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

    print("  lokalny po_terminie powtórka priorytet  dystans  kategoria")
    for locality, over, repeat, priority, distance, category, _id, item in ranking[:8]:
        print(f"  {'lok' if not locality else 'reg':>7} {over:>11} {repeat:>8} {priority:>9} "
              f"{distance:>7.1f}h  {category:<12} ID:{item.id} {(item.title or '')[:44]}")

    top = generator._select_top_article(grouped, now, recent_topics)
    print(f"\n→ NAGŁÓWEK: [ID:{top.id}] "
          f"[{'LOKALNY' if generator._is_local(top) else 'REGIONALNY'}] "
          f"kat={top.category}\n  {(top.title or '')[:100]}")


def run_window() -> int:
    """
    Okno materiału briefingu — doba LOKALNA, rozdzielona od klucza dnia (5.09.2026).

    Woła metodę PRODUKCYJNĄ `_material_window`, nie własną kopię reguły: kopia
    pod komentarzem „to samo, co briefing robi" już raz sprawdzała atrapę
    (`_local_article_ids`, 3.09). Klucz dnia zostaje północą UTC i test tego
    pilnuje — to etykieta dnia, nie chwila, a wisi na nim unikat kolumny
    i ścieżka `/api/summary/daily/{date}`.
    """
    from src.ai.summary_generator import SummaryGenerator

    print()
    print("=" * 78)
    print("Okno materiału briefingu a klucz dnia")
    print("=" * 78)

    KLUCZ = datetime(2026, 9, 5, 0, 0)          # `daily_summaries.date` — północ UTC
    POPOLUDNIE = datetime(2026, 9, 5, 11, 30)   # 13:30 lokalnie (przebieg odświeżający)
    RANO = datetime(2026, 9, 5, 5, 0)           # 7:00 lokalnie

    start, end = SummaryGenerator._material_window(POPOLUDNIE, KLUCZ)
    rano_start, rano_end = SummaryGenerator._material_window(RANO, KLUCZ)

    # Prawdziwe wpisy z dnia „VI Leśnego Nocnego Biegu"
    BIEG = datetime(2026, 9, 4, 22, 0)          # zapowiedź całodniowa na 5.09
    NOCNA_PUBLIKACJA = datetime(2026, 9, 4, 22, 30)   # 00:30 lokalnie 5.09
    WCZORAJ_WIECZOR = datetime(2026, 9, 4, 18, 0)     # 20:00 lokalnie 4.09

    checks = [
        ("okno zaczyna się o lokalnej północy", start, datetime(2026, 9, 4, 22, 0)),
        ("okno nie sięga w przyszłość", end, POPOLUDNIE),
        ("rano też nie sięga dalej niż teraz", rano_end, RANO),
        ("zapowiedź całodniowa NA DZIŚ jest w materiale",
         start <= BIEG < end, True),
        ("wpis z 00:30 lokalnie należy do dziś",
         start <= NOCNA_PUBLIKACJA < end, True),
        ("wczorajszy wieczór nadal poza oknem",
         start <= WCZORAJ_WIECZOR < end, False),
        # regresja, od której się zaczęło: granica w UTC gubiła zapowiedź
        ("stara granica UTC gubiłaby bieg",
         KLUCZ <= BIEG, False),
        # klucz dnia zostaje nietknięty
        ("klucz dnia to nadal północ UTC", KLUCZ.hour, 0),
        ("okno to NIE klucz", start == KLUCZ, False),
    ]

    failures = 0
    for label, got, expected in checks:
        ok = got == expected
        failures += not ok
        detail = f"{got}" + ("" if ok else f" (oczekiwano {expected})")
        print(f"{'✓' if ok else '✗'} {label:.<58} {detail}")

    print("-" * 78)
    print(f"{len(checks) - failures}/{len(checks)} zgodnych z oczekiwaniem")
    return failures


if __name__ == "__main__":
    failed = run_cases() + run_window()
    if "--db" in sys.argv:
        asyncio.run(run_db())
    sys.exit(1 if failed else 0)
