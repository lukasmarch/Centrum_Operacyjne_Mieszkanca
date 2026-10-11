"""
Sędzia sprawy: czy dwa wpisy z szarej strefy dedupu to ta sama sprawa (audyt 11.10.2026, E3c).

Dedup feedu (`feed_policy.same_story`) orzeka trzema osiami — termin, miejsce,
tekst/semantyka — i celowo NIE zwija par, w których dowód jest słaby. W szarej
strefie (cosinus ≥ 0,70 po wetach osi) leżą jednak przemieszane:
  - ta sama wiadomość dwóch redakcji („27-latek ranił policjanta w aptece”, 0,776),
  - dwie odsłony jednej sprawy (zapowiedź sesji Rady → relacja z obrad, 0,788),
  - RÓŻNE sprawy o tym samym temacie (różne mecze Dekorglassu, 0,74; wyłączenia
    prądu w dwóch różnych wsiach spoza gminy, 0,885 — tych weto miejsca nie widzi,
    bo `places_in` zna wyłącznie wsie gminy).
Żaden próg tego nie rozdziela. Rozdziela model czytający oba wpisy.

Pomiar przed wdrożeniem (40 par z 30 dni, ręcznie ocenionych, 2 przebiegi):
  **0/18 różnych spraw sklejonych**, 17–19/20 duplikatów i odsłon rozpoznanych,
  ~730 tokenów na parę (gpt-4o-mini) ≈ 3 centy miesięcznie. Pary i oceny:
  `scripts/fixtures/story_judge_pairs.json`, test `scripts/test_story_judge --live`.

⚠️ Prompt i obcinanie treści są TAKIE SAME jak w pomiarze. Zmiana któregokolwiek
unieważnia pomiar — przed wdrożeniem trzeba puścić `test_story_judge --live`.
⚠️ W razie wątpliwości sędzia ma mówić „inna”: błędne sklejenie UKRYWA informację
(mieszkaniec Turzy Małej traci komunikat o swojej wsi), niezwinięcie tylko ją powtarza.

Wynik zapisuje się raz (`articles.story_id` = id najstarszego wpisu sprawy,
`story_checked_at`) — po osadzeniu, w jobie embeddingów (6:50, 13:45), bo bez
osadzenia nie ma szarej strefy.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Awaitable, Callable, Optional

from sqlalchemy import select

from src.services.feed_policy import (
    _cosine,
    _place_axis,
    _term_axis,
    fetch_article_embeddings,
    same_story,
    story_key,
)
from src.utils.logger import setup_logger

logger = setup_logger("StoryJudge")

MODEL = "gpt-4o-mini"
GRAY_ZONE_MIN = 0.70          # poniżej: pomiar 30 dni — wyłącznie różne sprawy
PAIR_WINDOW = timedelta(days=3)
NEW_WINDOW = timedelta(days=3)
MAX_JUDGMENTS_PER_RUN = 60    # bezpiecznik kosztu; reszta czeka do następnego przebiegu
MAX_CANDIDATES_PER_ARTICLE = 5  # najbardziej podobne; sędzia i tak kończy na pierwszym trafieniu
CONTENT_CHARS = 380

SAME, UPDATE, DIFFERENT = "ta_sama", "odslona", "inna"

PROMPT = """Porównujesz dwa wpisy z lokalnego serwisu informacyjnego. Odpowiedz, czy opisują tę samą sprawę.

Werdykty:
- "ta_sama" — ta sama wiadomość o tym samym zdarzeniu (np. dwa źródła piszą o tym samym wypadku, tym samym otwarciu, tej samej decyzji), bez nowych faktów zmieniających sprawę.
- "odslona" — ta sama sprawa na innym etapie: zapowiedź i relacja z tego samego wydarzenia, ogłoszenie akcji i jej podsumowanie, zapowiedź sesji i jej wynik.
- "inna" — różne zdarzenia, nawet jeśli temat jest podobny: inne miejscowości, inne mecze, inne osoby, inne zwierzęta, inne firmy, ten sam typ zdarzenia w innym miejscu.

Zasady:
- Różna miejscowość, w której coś się dzieje (np. dwie różne wsie przy wyłączeniu prądu, dwie różne jednostki OSP) = "inna".
- Różni przeciwnicy w meczach, różne osoby, różne zwierzęta = "inna".
- W razie wątpliwości wybierz "inna" — błędne połączenie ukrywa informację przed mieszkańcem.

