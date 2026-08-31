"""
Narzędzia wiedzy — wyszukiwarka i świeży feed (etap 3, 2026-08-24)

**Dlaczego wyszukiwarka staje się narzędziem.** Do dziś retrieval był podatkiem:
każde pytanie do Redaktora i Urzędnika płaciło za przepisanie zapytania,
wyszukiwanie hybrydowe i rerank, ZANIM ktokolwiek wiedział, czy materiał
z bazy jest w ogóle potrzebny. „Kto jest wójtem” przechodziło przez pełny
retrieval po to, żeby odpowiedź i tak wzięła się z karty gminy.

Odwrotnie też: model nie mógł poprosić o więcej. Dostawał jeden zestaw
fragmentów i musiał sobie z nim poradzić — nawet gdy z pierwszego wyniku
jasno wynikało, czego naprawdę szukać.

**Świeżość to nie zadanie dla wyszukiwarki — i to jest tu najważniejsze.**
9.08.2026 na „Co nowego w gminie?” retrieval zwrócił Działdowo z 2.08, Płośnicę
z 25.02, Lubowidz z 19.03, Stawigudę z 31.03 — same cudze gminy, najstarsza
sprzed pół roku. Model zachował się POPRAWNIE, nie podając tego jako nowin,
i odpowiedział „nie mam aktualnych artykułów”, mając w bazie 16 świeżych wpisów.
Pytanie ogólne nie ma słów, które cokolwiek wyróżniają, więc najbliższymi
sąsiadami wektora są chunki ze słowami „nowe” i „gmina”; `rag_recency_boost`
tego nie przebija.

Stąd DWA narzędzia, nie jedno:

* `search_news` / `search_documents` — pytanie o KONKRETNĄ sprawę;
* `latest_local_news` — pytanie o to, CO SŁYCHAĆ. Zwykłe zapytanie po dacie,
  ta sama polityka co feed i briefing.

Do 24.08 wybierał między nimi regex `_GENERIC_QUESTION` w `redaktor.py`.
Teraz wybiera model — ale opisy narzędzi mówią mu wprost, że wyszukiwarka
NIE nadaje się do pytania „co nowego”. Regułę przenieśliśmy z kodu do opisu,
nie wyrzuciliśmy jej.

**Czego tu NIE MA i dlaczego.** Przepisywania pytania (`_rewrite_query`).
Jego jedynym zadaniem było zamienić „a w zeszłym roku?” na samodzielne
zapytanie do wyszukiwarki — a w ścieżce narzędziowej zapytanie układa MODEL,
który historię rozmowy ma przed sobą. Jedno wywołanie gpt-4o-mini mniej
na każde pytanie.

**Co ZOSTAJE i dlaczego.** Rerank i synonimy. Oba kupione pomiarem:
bez reranku przy pytaniu o dowód osobisty wchodziły ogłoszenia o sesji rady
(kosinus ~0,5 przepuszcza szum), a „eternit” nie trafiał w dokument o azbeście
w ogóle, dopóki `expand_query` nie dopisało terminu urzędowego.

Test: `cd backend && python -m scripts.test_agent_tools --db`
"""
import json
from datetime import datetime, timedelta
from typing import Optional

import openai
from sqlalchemy import case, func, or_, select

from src.ai.embeddings import embedding_service
from src.services import provenance as prov
from src.ai.tools import Tool, ToolContext, ToolResult, register
from src.config import settings
from src.database.schema import Article, LegalAct, Source
from src.services.feed_policy import (
    article_score,
    article_scope,
    collapse_duplicates,
    dedup_text,
    publishable_conditions,
    time_label,
)
from src.services.feed_policy import word_stem
from src.services.search_synonyms import expand_query
from src.utils.logger import setup_logger

logger = setup_logger("KnowledgeTools")

# Klient dzielony przez narzędzia. Rerank chodzi na gpt-4o-mini niezależnie od
# tego, jakim modelem myśli agent — to zadanie klasyfikacyjne, nie redakcyjne.
_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Ile fragmentów pokazujemy modelowi. Powyżej tego kontekst zaczyna konkurować
# sam ze sobą — a każdy fragment to ~1,8 tys. znaków.
MAX_FRAGMENTS = 8

