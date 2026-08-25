"""
Weryfikacja mechanizmów przeciw halucynacjom kategoryzacji i briefingu.

Trzy klasy błędów z produkcji, na które prośby w promptach nie wystarczyły:
- 04.08.2026: 40-znakowy post „RyBaśka - Restauracja Rybna" dostał zmyślony
  nagłówek, summary i lokalizację Rybno (z przymiotnika „rybna");
- 12.08.2026: post o Nocy Perseidów BEZ żadnej daty dostał event_start,
  a highlights briefingu — „temperaturą sięgającą 23°C" wbrew zakazowi liczb;
- 12.08.2026: nabór na azbest w czterech redakcjach zajął trzy pierwsze
  miejsca feedu, bo dedup porównywał surowe teksty, nie temat.

Wszystko liczone kodem, zero wywołań modelu.

Użycie:
    cd backend && python -m scripts.test_grounding
"""
import asyncio
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from pydantic_ai import ModelRetry

from src.services import energa
from src.ai.article_processor import (
    MIN_CONTENT_CHARS,
    SourceText,
    _clean_title,
    _event_date_grounded,
    _is_low_content,
    _mentioned_in_text,
    ground_categorization,
)
from src.ai.models import ArticleCategory, DailySummary as DailySummaryModel
from src.ai.summary_generator import (
    _MEASUREMENT_RE,
    SummaryRun,
    validate_summary,
)
from src.services.alert_policy import _flat
from src.services.feed_policy import collapse_duplicates, dedup_text


@dataclass(eq=False)  # tożsamość, nie wartość — test sprawdza KTÓRY obiekt został
class FakeArticle:
    title: str = ""
    content: Optional[str] = None
    summary: Optional[str] = None
    display_title: Optional[str] = None
    event_at: Optional[datetime] = None


def category(**overrides) -> ArticleCategory:
    base = dict(
        primary_category="Urząd",
        confidence=0.9,
        summary="s",
        display_title="Tytuł",
    )
    base.update(overrides)
    return ArticleCategory(**base)


def run_grounding(cat: ArticleCategory, title: str, body: str) -> ArticleCategory:
    ctx = SimpleNamespace(deps=SourceText(title=title, body=body))
    return asyncio.run(ground_categorization(ctx, cat))


def run_summary_validator(out: DailySummaryModel, deps: SummaryRun):
    ctx = SimpleNamespace(deps=deps)
    try:
        return asyncio.run(validate_summary(ctx, out)), None
    except ModelRetry as retry:
        return None, retry


def summary_model(**overrides) -> DailySummaryModel:
    base = dict(
        date="2026-08-12",
        headline="Nagłówek",
        highlights="Spokojny dzień w gminie.",
        air_quality_summary="Pomiar z 7:00: CAQI 13",
        headline_importance_score=5,
        cited_article_ids=[],
    )
    base.update(overrides)
    return DailySummaryModel(**base)


RYBASKA_TITLE = "RyBaśka - Restauracja Rybna \U0001f44c\U0001f37d️ \U0001f41f"
FB_SUFFIX = "  Pełna treść u źródła: https://www.facebook.com/example/posts/123"

AZBEST = [
    FakeArticle(display_title="Nabór wniosków na usuwanie azbestu w Gminie Rybno do 19 sierpnia 2026 roku"),
    FakeArticle(display_title="Nabór wniosków na usuwanie azbestu w Gminie Rybno w 2026 roku"),
    FakeArticle(display_title="Nabór wniosków na utylizację azbestu w Rybnie na 2026 rok"),
    FakeArticle(display_title="Nabór wniosków o pomoc w usuwaniu azbestu ogłoszony przez Gminę Rybno"),
]
STYPENDIA = FakeArticle(
    display_title="Nabór wniosków o stypendia szkolne dla uczniów z gminy Rybno"
)
ENERGA_TITLE = "Wyłączenie planowane - Region Mława - Rybno gmina wiejska"