Odpowiedz wyłącznie JSON: {"werdykt": "ta_sama" | "odslona" | "inna", "powod": "<krótko>"}"""


def describe(article) -> str:
    """Wpis dla sędziego — dokładnie w postaci z pomiaru 11.10.2026."""
    title = getattr(article, "display_title", None) or getattr(article, "title", "")
    event_at = getattr(article, "event_at", None)
    content = ((getattr(article, "summary", None) or "") + " " + (getattr(article, "content", None) or ""))
    content = content[:CONTENT_CHARS].replace("\n", " ")
    return f"Tytuł: {title}\nTermin: {str(event_at) if event_at else 'brak'}\nTreść: {content}"


async def ask_model(a, b, session=None) -> Optional[str]:
    """Werdykt modelu albo None przy błędzie (para zostaje na następny przebieg)."""
    from openai import AsyncOpenAI
    from src.config import settings
    from src.utils.cost_tracker import log_api_cost

    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": f"WPIS A\n{describe(a)}\n\nWPIS B\n{describe(b)}"},
            ],
        )
        if session is not None and response.usage:
            log_api_cost(
                session, model=MODEL,
                tokens_input=response.usage.prompt_tokens or 0,
                tokens_output=response.usage.completion_tokens or 0,
                endpoint="scheduler:story_judge",
            )
        verdict = json.loads(response.choices[0].message.content).get("werdykt")
        return verdict if verdict in (SAME, UPDATE, DIFFERENT) else None
    except Exception as exc:  # noqa: BLE001 — sędzia nie może wywrócić jobu osadzania
        logger.error(f"Sędzia sprawy: błąd modelu ({type(exc).__name__}: {exc})")
        return None


def gray_zone_candidates(new, pool: list, keys: dict) -> list:
    """Starsze wpisy, z którymi `new` trzeba porównać sędzią — malejąco po podobieństwie.

    Czysta funkcja: weta osi zostają PRZED sędzią (inny termin, inne wsie gminy),
    pary zwinięte już przez osie pomijamy — feed i tak je łączy."""
    k_new = keys[new.id]
    if k_new.embedding is None:
        return []
    out = []
    for other in pool:
        if other.id == new.id:
            continue
        if (other.published_at, other.id) >= (new.published_at, new.id):
            continue  # porównujemy tylko ze STARSZYMI — każda para raz
        if new.published_at - other.published_at > PAIR_WINDOW:
            continue
        k_other = keys[other.id]
        if k_other.embedding is None:
            continue
        if _term_axis(k_new, k_other) is False or _place_axis(k_new, k_other) is False:
            continue
        if same_story(k_new, k_other):
            continue
        similarity = _cosine(k_new.embedding, k_other.embedding)
        if similarity >= GRAY_ZONE_MIN:
            out.append((similarity, other))
    out.sort(key=lambda pair: (-pair[0], pair[1].id))
    return [other for _sim, other in out[:MAX_CANDIDATES_PER_ARTICLE]]


async def link_new_stories(
    session,
    now: Optional[datetime] = None,
    judge: Optional[Callable[..., Awaitable[Optional[str]]]] = None,
    max_judgments: int = MAX_JUDGMENTS_PER_RUN,
) -> dict:
    """Ocenia wpisy osadzone, a jeszcze nie sprawdzone; łączy je ze starszymi w sprawy.

    `judge` wstrzykiwalny — testy podają atrapę zamiast modelu.
    Zwraca statystyki przebiegu.
    """
    from src.database.schema import Article

    now = now or datetime.utcnow()
    judge = judge or ask_model
    stats = {"checked": 0, "judged": 0, "linked": 0, "deferred": 0}

    new_rows = (await session.execute(
        select(Article).where(
            Article.processed == True,  # noqa: E712
            Article.embedded == True,  # noqa: E712
            Article.story_checked_at.is_(None),
            Article.published_at.isnot(None),
            Article.published_at >= now - NEW_WINDOW,
        ).order_by(Article.published_at, Article.id)
    )).scalars().all()
    if not new_rows:
        return stats

    pool = (await session.execute(
        select(Article).where(
            Article.processed == True,  # noqa: E712
            Article.published_at.isnot(None),
            Article.published_at >= now - NEW_WINDOW - PAIR_WINDOW,
        )
    )).scalars().all()
    by_id = {a.id: a for a in pool}
    embeddings = await fetch_article_embeddings(session, list(by_id))
    keys = {a.id: story_key(a, embeddings.get(a.id)) for a in pool}

    for new in new_rows:
        if new.id not in keys:
            continue
        candidates = gray_zone_candidates(new, pool, keys)
        if stats["judged"] + len(candidates) > max_judgments and candidates:
            stats["deferred"] += 1
            continue  # nie oznaczamy — wróci w następnym przebiegu
        failed = False
        for other in candidates:
            stats["judged"] += 1
            verdict = await judge(other, new, session=session)
            if verdict is None:
                failed = True
                break
            if verdict in (SAME, UPDATE):
                root = other.story_id or other.id
                other.story_id = root
                new.story_id = root
                # klucze w pamięci też — następny wpis z tego przebiegu widzi już sprawę
                keys[other.id] = story_key(other, embeddings.get(other.id))
                keys[new.id] = story_key(new, embeddings.get(new.id))
                stats["linked"] += 1
                logger.info(f"Sprawa {root}: {new.id} ↔ {other.id} ({verdict})")
                break
        if failed:
            continue  # błąd modelu — bez znacznika, spróbujemy ponownie
        new.story_checked_at = now
        stats["checked"] += 1

    await session.commit()
    logger.info(f"Sędzia sprawy: {stats}")
    return stats