# Poniżej tej trafności fragment nie zasługuje na kafelek źródła w interfejsie.
# Niższy próg niż wyszukiwania: do odpowiedzi fragment może się przydać, do
# pokazania mieszkańcowi „to jest źródło” — już nie.
SOURCE_DISPLAY_MIN = 0.50

# Okno „co słychać”. Dwie doby, bo w sobotę rano pytanie dotyczy też piątku.
FEED_WINDOW_H = 48
FEED_MAX_ITEMS = 8
FEED_SUMMARY_CHARS = 110


async def _rerank(query: str, docs: list[dict], keep: int) -> list[dict]:
    """Listwise rerank: zostawia fragmenty, które FAKTYCZNIE pomagają odpowiedzieć.

    Kupione porażką: przy pytaniu o dowód osobisty kosinus ~0,5 przepuszczał
    ogłoszenia o sesji rady — podobny temat to za mało. Pusta lista jest
    poprawnym wynikiem i znaczy „odpowiedz z wiedzy ogólnej”.

    Błąd API zachowuje oryginalną kolejność: gorszy porządek jest lepszy
    niż brak odpowiedzi.
    """
    if len(docs) <= 1:
        return docs
    items = "\n".join(
        f"[{i}] {d['metadata'].get('title', '')} — {d['chunk_text'][:200]}"
        for i, d in enumerate(docs)
    )
    try:
        resp = await _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "Oceń, które fragmenty FAKTYCZNIE pomagają odpowiedzieć na pytanie. "
                    "Zwróć TYLKO JSON: listę indeksów trafnych fragmentów od najtrafniejszego, "
                    "np. [3,0,5]. Pomiń fragmenty niezwiązane z pytaniem (podobny temat to za mało "
                    "— fragment musi zawierać informację przydatną do odpowiedzi). "
                    "Jeśli żaden nie pasuje, zwróć []."
                )},
                {"role": "user", "content": f"PYTANIE: {query}\n\nFRAGMENTY:\n{items}"},
            ],
            temperature=0,
            max_tokens=60,
        )
        raw = (resp.choices[0].message.content or "").strip()
        start, end = raw.find("["), raw.rfind("]")
        indices = json.loads(raw[start:end + 1]) if start != -1 and end > start else []
        picked = [docs[i] for i in indices if isinstance(i, int) and 0 <= i < len(docs)]
        logger.info(f"Rerank: {len(docs)} kandydatów -> {len(picked)} trafnych")
        return picked[:keep]
    except Exception as e:
        logger.warning(f"Rerank nie zadziałał, zostawiam kolejność wyszukiwarki: {e}")
        return docs[:keep]