ENERGA_PLANOWANE = "Wyłączenie planowane - Region Mława - Rybno gmina wiejska"
ENERGA_A = energa.headline(
    ENERGA_PLANOWANE,
    "Rybno gmina wiejska 25.08.2026 10:00-15:00 - Rybno ulice Kościelna 1, 3, 5, "
    "Lubawska 1, 3, Stroma 1, Wyzwolenia 52A, 71, 72, 76A, 89, 91, 269/1, "
    "Zajeziorna 35, 37, 39, 41, 50, 52, 54, 56, 58.",
)
ENERGA_B = energa.headline(
    ENERGA_PLANOWANE,
    "Rybno gmina wiejska 25.08.2026 09:30-15:00 - Rybno ulica Wyzwolenia 90, 90/c, 90B, 94b.",
)
ENERGA_AWARIA = energa.headline(
    "Wyłączenie awaryjne - Region Mława - Płośnica gmina wiejska",
    "Płośnica gmina wiejska 22.08.2026 07:26-13:00 - Gralewo, Gruszka.",
)


def main() -> int:
    print("=" * 78)
    print("Grounding odpowiedzi modelu + próg krótkiej treści + dedup tematyczny")
    print("=" * 78)

    # -- walidator kategoryzacji ---------------------------------------------
    ghost_loc = run_grounding(
        category(locations_mentioned=["Rybno", "Działdowo"]),
        title="Remont świetlicy",
        body="W Działdowie wyremontowano świetlicę przy szkole.",
    )
    perseidy = run_grounding(
        category(event_start="2026-08-12T00:00"),
        title="Nicolaus Copernicus Foundation zaprasza na Lubawską Noc Perseidów",
        body="Dowiedź się więcej: https://gazetaolsztynska.pl/artykul/n2447085",
    )
    festyn = run_grounding(
        category(event_start="2026-08-27T15:00"),
        title="Festyn rodzinny",
        body="Zapraszamy 27 sierpnia o 15:00 na boisko w Rumianie.",
    )
    jutro = run_grounding(
        category(event_start="2026-08-13T18:00"),
        title="Zebranie wiejskie",
        body="Zebranie odbędzie się jutro o 18:00 w świetlicy.",
    )
    clamp = run_grounding(
        category(locality=3),
        title="Dotacje dla kół gospodyń",
        body="Samorząd województwa ogłosił nabór dla kół gospodyń wiejskich.",
    )
    wojt = run_grounding(
        category(locality=3),
        title="Nabór wniosków na usuwanie azbestu",
        body="Wójt Gminy Rybno ogłasza nabór wniosków dla mieszkańców.",
    )
    emoji_title = run_grounding(
        category(display_title="⚠️ UWAGA! Brak wody w Tuczkach!"),
        title="x",
        body="Brak wody w Tuczkach do odwołania." + " x" * 80,
    )

    # -- walidator briefingu -------------------------------------------------
    _, retry_temp = run_summary_validator(
        summary_model(highlights="Pogoda sprzyja, temperatura sięga 23°C po południu."),
        SummaryRun(),
    )
    _, retry_caqi = run_summary_validator(
        summary_model(highlights="Powietrze bardzo dobre, CAQI 20.76 rano."),
        SummaryRun(),
    )
    ok_dates, _ = run_summary_validator(
        summary_model(
            highlights="Nabór wniosków trwa do **19 sierpnia**. "
            "Dziś o 11:00 w Rumianie: poświęcenie pojazdów."
        ),
        SummaryRun(),
    )
    _, retry_required = run_summary_validator(
        summary_model(cited_article_ids=[5229, 5304]),
        SummaryRun(required_headline_id=5304, known_article_ids=frozenset({5229, 5304})),
    )
    filtered, _ = run_summary_validator(
        summary_model(cited_article_ids=[5304, 9999]),
        SummaryRun(required_headline_id=5304, known_article_ids=frozenset({5229, 5304})),
    )

    # -- dedup tematyczny ----------------------------------------------------
    feed = collapse_duplicates(
        AZBEST + [STYPENDIA], text_of=dedup_text
    )
    outage_a = FakeArticle(title=ENERGA_TITLE, content="Ulice: Leśna, Polna",
                           event_at=datetime(2026, 8, 20, 8, 0))
    outage_b = FakeArticle(title=ENERGA_TITLE, content="Ulice: Leśna, Polna",
                           event_at=datetime(2026, 8, 22, 9, 0))
    outage_a_refresh = FakeArticle(title=ENERGA_TITLE, content="Ulice: Leśna, Polna",
                                   event_at=datetime(2026, 8, 20, 8, 0))
    outages = collapse_duplicates(
        [outage_a, outage_b, outage_a_refresh], text_of=dedup_text
    )

    checks = [
        (
            "post RyBaśki (40 zn.) jest poniżej progu — model nie zostanie wywołany",
            _is_low_content(RYBASKA_TITLE, RYBASKA_TITLE + FB_SUFFIX),
            f"próg={MIN_CONTENT_CHARS}",
        ),
        (
            "doklejka „Pełna treść u źródła\" nie liczy się do progu",
            _is_low_content("Krótki post", "Krótki post" + FB_SUFFIX * 3),
            "sam sufiks nie robi z posta pełnej treści",
        ),
        (
            "krótki post ze słowem pilnym IDZIE do modelu",
            not _is_low_content("Uwaga", "Jutro brak wody na ul. Leśnej od 8:00"),
            "awaria w 40 znakach to pełnoprawna informacja",
        ),
        (
            "normalny artykuł idzie do modelu",
            not _is_low_content("Tytuł", "treść " * 40),
            "",
        ),
        (
            "tytuł RyBaśki po czyszczeniu: bez emoji, z nazwą",
            _clean_title(RYBASKA_TITLE) == "RyBaśka - Restauracja Rybna",
            repr(_clean_title(RYBASKA_TITLE)),
        ),
        (
            "lokalizacja spoza tekstu odpada (Rybno nie pada w Działdowie)",
            ghost_loc.locations_mentioned == ["Działdowo"],
            str(ghost_loc.locations_mentioned),
        ),
        (
            "rdzenie znoszą odmianę: „Rybno\" trafia w „w Rybnie\"",
            _mentioned_in_text("Rybno", _flat("spotkanie w Rybnie"))
            and not _mentioned_in_text("Rybno", _flat("spotkanie w Lidzbarku")),
            "",
        ),
        (
            "Perseidy: event_start bez śladu daty w tekście — odrzucony",
            perseidy.event_start is None and perseidy.event_end is None,
            str(perseidy.event_start),
        ),
        (
            "festyn „27 sierpnia o 15:00\": termin zostaje",
            festyn.event_start == "2026-08-27T15:00",
            str(festyn.event_start),
        ),
        (
            "„jutro o 18:00\": słowo względne wystarcza za ślad daty",
            jutro.event_start == "2026-08-13T18:00",
            str(jutro.event_start),
        ),
        (
            "locality 3→2, gdy w tekście nie pada nazwa z gminy",
            clamp.locality == 2,
            f"locality={clamp.locality}",
        ),
        (
            "„Wójt Gminy Rybno\" wystarcza za dowód lokalności (locality=3 zostaje)",
            wojt.locality == 3,
            f"locality={wojt.locality}",
        ),
        (
            "emoji i wykrzykniki znikają z display_title",
            emoji_title.display_title == "UWAGA BRAK WODY W TUCZKACH"
            or emoji_title.display_title == "UWAGA Brak wody w Tuczkach",
            repr(emoji_title.display_title),
        ),
        (
            "„23°C\" w highlights → ModelRetry",
            retry_temp is not None,
            str(retry_temp),
        ),
        (
            "„CAQI 20.76\" w highlights → ModelRetry",
            retry_caqi is not None,
            str(retry_caqi),
        ),
        (
            "daty i godziny w highlights są dozwolone",
            ok_dates is not None,
            "„19 sierpnia\", „11:00\" to nie liczby pomiarowe",
        ),
        (
            "nagłówek z innego artykułu niż wymagany → ModelRetry",
            retry_required is not None,
            str(retry_required),
        ),
        (
            "cytowanie spoza materiału odpada po cichu",
            filtered is not None and filtered.cited_article_ids == [5304],
            str(filtered.cited_article_ids if filtered else None),
        ),
        (
            "azbest w 4 redakcjach skleja się do 2, stypendia zostają",
            len([a for a in feed if "azbest" in (a.display_title or "")]) == 2
            and STYPENDIA in feed,
            f"feed po dedup: {[a.display_title[:40] for a in feed]}",
        ),
        (
            "dwa wyłączenia o RÓŻNYCH terminach to dwa wpisy",
            outage_a in outages and outage_b in outages,
            f"zostało {len(outages)}",
        ),
        (
            "odświeżenie tego samego wyłączenia (ten sam termin) skleja się",
            outage_a_refresh not in outages,
            f"zostało {len(outages)}",
        ),

        # --- tytuł wyłączenia składa kod, nie model (22.08.2026) --------------
        # Feed pokazał obok siebie „…w Rybnie 25 sierpnia 2026 roku" i „…w Rybnie
        # 25 sierpnia 2026" — czytało się to jak powtórka, a to były dwa różne
        # wyłączenia (inne godziny, inne ulice). Dedup słusznie ich nie scalił.
        (
            "dwa wyłączenia tego samego dnia mają ROZRÓŻNIALNE tytuły",
            ENERGA_A != ENERGA_B
            and "10:00–15:00" in ENERGA_A and "09:30–15:00" in ENERGA_B,
            f"{ENERGA_A!r} vs {ENERGA_B!r}",
        ),
        (
            "tytuł niesie ulice, czyli to, po czym mieszkaniec pozna swój dom",
            "Kościelna" in ENERGA_A and "Wyzwolenia" in ENERGA_B,
            ENERGA_A,
        ),
        (
            "numery domów nie wchodzą do tytułu",
            not any(znak.isdigit() for znak in ENERGA_A.split("—", 1)[1]),
            ENERGA_A.split("—", 1)[1].strip(),
        ),
        (
            "wyłączenie awaryjne nie podaje się za planowane",
            ENERGA_AWARIA.startswith("Wyłączenie prądu")
            and ENERGA_A.startswith("Planowane"),
            f"{ENERGA_AWARIA[:34]!r}",
        ),
        (
            "zwykły artykuł nie jest tytułowany jak wyłączenie",
            energa.headline("Zebranie wiejskie w Rybnie", "Zebranie 17 września.") is None,
            "None",
        ),
        # Feed pisze „Wyłączenie planowe" w 14 na 15 wpisów w bazie (pomiar
        # 25.08.2026), a warunek szukał wyłącznie formy „planowane" — czyli
        # praktycznie każda zapowiedź dostawała tytuł nieodróżnialny od awarii.
        # Energa zapisuje zakresy numerów słownie („Prusy od 1 do 5") i dorzuca
        # działki („dz. 174/12"). 25.08.2026 backfill chciał z tego zrobić
        # tytuły „Filice od do, dz." i „Księży Dwór od do".
        (
            "zakres numerów nie wchodzi do tytułu jako nazwa",
            energa.headline(
                "Wyłączenie planowe - Region Mława - Rybno gmina wiejska",
                "Rybno gmina wiejska 28.08.2026 09:00-14:00 - Prusy od 1 do 5, 5A, "
                "od 10 do 14, 19, Rybno ulica Lubawska 604/s.",
            ).endswith("— Prusy, Rybno"),
            'Prusy, Rybno — bez zakresu numerów',
        ),
        (
            'forma „planowe”, a nie „planowane”, też jest zapowiedzią',
            energa.is_planned("Wyłączenie planowe - Region Mława - Rybno gmina wiejska")
            and not energa.is_planned(
                "Wyłączenie awaryjne - Region Mława - Rybno gmina wiejska"
            ),
            "planowe → tak, awaryjne → nie",
        ),
    ]

    failures = 0
    for name, passed, detail in checks:
        mark = "✓" if passed else "✗"
        print(f" {mark} {name}")
        if not passed:
            failures += 1
            print(f"   → {detail}")

    print("=" * 78)
    if failures:
        print(f"BŁĘDY: {failures}/{len(checks)}")
        return 1
    print(f"OK: {len(checks)}/{len(checks)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
