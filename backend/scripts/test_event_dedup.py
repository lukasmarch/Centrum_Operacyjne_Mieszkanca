"""
Weryfikacja bramek kalendarza wydarzeń (`ai/event_extractor.py`, `feed_policy`).

Trzy części:
  1. GROUNDING  — czy `ground_event` przycina odpowiedź modelu do tekstu:
                  relacja z przeszłości odpada, data bez śladu odpada,
                  miejsce spoza tekstu znika, locality=3 wymaga nazwy z gminy;
  2. BRAMKA MIEJSCA — czy `is_pinned_alert` przypina wyłącznie awarie z gminy
                  (21.08.2026 feed przypiął wyłączenie w Iłowie-Osadzie);
  3. BAZA (--db) — czy zapytanie dedupu w ogóle się wykonuje (patrz `find_duplicate`)
                  oraz czy w kalendarzu NIE MA już powtórek i wpisów spoza powiatu:
                  dla każdego dnia liczy pary widocznych wydarzeń o podobieństwie
                  ≥ progu. To jest test, który 20.08 wyłapałby maila z sześcioma
                  wersjami turnieju w Tuczkach.

Użycie:
    cd backend && python -m scripts.test_event_dedup           # bez bazy
    cd backend && python -m scripts.test_event_dedup --db      # + stan bazy
"""
import asyncio
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from src.ai.article_processor import SourceText
from src.ai.event_extractor import DUPLICATE_SIMILARITY, ground_event, _place_key
from src.ai.models import ExtractedEvent
from src.services.feed_policy import MIN_EVENT_LOCALITY, is_pinned_alert

NOW = datetime(2026, 8, 21, 6, 0)   # 08:00 czasu lokalnego


@dataclass
class _Ctx:
    """Minimalny RunContext — walidator sięga wyłącznie po `deps`."""
    deps: SourceText


# (opis, tekst źródłowy, odpowiedź modelu, co ma zostać)
GROUNDING_CASES = [
    (
        "zapowiedź z datą i miejscowością przechodzi",
        "Zapraszamy 23 sierpnia na turniej charytatywny w Tuczkach. Start o 9:00.",
        dict(is_event=True, is_upcoming=True, locality=3, title="Turniej w Tuczkach",
             event_date=datetime(2026, 8, 23, 9, 0), location="Tuczki"),
        dict(is_event=True, locality=3, location="Tuczki"),
    ),
    (
        "relacja z tego, co było, NIE jest wydarzeniem",
        "W sobotę 16 sierpnia odbyły się dożynki w Rumianie. Dziękujemy za przybycie!",
        dict(is_event=True, is_upcoming=False, locality=3, title="Dożynki w Rumianie",
             event_date=datetime(2026, 8, 16, 14, 0), location="Rumian"),
        dict(is_event=False),
    ),
    (
        "data bez śladu w tekście odpada",
        "Wkrótce zapraszamy na spotkanie w świetlicy. Szczegóły podamy później.",
        dict(is_event=True, is_upcoming=True, locality=3, title="Spotkanie",
             event_date=datetime(2026, 9, 12, 17, 0), location="Rybno"),
        dict(is_event=False),
    ),
    (
        "miejsce dopisane z nazwy firmy znika",
        "Restauracja RyBaśka zaprasza 30 sierpnia na koncert.",
        dict(is_event=True, is_upcoming=True, locality=2, title="Koncert",
             event_date=datetime(2026, 8, 30, 18, 0), location="Koszelewy"),
        dict(is_event=True, location=None),
    ),
    (
        "locality=3 bez nazwy z gminy schodzi do 2",
        "1 września w Sąpach koło Młynar odbędą się warsztaty zielarskie.",
        dict(is_event=True, is_upcoming=True, locality=3, title="Warsztaty",
             event_date=datetime(2026, 9, 1, 10, 0), location="Sąpy"),
        dict(is_event=True, locality=2),
    ),
]

# (opis, tytuł, event_at, locality, czy ma być przypięte)
PIN_CASES = [
    ("wyłączenie w gminie Rybno jutro rano",
     "Planowane wyłączenie prądu w gminie Rybno 22 sierpnia 2026 r",
     NOW + timedelta(hours=25), None, True),
    ("wyłączenie w Iłowie-Osadzie dziś (art. 5322)",
     "Planowana przerwa w dostawie prądu w Iłowo-Osada 21 sierpnia 2026",
     NOW + timedelta(minutes=30), None, False),
    ("wyłączenie w Działdowie (art. 5464)",
     "Planowane wyłączenie prądu w Działdowie 22 sierpnia 2026 r",
     NOW + timedelta(hours=25), None, False),
    ("ocena z kategoryzacji rozstrzyga przed tekstem (locality=3)",
     "Awaria sieci wodociągowej — komunikat ZGK",
     NOW + timedelta(hours=2), 3, True),
    ("ocena z kategoryzacji odrzuca wpis powiatowy (locality=2)",
     "Awaria sieci energetycznej w Rybnie i okolicy",
     NOW + timedelta(hours=2), 2, False),
]