async def _search(
    ctx: ToolContext,
    query: str,
    *,
    source_types: list[str],
    top_k: int,
    threshold: float,
    semantic_weight: float,
    recency_boost: float,
    czego_szukam: str,
) -> ToolResult:
    """Wspólny trzon obu wyszukiwarek. Różnią się WYŁĄCZNIE korpusem i progami —
    a te były kalibrowane osobno na osobnych korpusach, więc jedno narzędzie
    z parametrem musiałoby wybrać jeden zestaw i popsuć drugi."""
    query = (query or "").strip()
    if not query:
        return ToolResult(
            content={"blad": "Puste zapytanie."}, error="bad_arguments"
        )

    # Mieszkaniec mówi „eternit”, BIP pisze „azbest” — embedding tych dwóch nie
    # łączy (0,674 dla „azbest”, zero trafień dla „eternit”). Termin urzędowy
    # jest DOPISYWANY, nie podmieniany: oryginał dalej pracuje w gałęzi BM25.
    expanded = expand_query(query)

    candidates = await embedding_service.hybrid_search(
        session=ctx.session,
        query=expanded,
        top_k=max(top_k * 2, 12),
        source_types=source_types,
        similarity_threshold=threshold,
        semantic_weight=semantic_weight,
        recency_boost=recency_boost,
    )
    docs = await _rerank(query, candidates, keep=min(top_k, MAX_FRAGMENTS))

    if not docs:
        return ToolResult(
            content={
                "info": f"Wyszukiwarka nie znalazła nic na temat: {query}",
                "co_powiedziec": (
                    "Powiedz wprost, że nie masz na to materiału w bazie, i dopiero "
                    "potem odpowiedz z wiedzy ogólnej — zaznaczając, że to wiedza "
                    "ogólna, a nie dokument gminy. Nie zmyślaj dat, numerów ani kwot."
                ),
            },
            empty=True,
            summary=f"brak trafień: {query[:40]}",
        )

    fragmenty, sources, seen = [], [], set()
    for doc in docs:
        meta = doc["metadata"]
        raw_date = meta.get("published_at", "") or meta.get("event_date", "")
        data = ""
        if raw_date:
            try:
                data = datetime.fromisoformat(
                    raw_date.replace("Z", "+00:00")
                ).strftime("%d.%m.%Y")
            except Exception:
                data = raw_date[:10]

        fragmenty.append({
            "tekst": doc["chunk_text"],
            "zrodlo": meta.get("source_name", doc["source_type"]),
            "tytul": meta.get("title", ""),
            "data": data or None,
            "trafnosc": round(doc["similarity"], 2),
        })

        # Kafelki źródeł idą OBOK odpowiedzi, nie przez model — przepisywanie
        # adresu URL było jedynym powodem, dla którego mógłby go przekręcić.
        key = f"{doc['source_type']}:{doc['source_id']}"
        if key not in seen and doc["similarity"] >= SOURCE_DISPLAY_MIN:
            seen.add(key)
            sources.append({
                "type": doc["source_type"],
                "id": doc["source_id"],
                "title": meta.get("title", ""),
                "url": meta.get("url", ""),
                "similarity": doc["similarity"],
            })

    return ToolResult(
        content={"czego_szukano": query, "fragmenty": fragmenty},
        sources=sources,
        summary=f"{len(fragmenty)} {czego_szukam}",
    )


async def search_news(ctx: ToolContext, query: str) -> ToolResult:
    """Wyszukiwarka po artykułach lokalnych."""
    return await _search(
        ctx, query,
        source_types=["article"],
        top_k=8, threshold=0.35, semantic_weight=0.90, recency_boost=0.25,
        czego_szukam="fragmentów artykułów",
    )


async def search_documents(ctx: ToolContext, query: str) -> ToolResult:
    """Wyszukiwarka po dokumentach BIP i urzędowych."""
    return await _search(
        ctx, query,
        source_types=["bip_static", "bip", "legal_act", "article"],
        top_k=6, threshold=0.40, semantic_weight=0.55, recency_boost=0.0,
        czego_szukam="fragmentów dokumentów",
    )


