"""
Bramka substancji i cudzych awarii (9.10.2026).

Briefing otworzył dzień nagłówkiem „Tajemniczy incydent w Rybnie — brak
szczegółów”, bo wpis Syli (art. 6543) miał za całą treść „‼️‼️‼️” i link.
Reguły są deterministyczne, więc test nie woła modelu.

Użycie: python -m scripts.test_content_gate [--db]
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ai.summary_generator import _NO_DATA_RE
from src.services.feed_policy import (
    MIN_HEADLINE_LETTERS,
    has_substance,
    informative_letters,
    is_foreign_incident,
)

SUFFIX = "\n\nPełna treść u źródła: https://www.facebook.com/serwis/posts/pfbid02W3sNEbi82Q6gFERRL"
failures = 0


def check(label: str, got, expected) -> None:
    global failures
    ok = got == expected
    failures += 0 if ok else 1
    print(f"{'✓' if ok else '✗'} {label}: {got}" + ("" if ok else f" (oczekiwano {expected})"))


print("Bramka substancji")
check("same emoji + nasza doklejka z linkiem", has_substance("‼️‼️‼️", "‼️‼️‼️" + SUFFIX), False)
check("pusty tytuł i treść", has_substance("", ""), False)
check("jedno słowo wystarcza do feedu", has_substance("Awaria", ""), True)
check("emoji w tytule, słowa w treści", has_substance("‼️", "Brak wody na ul. Leśnej" + SUFFIX), True)
check(
    "link w treści nie jest słowem (art. 6543)",
    informative_letters("‼️‼️‼️", "‼️‼️‼️" + SUFFIX) < MIN_HEADLINE_LETTERS, True,
)
check(
    "pełne ogłoszenie otwiera briefing",
    informative_letters("Zebranie wiejskie", "Zapraszamy na zebranie wiejskie 17 września o 18:00 do świetlicy.") >= MIN_HEADLINE_LETTERS,
    True,
)

print("\nAwarie spoza gminy")
check("Księży Dwór, locality=2 (art. 6388)", is_foreign_incident("Awaria", "Planowane wyłączenie prądu — Księży Dwór", None, 2), True)
check("Rzemieślnicza w Rybnie, locality=2 (art. 6317)", is_foreign_incident("Awaria", "Awaria wodociągu na ulicy Rzemieślniczej w Rybnie", None, 2), False)
check("wyłączenie w gminie, locality=3", is_foreign_incident("Awaria", "Wyłączenie prądu — Żabiny", None, 3), False)
check("wiadomość nie-awaryjna spoza gminy nie jest tą regułą", is_foreign_incident("Bezpieczeństwo", "Zatrzymanie 17-latka w Przasnyszu", None, 0), False)

print("\nNagłówek ogłaszający brak wiedzy")
for text, expected in [
    ("Tajemniczy incydent w Rybnie - brak szczegółów na temat zdarzenia!", True),
    ("Szczegóły nie są jeszcze znane", True),
    ("Zagadkowe zdarzenie w gminie", True),
    ("Sesja Rady Gminy Rybno już w czwartek o 10:00", False),
]:
    check(f"„{text[:48]}”", bool(_NO_DATA_RE.search(text)), expected)


async def db_check() -> None:
    from sqlalchemy import select

    from src.database.connection import async_session
    from src.database.schema import Article
    from src.services.feed_policy import publishable_conditions

    async with async_session() as session:
        rows = (await session.execute(
            select(Article.id, Article.title).where(
                Article.processed == True,  # noqa: E712
                *publishable_conditions(Article),
            )
        )).all()
        bad = [r for r in rows if not has_substance(r.title, None)]
        print(f"\nBaza: {len(rows)} publikowalnych, w tym {len(bad)} bez słowa w tytule (treść może je ratować)")


if "--db" in sys.argv:
    asyncio.run(db_check())

print(f"\n{'✅ Wszystko zgodne' if not failures else f'✗ Błędów: {failures}'}")
sys.exit(1 if failures else 0)