def run_cases() -> int:
    failed = 0

    print("=" * 72)
    print("1. GROUNDING — odpowiedź modelu kontra tekst źródłowy")
    print("=" * 72)
    for label, text, payload, expected in GROUNDING_CASES:
        output = ExtractedEvent(**payload)
        ctx = _Ctx(deps=SourceText(title="", body=text))
        result = asyncio.run(ground_event(ctx, output))

        bad = {
            field: (getattr(result, field), want)
            for field, want in expected.items()
            if getattr(result, field) != want
        }
        if bad:
            failed += 1
            print(f"  ✗ {label}")
            for field, (got, want) in bad.items():
                print(f"      {field}: jest {got!r}, ma być {want!r}")
        else:
            print(f"  ✓ {label}")

    print()
    print("=" * 72)
    print("2. BRAMKA MIEJSCA — co feed przypina na górze")
    print("=" * 72)
    for label, title, event_at, locality, expected in PIN_CASES:
        pinned = is_pinned_alert(
            "Awaria", NOW - timedelta(days=1), NOW - timedelta(days=1), NOW,
            event_at, event_at + timedelta(hours=4), title, "", locality,
        )
        ok = pinned == expected
        failed += 0 if ok else 1
        mark = "✓" if ok else "✗"
        state = "przypięte" if pinned else "zwykły feed"
        print(f"  {mark} {label}: {state}")

    print()
    print("=" * 72)
    print("3. KLUCZ MIEJSCA — dopisek do nazwy to wciąż to samo miejsce")
    print("=" * 72)
    for a, b, same in [
        ("Ciechanów", "Ciechanów, dziedziniec Zamku Książąt Mazowieckich", True),
        ("Tuczki", "Tuczki", True),
        ("Rybno", "Hartowiec", False),
        ("Grądy", "Grądy, Gmina Rybno", True),
    ]:
        ok = (_place_key(a) == _place_key(b)) == same
        failed += 0 if ok else 1
        print(f"  {'✓' if ok else '✗'} „{a}” {'=' if same else '≠'} „{b}”")

    print()
    print(f"{'✓ Wszystko zielone' if not failed else f'✗ Błędów: {failed}'}")
    return failed