async def latest_local_news(ctx: ToolContext, hours: int = FEED_WINDOW_H) -> ToolResult:
    """Najnowsze wpisy serwisu — ta sama polityka treści co feed i briefing.

    To NIE jest wyszukiwarka i o to właśnie chodzi: zwykłe zapytanie po dacie,
    bez wektorów. Patrz docstring modułu, awaria z 9.08.
    """
    now = ctx.now
    hours = max(6, min(int(hours or FEED_WINDOW_H), 168))
    window_start = now - timedelta(hours=hours)

    result = await ctx.session.execute(
        select(Article, Source.name)
        .join(Source, Article.source_id == Source.id)
        .where(Article.processed == True)  # noqa: E712
        .where(*publishable_conditions(Article))
        .where(or_(Article.published_at >= window_start, Article.event_at >= now))
        .order_by(func.coalesce(Article.event_at, Article.published_at).desc())
        .limit(60)
    )
    rows = list(result)

    # Kolejność PRZED deduplikacją: `collapse_duplicates` zostawia wpis wcześniejszy
    # na liście, więc na nieposortowanej zostawiłaby przypadkowy.
    rows.sort(
        key=lambda row: article_score(
            row[0].published_at, row[0].scraped_at, row[1], now,
            row[0].event_at, row[0].event_until, row[0].content_score,
            row[0].locality, row[0].title, row[0].content,
        ),
        reverse=True,
    )
    rows = collapse_duplicates(rows, text_of=lambda row: dedup_text(row[0]))[:FEED_MAX_ITEMS]

    if not rows:
        return ToolResult(
            content={
                "info": f"Brak wpisów z ostatnich {hours} h.",
                "co_powiedziec": (
                    "Powiedz wprost, że w tym oknie czasowym nic nie przyszło. "
                    "Nie sięgaj po starsze wiadomości udając, że są nowe."
                ),
            },
            empty=True,
            summary=f"feed pusty ({hours} h)",
        )

    wpisy, lokalne, sources = [], 0, []
    for article, source_name in rows:
        summary = (article.summary or "").strip().replace("\n", " ")
        if len(summary) > FEED_SUMMARY_CHARS:
            summary = summary[:FEED_SUMMARY_CHARS].rstrip() + "…"
        # `article_scope`, nie `is_local_article`: ta druga mówi „nasz region"
        # i jest celowo szeroka (steruje rankingiem). Jako ETYKIETA kłamie —
        # blok komunalny w Działdowie szedł do mieszkańca jako „gmina Rybno".
        zasieg = article_scope(source_name, article.title, article.content)
        lokalne += zasieg == "gmina Rybno"
        wpisy.append({
            "kiedy": time_label(
                article.published_at, article.event_at, article.event_until, now
            ),
            "zasieg": zasieg,
            "tytul": article.display_title or article.title or "",
            "opis": summary or None,
            "kategoria": article.category or None,
        })

        # Kafelki źródeł — tak samo jak w `search_news` i `search_legal_acts`.
        # Do 24.08 to narzędzie ich NIE zwracało, więc odpowiedź na „co nowego"
        # jako jedyna szła bez ani jednego odnośnika: mieszkaniec dostawał
        # streszczenie wpisu i nie miał jak dojść do oryginału. `similarity`
        # jest sztywne 1.0 — tu nie ma podobieństwa do mierzenia, wpis wybrała
        # polityka feedu, a próg `source_display_threshold` na froncie musi go
        # przepuścić.
        if article.url:
            sources.append({
                "type": "article",
                "id": article.id,
                "title": (article.display_title or article.title or "")[:200],
                "url": article.url,
                "similarity": 1.0,
            })

    return ToolResult(
        content={
            "okno_godzin": hours,
            "w_gminie_rybno": lokalne,
            "wpisy": wpisy,
        },
        sources=sources,
        summary=f"{len(wpisy)} wpisów ({lokalne} z gminy)",
    )


# Zakres rejestru aktów. Mówimy o nim WPROST w każdej odpowiedzi z pustką —
# mieszkaniec pytający o uchwałę z 2019 r. musi wiedzieć, że jej u nas nie ma,
# a nie że jej nie ma w ogóle.
ACTS_SINCE_LABEL = "2024"

# Ile aktów naraz. Dziesięć to tyle, ile człowiek przeczyta w odpowiedzi czatu;
# przy większej liczbie i tak wybierze z pierwszych kilku.
ACTS_DEFAULT_LIMIT = 5
ACTS_MAX_LIMIT = 15

# Ile treści oddajemy przy LIŚCIE aktów — tyle, żeby model rozpoznał, o czym
# jest akt, i nie więcej: pięć uchwał po 8 tys. znaków wypchnęłoby wszystko inne.
ACTS_PREVIEW_CHARS = 400

# Ile treści oddajemy, gdy trafiony jest DOKŁADNIE JEDEN akt. Wtedy pytanie
# brzmi „o czym jest ta uchwała", a na to nie da się odpowiedzieć z zajawki.
#
# 24.08.2026: „możesz podsumować Uchwałę nr XXIII/180/2026" → agent poszedł do
# `search_documents`, bo rejestr oddawał mu 400 znaków. Wyszukiwarka wektorowa
# NIE ZNAJDUJE aktu po numerze (numer nie niesie sensu dla embeddingu), więc
# wróciła z fragmentami dwóch INNYCH uchwał, a agent uczciwie powiedział, że nie
# ma podsumowania. Miał je w zasięgu ręki przez cały czas.
ACTS_FULL_CHARS = 8000


