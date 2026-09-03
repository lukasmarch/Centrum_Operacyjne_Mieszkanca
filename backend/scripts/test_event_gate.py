"""
Weryfikacja bramki wyboru artykułów do ekstrakcji wydarzeń
(`ai/event_extractor.is_event_candidate`).

Bramka decyduje, czy artykuł w ogóle zostanie pokazany modelowi. Do 18.08.2026
była to biała lista trzech kategorii i przez to w kalendarzu nie było ANI JEDNEGO
wydarzenia sportowego — zapowiedź „Zarybinek MTB Classic" na 23.08 wisiała w bazie
z trzech źródeł od 14.08 i nigdy nie stała się wydarzeniem. Test pilnuje, żeby
regresja nie wróciła cicho: kategoria Sport MUSI przechodzić.

Druga część liczy, ile wpisów bramka przepuszcza na realnych danych — to jest
bezpośredni koszt w wywołaniach gpt-4o, więc ma być widoczny, a nie domyślany.

Użycie:
    cd backend && python -m scripts.test_event_gate          # same przypadki
    cd backend && python -m scripts.test_event_gate --db     # + realne wpisy
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Tuple

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from src.ai.event_extractor import is_event_candidate
from src.database.schema import Article

# (opis, kategoria, is_filler, is_promotional, czy ma przejść)
CASES: List[Tuple[str, str, bool, bool, bool]] = [
    # --- MUSI przejść ---------------------------------------------------------
    ("zawody MTB — regresja z 18.08.2026", "Sport", False, False, True),
    ("rajd rowerowy, turystyka", "Rekreacja", False, False, True),
    ("dożynki parafialne", "Kultura", False, False, True),
    ("sesja rady gminy", "Urząd", False, False, True),
    ("dni otwarte w szkole", "Edukacja", False, False, True),
    ("zapowiedziane zamknięcie drogi", "Transport", False, False, True),
    ("biała sobota, badania profilaktyczne", "Zdrowie", False, False, True),
    ("otwarcie nowego sklepu z godziną", "Biznes", False, False, True),

    # --- MUSI odpaść ----------------------------------------------------------
    ("wyłączenie prądu — ma własny push, nie kalendarz", "Awaria", False, False, False),
    ("obwieszczenie o działce", "Nieruchomości", False, False, False),
    ("post powitalny na fanpage'u", "Kultura", True, False, False),
    ("reklama ubezpieczeń wklejona w feed", "Biznes", False, True, False),
    ("filler w kategorii, która normalnie przechodzi", "Sport", True, False, False),
]


# (opis, tytuł, treść, locality, czy ma przejść)
#
# Bramka lokalności odsiewa najwięcej ze wszystkich: pomiar 3.09.2026 na 14 dniach
# dał 96 odrzuconych, z czego 10 wymieniało miejscowość z gminy Rybno. Ocena
# dotyczy ARTYKUŁU i bywa niedeterministyczna, więc nazwa w tekście ją przebija.
LOCALITY_CASES = [
    ("bieg w Kopaniarzach z oceną 0 ← realny wpis, wydarzenie uratował drugi post",
     "VI Leśny Nocny Bieg w Kopaniarzach zaprasza do udziału",
     "Zapraszamy na bieg w Kopaniarzach 5 września.", 0, True),
    ("turniej w Tuczkach z oceną 0",
     "Charytatywny Turniej Piłki Nożnej w Tuczkach",
     "Turniej odbył się w Tuczkach.", 0, True),
    ("piknik w Ciechanowie — cudzy powiat, nadal odpada",
     "Piknik rodzinny w Ciechanowie",
     "Impreza w Ciechanowie dla mieszkańców.", 0, False),
    ("festyn w Sierpcu z oceną 1 — odpada",
     "Festyn w Sierpcu", "Zapraszamy do Sierpca.", 1, False),
    ("wpis z gminy z poprawną oceną przechodzi jak dotąd",
     "Dożynki w Rybnie", "Święto plonów w Rybnie.", 3, True),
    ("brak oceny — decyduje dopiero ocena wydarzenia",
     "Zebranie wiejskie", "Spotkanie mieszkańców.", None, True),
]


def run_locality_cases() -> bool:
    print()
    print("=" * 72)
    print("BRAMKA LOKALNOŚCI — nazwa miejscowości przebija niską ocenę")
    print("=" * 72)

    failed = False
    for opis, tytul, tresc, locality, oczekiwane in LOCALITY_CASES:
        article = Article(
            source_id=1, title=tytul, content=tresc,
            url=f"https://example.test/{abs(hash(opis))}",
            category="Sport", is_filler=False, is_promotional=False,
            processed=True, locality=locality,
        )
        wynik = is_event_candidate(article)
        ok = wynik == oczekiwane
        failed = failed or not ok
        znak = "✓" if ok else "✗"
        strzalka = "przechodzi" if wynik else "odpada"
        print(f"  {znak} [locality={str(locality):<4}] {opis[:52]:<52} → {strzalka}")
        if not ok:
            print(f"      OCZEKIWANO: {'przechodzi' if oczekiwane else 'odpada'}")
    return failed


def run_cases() -> bool:
    print("=" * 72)
    print("BRAMKA EKSTRAKCJI WYDARZEŃ — przypadki brzegowe")
    print("=" * 72)

    failed = False
    for opis, kategoria, filler, promo, oczekiwane in CASES:
        article = Article(
            source_id=1,
            title=opis,
            url=f"https://example.test/{abs(hash(opis))}",
            category=kategoria,
            is_filler=filler,
            is_promotional=promo,
            processed=True,
        )
        wynik = is_event_candidate(article)
        ok = wynik == oczekiwane
        failed = failed or not ok
        znak = "✓" if ok else "✗"
        strzalka = "przechodzi" if wynik else "odpada"
        print(f"  {znak} [{kategoria:<14}] {opis[:46]:<46} → {strzalka}")
        if not ok:
            print(f"      OCZEKIWANO: {'przechodzi' if oczekiwane else 'odpada'}")

    print()
    print("WYNIK:", "BŁĄD" if failed else "wszystkie przypadki zgodne")
    return failed


async def run_db() -> None:
    """Ile wpisów z ostatnich 14 dni bramka przepuszcza — czyli ile kosztuje."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from src.config import settings

    print()
    print("=" * 72)
    print("REALNE DANE — 14 dni")
    print("=" * 72)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT category, is_filler, is_promotional, count(*) AS ile
              FROM articles
             WHERE scraped_at > now() - interval '14 days'
               AND category IS NOT NULL
             GROUP BY 1, 2, 3
        """))).fetchall()
    await engine.dispose()

    przeszlo, odpadlo = 0, 0
    per_kategoria: dict = {}
    for row in rows:
        article = Article(
            source_id=1, title="x", url="x",
            category=row.category,
            is_filler=row.is_filler,
            is_promotional=row.is_promotional,
            processed=True,
        )
        if is_event_candidate(article):
            przeszlo += row.ile
            per_kategoria[row.category] = per_kategoria.get(row.category, 0) + row.ile
        else:
            odpadlo += row.ile

    print(f"  przechodzi: {przeszlo:>4}   odpada: {odpadlo:>4}   "
          f"(~{przeszlo / 14:.1f} wywołań gpt-4o dziennie)")
    print()
    for kategoria, ile in sorted(per_kategoria.items(), key=lambda x: -x[1]):
        print(f"    {kategoria:<16} {ile:>4}")


if __name__ == "__main__":
    failed = run_cases()
    failed = run_locality_cases() or failed
    if "--db" in sys.argv:
        asyncio.run(run_db())
    sys.exit(1 if failed else 0)