async def run_db() -> int:
    """Czy w widocznym kalendarzu zostały powtórki albo wpisy spoza powiatu."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from src.config import settings

    print()
    print("=" * 72)
    print("4. BAZA — stan widocznego kalendarza")
    print("=" * 72)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    failed = 0

    async with async_session() as session:
        # Najpierw samo ZAPYTANIE, dopiero potem jego wynik. `find_duplicate`
        # to jedyna funkcja nowej bramki rozmawiająca z bazą i do 22.08.2026
        # nie wołał jej żaden test: czternaście zielonych sprawdzeń grounding-u
        # przepuściło SQL, którego produkcja nie wykonała ani razu. Ekstraktor
        # woła ją zawsze bez wykluczenia i właśnie ta gałąź się wywracała, więc
        # `exclude_id` zostaje tu pusty celowo — z ID w środku zapytanie działa.
        from src.ai.event_extractor import find_duplicate

        probe = [0.0] * 1536
        probe[0] = 1.0
        try:
            await find_duplicate(session, probe, datetime.utcnow(), "Rybno")
            print("  ✓ find_duplicate wykonuje się bez wykluczenia (ścieżka ekstraktora)")
        except Exception as exc:
            failed += 1
            print(f"  ✗ find_duplicate(exclude_id=None) nie wykonało się: {exc}")
            await session.rollback()

        pairs = (await session.execute(text("""
            SELECT ea.id, eb.id, round((1 - (a.embedding <=> b.embedding))::numeric, 2),
                   left(ea.title, 40), left(eb.title, 40), date(ea.event_date),
                   ea.location, eb.location
            FROM events ea
            JOIN events eb ON ea.id < eb.id
                          AND date(ea.event_date) = date(eb.event_date)
            JOIN document_embeddings a ON a.source_type='event' AND a.source_id=ea.id
            JOIN document_embeddings b ON b.source_type='event' AND b.source_id=eb.id
            WHERE ea.canonical_id IS NULL AND eb.canonical_id IS NULL
              -- tylko to, co mieszkaniec faktycznie widzi
              AND (ea.locality IS NULL OR ea.locality >= :minimum)
              AND (eb.locality IS NULL OR eb.locality >= :minimum)
              AND ea.event_date >= now() - interval '7 days'
              AND 1 - (a.embedding <=> b.embedding) >= :threshold
            ORDER BY 3 DESC
        """), {"threshold": DUPLICATE_SIMILARITY, "minimum": MIN_EVENT_LOCALITY})).all()

        # Para o ZGODNYM miejscu to błąd pipeline'u — dedup miał ją scalić.
        # Para o różnym miejscu to sprawa dla człowieka: reguła miejsca celowo
        # nie scala w razie wątpliwości („Zagroda Edukacyjna w Sąpach" kontra
        # „Sąpy, gmina Młynary"), bo dwie różne imprezy tego samego dnia w tej
        # samej wsi kosztują więcej niż jedna powtórka.
        missed, review = [], []
        for row in pairs:
            key_a, key_b = _place_key(row[6]), _place_key(row[7])
            same_place = not (key_a and key_b) or key_a == key_b
            (missed if same_place else review).append(row)

        if missed:
            failed += 1
            print(f"  ✗ Powtórki wciąż widoczne ({len(missed)} par):")
            for id_a, id_b, sim, title_a, title_b, day, _, _ in missed[:15]:
                print(f"      {sim}  {day}  #{id_a} {title_a}  ==  #{id_b} {title_b}")
            print("    → python -m scripts.dedupe_events --apply")
        else:
            print("  ✓ Brak nierozstrzygniętych powtórek wśród widocznych wydarzeń (7 dni)")

        if review:
            print(f"  … do przejrzenia ({len(review)}): podobne, ale różne miejsce")
            for id_a, id_b, sim, title_a, title_b, day, loc_a, loc_b in review[:10]:
                print(f"      {sim}  {day}  #{id_a} {title_a} ({loc_a or '—'})")
                print(f"            == #{id_b} {title_b} ({loc_b or '—'})")

        # Sprawdzamy to, co mieszkaniec WIDZI — czyli wpisy przechodzące przez
        # `visible_event_conditions`. Wpis z oceną poniżej progu jest już ukryty
        # i nie jest błędem; błędem jest obcy ośrodek, który mimo bramki został.
        # Lista obcych ośrodków pochodzi z migracji — jedna na projekt.
        from scripts.migrations.add_locality_and_event_dedup import OBCE_PLACES
        from src.services.alert_policy import _flat

        visible = (await session.execute(text("""
            SELECT id, title, location, locality FROM events
            WHERE canonical_id IS NULL
              AND (locality IS NULL OR locality >= :minimum)
              AND event_date >= now()
            ORDER BY event_date LIMIT 200
        """), {"minimum": MIN_EVENT_LOCALITY})).all()

        far = [
            row for row in visible
            if any(name in _flat(f"{row[2] or ''} {row[1] or ''}") for name in OBCE_PLACES)
        ]
        hidden = (await session.execute(text("""
            SELECT count(*) FROM events
            WHERE canonical_id IS NULL AND locality IS NOT NULL AND locality < :minimum
        """), {"minimum": MIN_EVENT_LOCALITY})).scalar()

        if far:
            failed += 1
            print(f"  ✗ Obcy ośrodek WIDOCZNY w kalendarzu ({len(far)}):")
            for row in far:
                print(f"      #{row[0]} [{row[3]}] {row[1][:50]} ({row[2] or '—'})")
        else:
            print(f"  ✓ Żaden obcy ośrodek nie przechodzi bramki "
                  f"({len(visible)} widocznych, {hidden} ukrytych lokalnością)")

        stats = (await session.execute(text("""
            SELECT count(*) FILTER (WHERE canonical_id IS NULL),
                   count(*) FILTER (WHERE canonical_id IS NOT NULL),
                   count(*) FILTER (WHERE locality IS NULL)
            FROM events WHERE event_date > now() - interval '30 days'
        """))).one()
        print(f"\n  30 dni: widocznych {stats[0]}, scalonych {stats[1]}, "
              f"bez oceny lokalności {stats[2]}")

    await engine.dispose()
    return failed


if __name__ == "__main__":
    failures = run_cases()
    if "--db" in sys.argv:
        failures += asyncio.run(run_db())
    sys.exit(1 if failures else 0)