async def search_legal_acts(
    ctx: ToolContext,
    query: Optional[str] = None,
    rodzaj: Optional[str] = None,
    rok: Optional[int] = None,
    limit: int = ACTS_DEFAULT_LIMIT,
) -> ToolResult:
    """Rejestr uchwał Rady i zarządzeń Wójta — po METADANYCH, nie po wektorach.

    **To jest cała racja bytu tego narzędzia.** „Jakie są najnowsze uchwały"
    nie ma słów wyróżniających, więc wyszukiwarka podobieństwa zwróciłaby
    przypadkowe akty sprzed lat — dokładnie ta sama porażka co przy pytaniu
    „co nowego" (9.08). Najnowsze uchwały to `ORDER BY adopted_at DESC`.

    `query` zawęża po tytule i treści zwykłym LIKE. Świadomie prymitywnie:
    do szukania „po sensie" jest `search_documents`, który czyta te same akty
    przez RAG. Tutaj chodzi o rejestr — numer, data, status.
    """
    limit = max(1, min(int(limit or ACTS_DEFAULT_LIMIT), ACTS_MAX_LIMIT))

    stmt = select(LegalAct)
    opis = []

    # Rodzaj to nie ozdoba: uchwała Rady i zarządzenie Wójta to dwa różne
    # rodzaje decyzji, o różnej mocy i różnym autorze. Mieszkaniec pytający
    # o uchwały nie chce dostać zarządzeń budżetowych.
    if rodzaj:
        low = rodzaj.strip().lower()
        if low.startswith("uchwal") or low.startswith("uchwał"):
            stmt = stmt.where(LegalAct.act_group.ilike("%Uchwały%"))
            opis.append("uchwały Rady")
        elif low.startswith("zarzadz") or low.startswith("zarządz"):
            stmt = stmt.where(LegalAct.act_group.ilike("%Zarządzenia%"))
            opis.append("zarządzenia Wójta")

    if rok:
        stmt = stmt.where(func.extract("year", LegalAct.adopted_at) == int(rok))
        opis.append(f"rok {rok}")

    if query and query.strip():
        # KAŻDE słowo musi wystąpić, ale niekoniecznie obok siebie. Dosłowne
        # dopasowanie frazy przegrywało z językiem urzędowym: „usuwanie azbestu”
        # nie trafia w „unieszkodliwianie wyrobów zawierających azbest”, choć
        # oba słowa w akcie są.
        for word in [w for w in query.strip().split() if len(w) > 2][:4]:
            like = f"%{word_stem(word)}%"
            stmt = stmt.where(or_(LegalAct.title.ilike(like),
                                  LegalAct.content.ilike(like),
                                  LegalAct.act_number.ilike(like)))
        opis.append(f"„{query.strip()}”")

    # Druga oś sortowania nie jest ozdobą: jedna sesja Rady podejmuje kilkanaście
    # uchwał TEGO SAMEGO DNIA (24.06.2026 — osiem), a sam `adopted_at DESC`
    # zwraca je wtedy w kolejności losowej. „Najnowsze uchwały” przestawały być
    # powtarzalne między dwoma wywołaniami tego samego pytania.
    # `bip_id` rośnie z kolejnością wprowadzania do rejestru, więc przybliża
    # kolejność podejmowania w obrębie dnia.
    porzadek = []
    if query and query.strip():
        # Gdy mieszkaniec PYTA O TEMAT, sama data nie wystarcza: akt, który ma
        # szukane słowa w TYTULE, jest o tym temacie; akt, który ma je gdzieś
        # w treści, wspomina o nim mimochodem. 25.08.2026 pytanie „plan ogólny"
        # zwracało pięć uchwał, wśród nich żadnej właściwej — jedyna uchwała
        # o planie ogólnym (III/20/2024) jest NAJSTARSZA w rejestrze i wypadała
        # poza limit, przepchnięta przez akty, które słowo „ogólny" mają
        # w uzasadnieniu.
        trafienia = sum(
            case((LegalAct.title.ilike(f"%{word_stem(w)}%"), 1), else_=0)
            for w in [w for w in query.strip().split() if len(w) > 2][:4]
        )
        porzadek.append(trafienia.desc())

    stmt = stmt.order_by(
        *porzadek, LegalAct.adopted_at.desc().nullslast(), LegalAct.bip_id.desc()
    ).limit(limit)
    acts = (await ctx.session.execute(stmt)).scalars().all()

    czego = " · ".join(opis) if opis else "najnowsze"

    if not acts:
        return ToolResult(
            content={
                "info": f"Brak aktów pasujących do: {czego}.",
                "zakres_rejestru": f"od {ACTS_SINCE_LABEL} r.",
                "co_powiedziec": (
                    f"UWAGA: pusty wynik dotyczy WYŁĄCZNIE tego zawężenia "
                    f"({czego}). Jeśli WCZEŚNIEJSZE wywołanie tego narzędzia coś "
                    f"zwróciło, odpowiedz z TAMTEGO wyniku — nie przedstawiaj "
                    f"własnego zawężenia jako braku aktu.\n"
                    f"Jeśli nic nie znalazłeś w żadnym wywołaniu: powiedz to WPROST "
                    f"i dodaj, że rejestr obejmuje akty od {ACTS_SINCE_LABEL} r. — "
                    f"starsze są w BIP Gminy Rybno (bip.gminarybno.pl, dział "
                    f"„Akty prawne”). NIE podawaj numeru ani daty uchwały z pamięci."
                ),
            },
            empty=True,
            summary=f"brak aktów: {czego}",
        )

    # Jeden trafiony akt = pytanie o TEN akt („podsumuj", „o czym jest").
    # Wtedy oddajemy treść, a nie zajawkę.
    pojedynczy = len(acts) == 1
    limit_tresci = ACTS_FULL_CHARS if pojedynczy else ACTS_PREVIEW_CHARS
    pole_tresci = "tresc_aktu" if pojedynczy else "poczatek_tresci"

    pozycje, sources = [], []
    for act in acts:
        pozycje.append({
            "numer": act.act_number,
            "rodzaj": act.act_group,
            "data_podjecia": act.adopted_at.isoformat() if act.adopted_at else None,
            "wchodzi_w_zycie": act.effective_from.isoformat() if act.effective_from else None,
            "status": act.status,
            "tytul": act.title,
            pole_tresci: (act.content or "")[:limit_tresci] or None,
        })
        sources.append({
            "type": "legal_act",
            "id": act.id,
            "title": f"{act.act_number or ''} — {act.title}".strip(" —")[:200],
            "url": act.url,
            "similarity": 1.0,
        })

    return ToolResult(
        content={
            "zakres_rejestru": f"akty od {ACTS_SINCE_LABEL} r.",
            "czego_szukano": czego,
            "akty": pozycje,
        },
        sources=sources,
        summary=f"{len(pozycje)} aktów ({czego})",
    )


register(Tool(
    name="search_news",
    provenance=prov.MEDIA,
    description=(
        "Szuka w archiwum artykułów lokalnych (gmina Rybno, powiat działdowski "
        "i okolice) fragmentów na KONKRETNY temat: nazwa miejscowości, imprezy, "
        "instytucji, inwestycji, klubu, osoby. Podaj `query` jako samodzielne "
        "zapytanie — jeśli mieszkaniec pyta „a co z tym”, rozwiń to na podstawie "
        "rozmowy. NIE UŻYWAJ do pytań ogólnych typu „co nowego”, „co słychać”, "
        "„co się wydarzyło” — wyszukiwarka podobieństwa zwraca wtedy przypadkowe "
        "stare wpisy z cudzych gmin; do tego służy latest_local_news."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Czego szukamy — samodzielne zapytanie, zrozumiałe bez "
                    "kontekstu rozmowy."
                ),
            },
        },
        "required": ["query"],
    },
    fn=search_news,
    status_message="Szukam w artykułach…",
    short="wyszukiwarka po artykułach lokalnych (konkretny temat, NIE „co nowego”)",
))

register(Tool(
    name="search_documents",
    provenance=prov.URZEDOWE,
    description=(
        "Szuka w dokumentach urzędowych: stałe działy BIP (statut, procedury, "
        "podatki i opłaty, ochrona środowiska i azbest, gospodarka odpadami, "
        "fundusz sołecki, porady prawne), obwieszczenia BIP oraz artykuły. "
        "Używaj do pytań o procedury, dokumenty, programy i decyzje gminy. "
        "Podaj `query` jako samodzielne zapytanie. Pisz językiem sprawy, nie "
        "cytatem pytania: mieszkaniec mówi „eternit”, dokument mówi „azbest” "
        "(synonimy są dopisywane automatycznie, ale trafny termin pomaga)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Czego szukamy — samodzielne zapytanie, zrozumiałe bez "
                    "kontekstu rozmowy."
                ),
            },
        },
        "required": ["query"],
    },
    fn=search_documents,
    status_message="Przeglądam dokumenty BIP…",
    short="wyszukiwarka po dokumentach BIP i urzędowych",
))

register(Tool(
    name="latest_local_news",
    provenance=prov.MEDIA,
    description=(
        "Najnowsze wpisy serwisu w kolejności, w jakiej widzi je mieszkaniec na "
        "stronie głównej — z datą, zasięgiem (gmina Rybno / okolice) i kategorią. "
        "TO JEST WŁAŚCIWE NARZĘDZIE do pytań „co nowego”, „co słychać”, "
        "„co się wydarzyło”, „podsumuj ostatnie wiadomości”. Nie jest wyszukiwarką: "
        "zwraca wszystko z okna czasowego, nie fragmenty pasujące do słów."
    ),
    parameters={
        "type": "object",
        "properties": {
            "hours": {
                "type": "integer",
                "description": (
                    "Okno wstecz w godzinach. Domyślnie 48 — w sobotę rano "
                    "pytanie „co nowego” dotyczy też piątku. Zakres 6–168."
                ),
            },
        },
        "required": [],
    },
    fn=latest_local_news,
    status_message="Sprawdzam najnowsze wpisy…",
    short="świeże wpisy serwisu po dacie (do pytań „co nowego”)",
))


register(Tool(
    name="search_legal_acts",
    provenance=prov.URZEDOWE,
    description=(
        "Rejestr aktów prawnych gminy: uchwały Rady Gminy i zarządzenia Wójta — "
        "wraz z TREŚCIĄ aktu. "
        "numer, data podjęcia, data wejścia w życie, status (Obowiązujący / "
        "Uchylony) i tytuł. TO JEST WŁAŚCIWE NARZĘDZIE do pytań „jakie są "
        "najnowsze uchwały”, „czy była uchwała o…”, „jaki numer ma uchwała "
        "o podatku od nieruchomości”. Bez argumentów zwraca NAJNOWSZE akty. "
        "Rejestr obejmuje akty od 2024 r. — starsze są tylko w BIP i musisz "
        "o tym powiedzieć, gdy nic nie znajdziesz.\n"
        "PYTANIE O KONKRETNY AKT („podsumuj uchwałę nr XXIII/180/2026”, „o czym "
        "jest to zarządzenie”) załatwiasz TUTAJ — podaj numer jako `query`. "
        "Gdy trafiony jest dokładnie jeden akt, dostajesz jego TREŚĆ w polu "
        "`tresc_aktu` i możesz ją streścić. NIE szukaj aktu po numerze przez "
        "search_documents: wyszukiwarka podobieństwa nie rozpoznaje numerów "
        "i zwróci fragmenty innych uchwał."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Zawężenie po tytule, treści lub numerze aktu. Dopasowanie "
                    "jest DOSŁOWNE, więc podaj jedno–dwa słowa klucza sprawy "
                    "(„azbest”, „podatek”, „budżet”), nie całe pytanie. "
                    "Pomiń, gdy pytanie brzmi „jakie są najnowsze”."
                ),
            },
            "rodzaj": {
                "type": "string",
                "enum": ["uchwały", "zarządzenia"],
                "description": (
                    "Uchwały Rady Gminy albo zarządzenia Wójta. To dwa różne "
                    "rodzaje decyzji — nie mieszaj ich, gdy mieszkaniec pyta "
                    "wyraźnie o jeden z nich."
                ),
            },
            "rok": {
                "type": "integer",
                "description": (
                    "Rok podjęcia aktu (2024–2026). Podawaj WYŁĄCZNIE wtedy, gdy "
                    "mieszkaniec sam wskazał rok. Dokładanie roku na własną rękę "
                    "zamienia trafny wynik w pustkę: uchwała o azbeście jest "
                    "z 2025 r., więc zawężenie do 2026 nie znajdzie nic."
                ),
            },
            "limit": {
                "type": "integer",
                "description": "Ile aktów zwrócić, domyślnie 5, maksymalnie 15.",
            },
        },
        "required": [],
    },
    fn=search_legal_acts,
    status_message="Przeglądam rejestr uchwał…",
    short="rejestr uchwał Rady i zarządzeń Wójta od 2024 r. (numer, data, status)",
))
