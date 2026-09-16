"""
Polityka treści — jedno miejsce, w którym stoi, co pokazujemy i w jakiej kolejności.

Konsumenci: `/api/articles` (feed) i `ai/summary_generator.py` (briefing dnia).
Reguła projektu: żadnych prywatnych reguł treści u konsumentów. Briefing miał
własną listę źródeł lokalnych i żadnego filtra reklam — skutkiem był nagłówek
o zgubionych okularach i darmowa reklama restauracji w dniu premiery.

Cztery mechanizmy:
1. `article_score`        — odległość w czasie × waga źródła; dla zdarzeń z terminem
                            liczy się odległość do ZDARZENIA, nie wiek ogłoszenia
2. `is_pinned_alert`      — awaria na górze, dopóki jest sprawą „teraz"
3. `collapse_duplicates`  — ten sam materiał z dwóch źródeł pokazujemy raz
4. `diversify`            — przeplot: między wpisami z tego samego źródła
                            co najmniej SOURCE_GAP innych
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Callable, Iterable, Optional, TypeVar
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, cast, func, or_
from sqlalchemy.types import Time

from src.services.alert_policy import (
    incident_of,
    is_foreign_region,
    places_in,
    span_from_text,
)
from src.services.time_span import is_all_day, local_day_bounds, to_local, when_label
from src.services.weather_alert import expired as weather_alert_expired
from src.services.weather_alert import is_weather_alert

# Rozpad połowiczny świeżości: po 18 h wpis waży połowę tego, co świeży
FRESHNESS_HALFLIFE_H = 18.0

# Zdarzenia przyszłe (wyłączenie prądu za trzy dni) też tracą na wadze, tylko
# wolniej — zapowiedź na jutro musi wygrywać z zapowiedzią na przyszły tydzień
LOOKAHEAD_HALFLIFE_H = 48.0

# Ile innych wpisów musi dzielić dwa wpisy z tego samego źródła
SOURCE_GAP = 2

# Awaria bez znanego terminu trafia na górę feedu tylko dopóki jest „teraz".
#
# ⚠️ Doba była za długa i 3.09.2026 pokazała, na czym to polega: awaria
# wodociągowa ZGK ogłoszona 2.09 o 9:07 stała przypięta na szczycie jeszcze
# następnego dnia rano, choć prace naprawcze skończyły się poprzedniego dnia.
# ZGK nie publikuje „już działa", więc sygnału końca nie ma i nie będzie —
# jedyne, co możemy zrobić, to nie udawać, że wpis sprzed doby opisuje stan
# gminy TERAZ. Dwanaście godzin znaczy: awaria ogłoszona rano schodzi ze
# szczytu wieczorem, ogłoszona wieczorem — rano.
#
# Awarii ze ZNANYM terminem to nie dotyczy: tam rozstrzyga `event_until`
# (z kategoryzacji albo wyczytany z treści przez `alert_policy.span_from_text`),
# a wyłączenie zapowiedziane na osiem godzin jest przypięte przez całe osiem.
AWARIA_PIN_HOURS = 12

# Zdarzenie z terminem przypinamy dopiero, gdy jest na wyciągnięcie ręki.
# Bez tego wyłączenie zapowiedziane na przyszły czwartek stało cztery dni
# na szczycie feedu obok trzech innych i zabijało wszystkie wiadomości.
PIN_LOOKAHEAD_H = 30

# Twardy limit bloku przypiętego. Przy burzy Energa potrafi wypuścić kilkanaście
# wyłączeń naraz — feed nie może się zamienić w listę awarii.
MAX_PINNED = 3

# Ile trwa zapowiedź, która nie podała godziny końca. Ta sama odpowiedź stoi
# już w dwóch miejscach — `weather_alert.validity_or_default` (backend) i
# `utils/eventTime.endOf` (front) — i mówi to samo: brak deklarowanego końca
# nie znaczy ani „wiecznie", ani „natychmiast".
#
# 25.08.2026 konsultacje w sprawie skanalizowania Rumiana, Naguszewa i Groszek
# (art. 5342, tego dnia o 19:00) NIE ISTNIAŁY w feedzie: ogłoszone 12.08,
# `event_until` puste, więc żaden z trzech warunków okna ich nie przepuścił.
# W rankingu wyszłyby drugie w całym feedzie (1,41 wobec 1,69 wyłączenia prądu).
DEFAULT_EVENT_DURATION_H = 3

DEFAULT_WEIGHT = 1.0

# Waga źródła w rankingu. Instytucje > media > scrapowane profile prywatne.
# Uwaga: typ z tabeli `sources` nie wystarcza — KPP i Radio 7 są oba `rss`,
# a profile gminy i ZGK są `social_media`, choć to źródła urzędowe.
SOURCE_WEIGHTS: dict[str, float] = {
    # infrastruktura — najwyższa wartość użytkowa
    "Energa - wyłączenia bieżące (RSS)": 1.40,
    "Energa - wyłączenia planowane (RSS)": 1.30,
    "Facebook - ZakladGospodarkiKomunalnej": 1.30,
    # urząd i służby
    "Gmina Rybno": 1.35,
    "BIP Gminy Rybno": 1.35,
    "KPP Działdowo (RSS)": 1.30,
    "Facebook - Gmina Działdowo": 1.25,
    "Powiat Działdowski (RSS)": 1.20,
    "Facebook - Rybno": 1.15,
    # media z redakcją i impressum
    "Radio 7 Działdowo (RSS)": 1.00,
    "Radio Olsztyn (RSS)": 0.95,
    "Moje Działdowo": 0.95,
    "Gazeta Olsztyńska (RSS)": 0.90,
    # scrapowane profile prywatne
    "Facebook - Syla": 0.85,
    "Facebook - Panorama Regionu": 0.85,
}

# Źródła o zasięgu szerszym niż gmina — o lokalności pojedynczego wpisu
# rozstrzyga jego treść, nie nazwa źródła. Feed Energi obejmuje Region Mława
# (Płośnica, Iłowo, Lidzbark…), więc samo „to Energa" nie znaczy „to nasze":
# 29.07.2026 briefing zapowiedział mieszkańcom Rybna wyłączenie prądu
# w Płośnicy jako lokalną awarię.
#
# KPP i Radio 7 dopisane po audycie z 11.08.2026: obsługują cały powiat i kawałek
# sąsiednich, a kod liczył każdy ich wpis jako lokalny po samej nazwie źródła.
# Pomiar tygodnia: 20 z 29 wpisów Radia 7 i 6 z 22 wpisów KPP nie dotyczyło gminy
# (Żuromin, Mława, Lidzbark) — stąd rozjazd między lokalnością raportowaną (77%)
# a realną (~26%). Nagłówek briefingu otwierał się nimi jak wiadomością z Rybna.
COUNTY_WIDE_SOURCES: frozenset[str] = frozenset({
    "Energa - wyłączenia bieżące (RSS)",
    "Energa - wyłączenia planowane (RSS)",
    "KPP Działdowo (RSS)",
    "Radio 7 Działdowo (RSS)",
})

# Źródła dotyczące bezpośrednio gminy Rybno i powiatu działdowskiego.
# Briefing trzymał tę wiedzę osobno, w postaci ID-ków (`LOCAL_SOURCE_IDS`),
# i przy każdym nowym źródle zostawała nieaktualna: Energa, KPP, Powiat i profil
# gminy liczyły się jako „regionalne", więc nie mogły wygrać nagłówka dnia.
LOCAL_SOURCES: frozenset[str] = COUNTY_WIDE_SOURCES | {
    "Gmina Rybno",
    "BIP Gminy Rybno",
    "Facebook - Rybno",
    "Facebook - Syla",
    "Facebook - ZakladGospodarkiKomunalnej",
    "Facebook - Panorama Regionu",
    "Facebook - Gmina Działdowo",
    "Moje Działdowo",
    "Powiat Działdowski (RSS)",
    "KPP Działdowo (RSS)",
    # Organizator imprezy w gminie. Źródło trzymane jako `disabled` — nic z niego
    # nie scrapujemy, służy wyłącznie za atrybucję dla komunikatów wpisywanych
    # ręcznie. Powód: 18.08.2026 jedyna informacja o zmianie organizacji ruchu
    # na 23.08 (wahadło na powiatowej 1255 N, 9:20–17:00) wisiała na fanpage'u
    # organizatora i nigdzie indziej — ani gmina, ani BIP jej nie wydały.
    "Łaciate Mazury MTB",
}

# Źródła, których nazw NIE eksponujemy w interfejsie.
# Prywatne profile FB pokazujemy jako neutralne „źródło ↗" z linkiem do oryginału:
# atrybucja zostaje (link), ale nie reklamujemy cudzej marki nagłówkiem
# i nie sugerujemy, że feed jest przedrukiem cudzego profilu.
UNNAMED_SOURCES: frozenset[str] = frozenset({
    "Facebook - Syla",
    "Facebook - Panorama Regionu",
})


def source_weight(source_name: Optional[str]) -> float:
    return SOURCE_WEIGHTS.get(source_name or "", DEFAULT_WEIGHT)


def is_local_source(source_name: Optional[str]) -> bool:
    return (source_name or "") in LOCAL_SOURCES


# Źródła mówiące WYŁĄCZNIE o gminie Rybno. Wszystkie pozostałe „lokalne" —
# Moje Działdowo, Powiat Działdowski, profil gminy Działdowo — mówią o SĄSIADACH
# tak samo często jak o nas, więc dla nich nazwa miejscowości musi paść w treści.
GMINA_SOURCES: frozenset[str] = frozenset({
    "Gmina Rybno",
    "BIP Gminy Rybno",
    "Facebook - Rybno",
    "Facebook - ZakladGospodarkiKomunalnej",
    "Facebook - Syla",
    "Łaciate Mazury MTB",
})


def article_scope(
    source_name: Optional[str],
    title: Optional[str] = None,
    content: Optional[str] = None,
) -> str:
    """Etykieta miejsca DLA CZŁOWIEKA: „gmina Rybno" / „okolice" / „poza regionem".

    Osobna od `is_local_article`, bo odpowiada na inne pytanie. Tamta mówi
    „czy to nasz region" i steruje RANKINGIEM — jej próg jest celowo szeroki,
    bo lepiej pokazać sąsiednią gminę niż zgubić naszą sprawę. Ta mówi
    „co napisać mieszkańcowi", a tu szeroki próg KŁAMIE.

    24.08.2026 Redaktor podał „Rozpoczęła się budowa bloku komunalnego
    w Działdowie (gmina Rybno)". Wpis przyszedł z „Powiat Działdowski (RSS)",
    które jest w `LOCAL_SOURCES`, ale nie w `COUNTY_WIDE_SOURCES` — więc
    `is_local_article` przepuszczało je bez patrzenia na treść. Model niczego
    nie zmyślił: dokładnie tak dostał to opisane.

    ⚠️ NIE podmieniać jednej funkcji drugą. `is_local_article` wchodzi
    w `article_score`, wybór nagłówka briefingu i newsletter; zwężenie jej
    progu zmienia to, co widzi mieszkaniec na stronie głównej, i wymaga
    przebiegu `scripts.test_summary_headline`.
    """
    if is_foreign_region(title, content):
        return "poza regionem"  # cudze Rybno spod Sochaczewa
    if source_name in GMINA_SOURCES:
        return "gmina Rybno"
    # Treść przed źródłem: Radio Olsztyn nie jest źródłem lokalnym, ale gdy pisze
    # O RYBNIE, to jest wiadomość z gminy. Bramka źródła postawiona wyżej
    # odcinałaby takie wpisy, zanim ktokolwiek spojrzy, o czym są.
    if places_in(title, content):
        return "gmina Rybno"
    return "okolice" if is_local_source(source_name) else "poza regionem"


def is_local_article(
    source_name: Optional[str],
    title: Optional[str] = None,
    content: Optional[str] = None,
) -> bool:
    """
    Czy wpis liczy się jako „nasz" — dotyczący gminy Rybno i najbliższych okolic.

    Dla większości źródeł wystarczy samo źródło. Dla feedów powiatowych musi
    paść nazwa z gminy; listę sołectw i ich odmiany trzyma `alert_policy`
    (bramka miejsca dla powiadomień) i jest to jedyna taka lista w projekcie.
    """
    if not is_local_source(source_name):
        return False
    if is_foreign_region(title, content):
        return False  # cudze Rybno spod Sochaczewa — patrz `alert_policy`
    if source_name in COUNTY_WIDE_SOURCES:
        return bool(places_in(title, content))
    return True


# Nazwy techniczne z tabeli `sources` nie nadają się do pokazania mieszkańcowi
# ("Facebook - ZakladGospodarkiKomunalnej"). Sufiks "(RSS)" zdejmowany automatycznie.
SOURCE_DISPLAY_NAMES: dict[str, str] = {
    "Facebook - ZakladGospodarkiKomunalnej": "ZGK w Rybnie",
    "Facebook - Gmina Działdowo": "Gmina Działdowo",
    "Facebook - Rybno": "Gmina Rybno (Facebook)",
    "KPP Działdowo (RSS)": "Policja — KPP Działdowo",
    "Energa - wyłączenia bieżące (RSS)": "Energa Operator",
    "Energa - wyłączenia planowane (RSS)": "Energa Operator",
}


def source_label(source_name: Optional[str]) -> Optional[str]:
    """Nazwa źródła do pokazania w UI albo None — wtedy front daje 'źródło ↗'."""
    if not source_name or source_name in UNNAMED_SOURCES:
        return None
    if source_name in SOURCE_DISPLAY_NAMES:
        return SOURCE_DISPLAY_NAMES[source_name]
    return source_name.replace(" (RSS)", "").strip()


# Ile jeszcze żyje zapowiedź po swoim terminie. Doba, nie zero: post
# o wczorajszych dożynkach mieszkaniec czyta jako relację i ma prawo go
# zobaczyć, a jego znacznik czasu mówi wprost „wczoraj". Wyłączenie prądu
# sprzed dwóch dni nie mówi już nic nikomu.
ENDED_EVENT_GRACE_H = 24


def publishable_conditions(article_model, now: Optional[datetime] = None):
    """
    Warunki SQL „to nadaje się do pokazania mieszkańcowi" — wspólne dla feedu,
    briefingu, newslettera, pusha i narzędzi agentów. Dopisanie kolejnej reguły
    ma działać we wszystkich tych miejscach naraz.

    Trzecia reguła (3.09.2026): zapowiedź, której termin minął ponad dobę temu,
    znika. „Planowane wyłączenie prądu 1 września, 09:00–14:00 — Kopaniarze"
    stało 3.09 w sekcji „Gmina Rybno" — okno feedu liczy się od publikacji
    (2 dni), a ranking dawał takiemu wpisowi tylko ×0,25, czyli spychał go
    niżej, zamiast usunąć. Przy 4–9 lokalnych wpisach dziennie „niżej" i tak
    znaczyło pierwszą stronę.

    Liczymy od KOŃCA zdarzenia, a dla zapowiedzi bez godziny końca — od końca
    jej doby (`event_at` o północy to zapis całodniowy, tak samo jak w
    `_event_end` i `summary_generator._event_is_over`). Wpisy bez
    terminu reguła nie dotyczy wcale: o nich rozstrzyga wiek publikacji.
    """
    now = now or datetime.utcnow()
    ended_before = now - timedelta(hours=ENDED_EVENT_GRACE_H)

    return [
        article_model.is_filler == False,        # noqa: E712 — SQLAlchemy
        article_model.is_promotional == False,   # noqa: E712
        or_(
            article_model.event_at.is_(None),
            article_model.event_until >= ended_before,
            and_(
                article_model.event_until.is_(None),
                or_(
                    article_model.event_at >= ended_before,
                    # zapowiedź całodniowa: doba liczy się od jej końca
                    and_(
                        cast(article_model.event_at, Time) == time(0, 0),
                        article_model.event_at >= ended_before - timedelta(days=1),
                    ),
                ),
            ),
        ),
    ]


# Ile dób lokalnych żyje w feedzie zwykła wiadomość: dziś, wczoraj i przedwczoraj.
# Liczone od PUBLIKACJI, nigdy od `scraped_at` — ten ostatni jest nadpisywany przy
# każdym ponownym pobraniu (`scrapers/base.save_to_db`), więc stary post wracał do
# okna jak świeży: 15.09.2026 było tak z siedmioma wpisami naraz.
NEWS_MAX_AGE_DAYS = 3

# Zapowiedź wchodzi do feedu w PRZEDDZIEŃ swojego terminu. Wcześniej jej miejscem
# jest kalendarz — o to właśnie rozjechała się polityka między 27.07 a 25.08.2026,
# gdy `still_relevant_event` wpuściło do feedu każdą zapowiedź aż do terminu:
# 15.09 na 35 wpisów 15 dotyczyło przyszłości, w tym zebranie ogłoszone 21.08
# i certyfikat QMP ogłoszony 7.08.
ANNOUNCEMENT_LEAD_DAYS = 1


def feed_window_conditions(article_model, now: Optional[datetime] = None):
    """
    Warunki SQL okna feedu — celowo SZERSZE niż prawda, ostatecznie orzeka
    `in_feed_window` w Pythonie.

    Ten sam podział pracy co przy przypinaniu awarii (`is_pinned_alert`): SQL
    zawęża pulę do rozsądnego rozmiaru, a reguły, które muszą czytać TREŚĆ
    (nazwa wsi przez `places_in`, rodzaj zdarzenia przez `incident_of`),
    wykonuje Python. Nie da się ich wyrazić w SQL, a przepisanie ich na
    kategorię z AI byłoby cofnięciem się do etykiety, która powstaje o 6:15
    i 13:15 i potrafi się zmienić między przebiegami.
    """
    now = now or datetime.utcnow()
    news_start, _ = local_day_bounds(now=now, days=1)
    news_start -= timedelta(days=NEWS_MAX_AGE_DAYS - 1)
    _, tomorrow_end = local_day_bounds(now=now, days=ANNOUNCEMENT_LEAD_DAYS + 1)
    ended_before = now - timedelta(hours=ENDED_EVENT_GRACE_H)

    with_term = and_(
        article_model.event_at.isnot(None),
        _event_end(article_model) >= ended_before,
    )

    return or_(
        # 1. Wiadomość — liczy się data publikacji, nie moment pobrania.
        func.coalesce(article_model.published_at, article_model.scraped_at) >= news_start,
        # 2. Zapowiedź w przeddzień, w dniu terminu albo trwająca.
        and_(with_term, article_model.event_at < tomorrow_end),
        # 3. Sprawy gminy z terminem — wcześniej niż D-1 wolno pokazać wyłącznie
        #    awarii i wiadomości urzędowej. Które to są, rozstrzyga `in_feed_window`.
        and_(with_term, article_model.locality >= MIN_ARTICLE_LOCALITY),
        and_(with_term, article_model.category.ilike("%awari%")),
    )


# Kategoria wiadomości urzędowej — sprawa, na którą mieszkaniec ma zareagować
# albo się stawić (zebranie wiejskie, konsultacje, termin w urzędzie). Tylko ona
# i awaria mają prawo stać w feedzie wcześniej niż w przeddzień terminu.
OFFICIAL_CATEGORY = "Urząd"


def in_feed_window(article, now: Optional[datetime] = None) -> bool:
    """
    Czy ten wpis należy DZIŚ do feedu — jedyne miejsce, gdzie to orzekamy.

    Trzy reguły, w kolejności od najczęstszej:

    1. **Wiadomość bez terminu** żyje `NEWS_MAX_AGE_DAYS` dób lokalnych od
       PUBLIKACJI.
    2. **Zapowiedź** czeka w kalendarzu i wchodzi do feedu w przeddzień terminu.
       Po terminie zostaje jeszcze dobę (`ENDED_EVENT_GRACE_H` w
       `publishable_conditions`), bo wczorajsza impreza czyta się jako relacja.
    3. **Wyjątek: awaria i wiadomość urzędowa DOTYCZĄCA GMINY** — te pokazujemy
       od ogłoszenia, bo mieszkaniec ma się do nich przygotować. Wyłączenie prądu
       w Żabinach za tydzień jest wiadomością; ten sam komunikat o Działdowie
       czeka do przeddnia i stoi w sekcji „Powiat i sąsiedzi".

    Rodzaj zdarzenia czytamy z TEKSTU (`alert_policy.incident_of`), nie
    z kategorii — ta powstaje o 6:15/13:15, a komunikat Energi z 18:05 wisi do
    rana bez niej. Kategoria „Urząd" dokłada się do tego, bo zebrania wiejskiego
    żaden wzorzec awarii nie rozpozna i rozpoznać nie powinien.
    """
    now = now or datetime.utcnow()
    event_at = getattr(article, "event_at", None)

    if event_at is None:
        published = getattr(article, "published_at", None) or getattr(article, "scraped_at", None)
        if published is None:
            return False
        news_start, _ = local_day_bounds(now=now, days=1)
        news_start -= timedelta(days=NEWS_MAX_AGE_DAYS - 1)
        return published >= news_start

    # Zapowiedź po terminie: o karencji rozstrzyga `publishable_conditions`,
    # tutaj wystarczy, że zdarzenie już się zaczęło.
    if event_at <= now:
        return True

    _, lead_end = local_day_bounds(now=now, days=ANNOUNCEMENT_LEAD_DAYS + 1)
    if event_at < lead_end:
        return True

    title = getattr(article, "title", None)
    content = getattr(article, "content", None)
    display = getattr(article, "display_title", None)
    locality = getattr(article, "locality", None)

    in_gmina = (
        locality >= MIN_ARTICLE_LOCALITY if locality is not None
        else bool(places_in(display or title, content))
    )
    if not in_gmina:
        return False

    category = (getattr(article, "category", None) or "").strip()
    if category == OFFICIAL_CATEGORY:
        return True
    return bool(incident_of(display or title, content)) or "awari" in category.lower()


# Jak długie zdarzenie wolno jeszcze uznać za „dzieje się TERAZ".
#
# Zerowy dystans należy się wyłączeniu prądu trwającemu dziewięć godzin
# i imprezie całodniowej — nie akcji rozłożonej na tygodnie. Pomiar 8.09.2026
# pokazał to od razu: bez progu na szczyt okna KPP weszły „Bezpieczna droga do
# szkoły" i „Zwalniaj" (art. 5736, 5737) — kampanie z `event_until` na 30
# września, więc „trwające" przez cały miesiąc — i wypchnęły stamtąd
# zatrzymanie sprawców kradzieży oraz spot profilaktyczny. Akcja trwająca
# miesiąc nigdy nie przestaje być „teraz", czyli zajmowałaby miejsce na stałe.
#
# 36 h mieści zapowiedź całodniową (doba) z zapasem na wpis, który zaczyna się
# wieczorem i kończy nazajutrz. Dłuższe zdarzenie liczy dystans od swojego
# POCZĄTKU — tak jak przed tą zmianą.
ONGOING_MAX_SPAN_H = 36


def _event_end(article_model):
    """
    Koniec zdarzenia w SQL — ta sama reguła, którą stosuje okno feedu
    (`feed_window_conditions`) i karencja w `publishable_conditions`:
    deklarowany `event_until`, dla zapowiedzi całodniowej koniec jej doby,
    dla reszty `DEFAULT_EVENT_DURATION_H`.
    """
    return case(
        (article_model.event_until.isnot(None), article_model.event_until),
        (
            cast(article_model.event_at, Time) == time(0, 0),
            article_model.event_at + timedelta(days=1),
        ),
        else_=article_model.event_at + timedelta(hours=DEFAULT_EVENT_DURATION_H),
    )


def source_window_order(article_model, now: Optional[datetime] = None):
    """
    Kolejność, w jakiej źródło wystawia swoje wpisy do okna `per_source`.

    To osobne pytanie od rankingu feedu (`article_score`): tam rozstrzyga się,
    co stoi wyżej, TU — co w ogóle wychodzi ze źródła. Wpis odcięty na tym
    etapie nie istnieje dla mieszkańca, choćby w rankingu wygrywał wszystko.

    ⚠️ 8.09.2026 to okno wycięło ze strony trzy wyłączenia prądu TRWAJĄCE
    w tej chwili (Filice, Sękowo, Kramarzewo, wszystkie 8.09 do 17:00) oraz
    jedyne wyłączenie w gminie Rybno (Truszczyny, art. 5790, nazajutrz
    10:00–15:00). Miejsca w piątce zajęły zapowiedzi na 11, 14 i 15 września
    — ogłoszone tego ranka, więc `least(termin, publikacja)` dawało im
    dystans 0,7 h. Push o Truszczynach poszedł dzień wcześniej o 20:12,
    briefing otwierał się nimi jako nagłówkiem; mieszkaniec, który kliknął
    w powiadomienie, nie znajdował tego wpisu na stronie.

    Dwie osi, obie brakujące wcześniej:

    1. **Miejsce.** Wpis o gminie Rybno nie może zostać wypchnięty przez wpis
       spoza gminy z tego samego źródła. `article_score` stosuje tę zasadę
       od 22.08.2026 (`locality_factor`), okno źródła nie znało jej wcale —
       a feedy Energi, KPP i Radia 7 obejmują cały powiat, więc wpisów spoza
       gminy jest w nich z definicji więcej niż naszych. Próg wspólny
       z rankingiem (`MIN_ARTICLE_LOCALITY`); wpis bez oceny lokalności nie
       jest promowany, bo nie ma czym.

    2. **Czas mierzony do OKNA zdarzenia, nie do jego początku.** Zdarzenie,
       które właśnie trwa, jest odległe o zero — wcześniej liczyło się tak
       samo jak zapowiedź na za cztery godziny i przegrywało ze świeżym
       ogłoszeniem czegokolwiek. Po terminie dystans znów rośnie, więc
       „drugie życie" zapowiedzi (`_reference_time`) zostaje nietknięte:
       ogłoszenie z dziś o festynie za trzy tygodnie nadal jest wiadomością
       dnia, bo bliżej ma publikację.
    """
    now = now or datetime.utcnow()

    published_distance = func.abs(func.extract(
        "epoch", func.coalesce(article_model.published_at, article_model.scraped_at) - now
    ))
    event_end = _event_end(article_model)
    event_distance = case(
        (article_model.event_at.is_(None), None),
        (article_model.event_at > now, func.extract("epoch", article_model.event_at - now)),
        (event_end < now, func.extract("epoch", now - event_end)),
        # trwa TERAZ i jest zdarzeniem punktowym — bliżej być nie może
        (
            event_end - article_model.event_at
            <= timedelta(hours=ONGOING_MAX_SPAN_H),
            0.0,
        ),
        # trwa, ale to akcja rozłożona na tygodnie — liczymy od jej początku
        else_=func.extract("epoch", now - article_model.event_at),
    )
    is_local = case(
        (article_model.locality >= MIN_ARTICLE_LOCALITY, 1),
        else_=0,
    )

    return [
        is_local.desc(),
        func.least(
            func.coalesce(event_distance, published_distance), published_distance
        ).asc(),
        article_model.scraped_at.desc(),
    ]


# Kalendarz mieszkańca gminy Rybno kończy się na sąsiednich gminach powiatu:
# do Działdowa czy Lidzbarka pojedzie, na Senioralia Powiatu Płońskiego nie.
# Pomiar 21.08.2026 na 130 wydarzeniach z 30 dni: gmina Rybno ~56, reszta to
# Sierpc (14), Działdowo (12), Ciechanów (9), Żuromin (8), Mława (6), Warszawa (3).
# Bramki miejsca nie było wcześniej żadnej — Radio 7 obsługuje ciechanowskie
# i płockie, więc newsletter wysłał „Dziś w okolicy: III Ciechanowski Festiwal".
MIN_EVENT_LOCALITY = 2


# Ile znaków słowa wchodzi do dopasowania. Polszczyzna jest fleksyjna, a akt
# prawny mówi innym przypadkiem niż mieszkaniec: pytanie „plan ogólny" nie
# trafiało w tytuł „przystąpienia do sporządzenia planu ogólnego", bo
# `ILIKE '%ogólny%'` nie widzi formy „ogólnego".
#
# Skutek był gorszy od braku odpowiedzi. 25.08.2026 na pytanie „Czy Rada
# uchwaliła już plan ogólny gminy Rybno?" rejestr zwrócił JEDEN akt — uchwałę
# o Strategii Rozwoju, która ma słowo „ogólny" gdzieś w treści — a agent wiernie
# o niej opowiedział. Odpowiedź brzmiała kompetentnie, cytowała prawdziwy numer
# i dotyczyła zupełnie innego dokumentu; właściwa uchwała III/20/2024 nie miała
# jak się pokazać.
#
# Obcinamy KOŃCÓWKĘ, nie dobieramy słownika form: „ogólny" → „ogóln",
# „uchwały" → „uchwał", „drogi" → „drog". Ten sam zabieg, co `_places_re`
# w testach i `_organ_key` w dedupie wydarzeń.
#
# ⚠️ Krótszy rdzeń przepuszcza więcej szumu — i to jest tu świadomy wybór:
# rejestr ma 430 pozycji i sortowanie po dacie, więc lepiej mieć właściwy akt
# wśród trzech niż nie mieć go wcale. Słów krótszych niż 5 znaków nie ruszamy,
# bo z „droga" zostałoby „dro".
STEM_MIN_LENGTH = 5
STEM_CUT = 2


def word_stem(word: str) -> str:
    """Rdzeń słowa do dopasowania LIKE — bez końcówki fleksyjnej."""
    if len(word) < STEM_MIN_LENGTH:
        return word
    return word[:-STEM_CUT]


def visible_event_conditions(event_model):
    """
    Warunki SQL „to wydarzenie pokazujemy mieszkańcowi" — dla kalendarza,
    briefingu, newslettera i Przewodnika naraz.

    Dwa powody, dla których wydarzenie zostaje w bazie, ale nie na ekranie:
    jest powtórzeniem innego (`canonical_id`) albo dzieje się za daleko
    (`locality`). NULL w lokalności to wpis sprzed 21.08.2026 — pokazujemy go,
    bo cofnięcie się z oceną wstecz kosztowałoby przebieg modelu po całej tabeli,
    a stare wpisy i tak wychodzą z okien czasowych.
    """
    return [
        event_model.canonical_id.is_(None),
        or_(
            event_model.locality.is_(None),
            event_model.locality >= MIN_EVENT_LOCALITY,
        ),
    ]


# --- cudze wezwania do kontaktu ---------------------------------------------

# Post źródłowy kończy się zwykle prośbą skierowaną do JEGO odbiorców: „napiszcie
# w komentarzu", „kontakt z redakcją". Przepisane do briefingu czyta się jak nasze
# — 2.08.2026 briefing prosił, by osoby rozpoznające znalezioną tablicę
# rejestracyjną skontaktowały się „z redakcją", której nie prowadzimy.
# Atrybucja zostaje (link do oryginału w feedzie); przejmujemy fakt, nie apel.
_CTA_PATTERNS = (
    r"kontakt\w*\s+z\s+redakcj",
    r"skontaktuj\w*\s+si\w*\s+z\s+redakcj",
    r"redakcj\w*\s+(prosi|czeka|pro[sś]i)",
    r"napisz\w*\s+(do\s+nas|w\s+komentarz|w\s+wiadomo[sś]ci|na\s+priv)",
    r"wiadomo[sś]ci?\s+prywatn",
    r"\bpw\b|\bpriv\b|messenger",
    r"w\s+komentarzu\s+poni[zż]ej|link\s+w\s+komentarz",
    r"(polub|obserwuj|[sś]led[zź])\w*\s+(nasz|profil|stron|fanpage)",
    r"udost[eę]pni\w*",
    r"zapraszamy\s+na\s+(nasz|profil|fanpage)",
    # Dopisek naszego scrapera pod treścią z profili FB — nie jest zdaniem
    # briefingu i model nie ma go przepisywać
    r"pe[lł]na\s+tre[sś][cć]\s+u\s+[zź]r[oó]d[lł]a",
)
_CTA_RE = re.compile("|".join(_CTA_PATTERNS), re.IGNORECASE)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def strip_foreign_cta(text: Optional[str]) -> str:
    """
    Treść bez zdań, które wzywają do kontaktu z cudzą redakcją albo profilem.

    Wycinamy całe zdanie, bo apel rzadko da się uratować w połowie. Gdy po
    wycięciu nic nie zostaje, oddajemy oryginał — lepszy cudzy apel niż pustka
    w materiale dla modelu.
    """
    if not text:
        return ""
    kept = [part for part in _SENTENCE_SPLIT_RE.split(text) if part.strip() and not _CTA_RE.search(part)]
    return " ".join(kept).strip() or text.strip()


def strip_cta_tail(title: Optional[str]) -> str:
    """
    Tytuł bez doklejonego apelu: „Znaleziono tablicę w Rybnie, pilny kontakt
    z redakcją" → „Znaleziono tablicę w Rybnie".

    Apel wchodzi też do `display_title` (kategoryzacja przepisuje wymowę posta),
    więc samo sięgnięcie po display_title zamiast tytułu źródłowego nie wystarcza.
    Ucinamy wyłącznie KOŃCÓWKĘ — człon w środku zdania zostawiamy nietknięty,
    żeby nie okaleczyć informacji.
    """
    if not title:
        return ""
    trimmed = title.strip()
    # Ucinamy po ostatnim separatorze, dopóki ogon jest apelem. Oryginalnej
    # interpunkcji nie odtwarzamy — zostaje dokładnie ten kawałek, który był.
    while True:
        separators = list(re.finditer(r"\s*[,;–—]\s+|\s+-\s+", trimmed))
        if not separators:
            return trimmed
        last = separators[-1]
        if not _CTA_RE.search(trimmed[last.end():]):
            return trimmed
        trimmed = trimmed[:last.start()].strip()


def _dateless_to_midday(
    timestamp: Optional[datetime],
    now: Optional[datetime] = None,
) -> Optional[datetime]:
    """
    Data bez godziny znaczy „tego dnia", a nie „o północy".

    `gminarybno.pl`, BIP i „Moje Działdowo" podają przy wpisie samą datę, więc
    scraper zapisuje północ (pomiar 05.08.2026: 8/8 wpisów gminy, 1/1 BIP,
    4/4 Moje Działdowo — wszystkie inne źródła mają realne godziny). Przy
    półokresie świeżości 18 h każdy wpis urzędu wchodził do rankingu obciążony
    kilkunastogodzinnym wiekiem, którego nie miał: ostrzeżenie meteorologiczne
    gminy z 05.08 przegrało w feedzie z „Powiat sierpecki. Samorządowcy
    rozmawiali o współpracy" z Radia 7 i wypadło poza pięć pozycji Dashboardu.

    Południe zamiast północy to najuczciwsze przybliżenie: błąd ±6 h zamiast
    stałego postarzania o 12–22 h. Nie sięgamy po `scraped_at`, bo ten jest
    nadpisywany przy każdym ponownym pobraniu (`scrapers/base.py`) — wpis
    odmładzałby się w kółko i wisiał na górze feedu tygodniami.
    """
    if timestamp is None or timestamp.time() != time(0, 0):
        return timestamp
    midday = timestamp.replace(hour=12)
    now = now or datetime.utcnow()
    # Nie wolno wskazać przyszłości: nad ranem południe jeszcze nie nastało,
    # a wpis „z dzisiaj" ma być świeży, nie zapowiedziany.
    return min(midday, now) if midday > now else midday


def _reference_time(
    published_at: Optional[datetime],
    scraped_at: Optional[datetime],
    event_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> Optional[datetime]:
    """
    Moment, względem którego liczymy wagę wpisu — ten BLIŻSZY teraz.

    Zapowiedź żyje dwa razy: w dniu ogłoszenia jest świeżą wiadomością, potem
    gaśnie, a przed samym terminem wraca. Branie zawsze terminu chowało ogłoszenie
    w chwili, gdy było najbardziej aktualne — festyn zapowiedziany dziś na koniec
    miesiąca spadałby na dno feedu tego samego poranka, w którym gmina go ogłosiła
    (przy `LOOKAHEAD_HALFLIFE_H` = 48 h dwadzieścia dni w przód to mnożnik 0,0007).

    Ta sama zasada, którą briefing stosuje przy wyborze nagłówka
    (`summary_generator._time_distance_h`): liczy się odległość, nie kierunek.
    """
    published = _dateless_to_midday(published_at, now) or scraped_at
    if not event_at:
        return published
    if not published:
        return event_at

    now = now or datetime.utcnow()
    return min(
        (event_at, published),
        key=lambda stamp: abs((now - stamp).total_seconds()),
    )


# --- znacznik czasu w materiale dla modelu -----------------------------------

LOCAL_TZ = ZoneInfo("Europe/Warsaw")


def _local(value: datetime) -> datetime:
    """Naiwny UTC z bazy → czas lokalny, którym mówi mieszkaniec."""
    return value.replace(tzinfo=ZoneInfo("UTC")).astimezone(LOCAL_TZ)


def time_label(
    published_at: Optional[datetime],
    event_at: Optional[datetime] = None,
    event_until: Optional[datetime] = None,
    now: Optional[datetime] = None,
    published_prefix: str = "",
) -> str:
    """
    Kiedy to jest — w postaci, w jakiej podajemy modelowi.

    Bez tego model nie odróżniał wpisu sprzed godziny od wpisu sprzed doby,
    a wyłączenie prądu ogłoszone dziesięć dni temu czytał jako starą wiadomość
    (7.08.2026: „nie ma żadnych zgłoszeń" czterdzieści minut przed wyłączeniem).
    Dla zdarzenia z terminem liczy się TERMIN, dla wiadomości — publikacja.

    Rdzeń „kiedy" (dzień + godziny, całodniowość) liczy wspólna warstwa
    `time_span.when_label`; tutaj zostaje wyłącznie to, CO Z TEGO WYNIKA —
    „TRWA TERAZ" / „już się zakończyło". `summary_generator._time_label`
    stoi na tym samym rdzeniu, w swoich nawiasach kwadratowych.
    """
    now = now or datetime.utcnow()

    if event_at:
        when = when_label(event_at, event_until, now)
        if event_until and event_at <= now <= event_until:
            return f"ZDARZENIE {when} — TRWA TERAZ"
        # Zapowiedź bez godziny trwa do końca SWOJEJ doby lokalnej — inaczej
        # dożynki byłyby „zakończone" o 00:01 w dniu dożynek.
        if is_all_day(event_at, event_until):
            if _local(now).date() > _local(event_at).date():
                return f"ZDARZENIE {when} — już się zakończyło"
        elif (event_until or event_at) < now:
            return f"ZDARZENIE {when} — już się zakończyło"
        return f"ZDARZENIE {when}"

    if not published_at:
        return "bez daty"

    return f"{published_prefix}{when_label(published_at, None, now, all_day=False)}"


# Ocena treści (`articles.content_score`, 0–6 = lokalność + użyteczność) przełożona
# na mnożnik. Zakres 0,7–1,3 dobrany celowo umiarkowanie: przy półokresie świeżości
# 18 h odpowiada przesunięciu o ~±9 h, więc przestawia kolejność w obrębie doby,
# ale nie wskrzesza wpisu sprzed tygodnia. Wpis nieoceniony (NULL — wszystko sprzed
# 11.08.2026 i wszystko przed przebiegiem kategoryzacji) dostaje 1,0 i zachowuje
# dotychczasową pozycję.
CONTENT_FACTOR_BASE = 0.7
CONTENT_FACTOR_STEP = 0.1
MAX_CONTENT_SCORE = 6


def content_factor(content_score: Optional[int]) -> float:
    """Mnożnik jakości treści; brak oceny = 1,0 (neutralnie)."""
    if content_score is None:
        return 1.0
    score = max(0, min(MAX_CONTENT_SCORE, content_score))
    return CONTENT_FACTOR_BASE + CONTENT_FACTOR_STEP * score


# Kara za wpis spoza gminy. Mnożnik, nie filtr: zasięg powiatowy bierzemy
# świadomie, żeby w feedzie nie było pustek, a awaria w Działdowie to dla
# dojeżdżających realna informacja. Ma zejść pod materiał lokalny, nie zniknąć.
LOCALITY_FACTOR_FOREIGN = 0.55

# Od jakiej oceny kategoryzacji wpis liczy się jako „nasz". 3 = gmina Rybno;
# 2 to sąsiednie gminy powiatu (Działdowo, Lidzbark, Iłowo-Osada) i właśnie
# one wypychały lokalny materiał ze szczytu feedu.
#
# ⚠️ To NIE jest `MIN_EVENT_LOCALITY` z `visible_event_conditions` (= 2).
# Tam próg decyduje o WIDOCZNOŚCI wydarzenia i jest celowo szerszy: festyn
# w sąsiedniej gminie to realna propozycja na weekend. Tu próg decyduje
# o KOLEJNOŚCI wiadomości, a wiadomość z cudzej gminy nie ma prawa stać
# nad naszą. Nie podstawiać jednej stałej pod drugą.
MIN_ARTICLE_LOCALITY = 3


def locality_factor(
    locality: Optional[int],
    source_name: Optional[str],
    title: Optional[str] = None,
    content: Optional[str] = None,
) -> float:
    """
    Mnożnik miejsca: 1,0 dla wpisu o gminie Rybno, mniej dla reszty powiatu.

    Powstał 22.08.2026, gdy pomiar dzisiejszego feedu dał **1 wpis lokalny na
    10 pierwszych** — całą górę zajęły wyłączenia Energi w Płośnicy, Lidzbarku
    i Działdowie. Przyczyna była w samym wzorze: `article_score` liczył wagę
    źródła razy świeżość razy ocenę treści i o miejscu nie wiedział NIC.
    Energa ma najwyższą wagę w tabeli (1,40 — więcej niż Gmina Rybno i BIP),
    bo przy awarii u nas naprawdę jest najważniejsza; przy awarii w cudzej
    gminie ta sama waga wypychała na szczyt cudzą wieś. Do tego wpis jeszcze
    nieskategoryzowany (przyszedł po 6:15 i czeka na 13:15) dostaje neutralne
    1,0 z `content_factor`, czyli więcej niż lokalna wiadomość z oceną 2.

    Trzy odpowiedzi na pytanie „czy to nasze", w kolejności zaufania:
    ocena z kategoryzacji (3 = gmina Rybno), przynależność źródła, wreszcie
    sama nazwa w tekście — ta ostatnia po to, żeby artykuł o Rybnie w Radiu
    Olsztyn nie był karany za to, że źródło jest wojewódzkie.

    ⚠️ Do 3.09.2026 ocena mogła wpis wyłącznie PODNIEŚĆ, nigdy obniżyć —
    „model bywa skąpy, a `is_local_article` zna źródła". Pomiar tego dnia
    pokazał, czym to jest w praktyce: „Termin płatności III raty podatku
    i opłaty za psa w DZIAŁDOWIE" miał NAJWYŻSZY wynik całego feedu (0,792),
    wyżej niż trwająca awaria wodociągowa w Rybnie (0,722). Kategoryzacja
    oceniła go na `locality=2`, czyli powiedziała wprost „to nie nasza gmina",
    a mnożnik i tak wyszedł 1,00 — bo `Facebook - Gmina Działdowo` jest
    w `LOCAL_SOURCES`, a nie w `COUNTY_WIDE_SOURCES`, więc `is_local_article`
    przepuszczało je bez zaglądania w treść. Kara trafiała wtedy w 3 wpisy
    na 20; cała reszta obcego materiału jechała bez niej.

    Dziś ocena rozstrzyga w OBIE strony i jest pierwsza w kolejności: model
    czytał ten konkretny tekst, źródło jest tylko domysłem o tym, o czym
    źródło zwykle pisze. Bramka źródła i nazwy zostaje dla wpisów bez oceny —
    tych sprzed 21.08.2026 i tych, które czekają na kategoryzację.
    """
    if locality is None and title is None and content is None:
        return 1.0  # wywołanie bez materiału — nie zgadujemy

    if is_foreign_region(title, content):
        return LOCALITY_FACTOR_FOREIGN  # cudze Rybno

    # Ocena z kategoryzacji rozstrzyga sama — w obie strony.
    if locality is not None:
        return 1.0 if locality >= MIN_ARTICLE_LOCALITY else LOCALITY_FACTOR_FOREIGN

    local = (
        is_local_article(source_name, title, content)
        or bool(places_in(title, content))
    )
    return 1.0 if local else LOCALITY_FACTOR_FOREIGN


def article_score(
    published_at: Optional[datetime],
    scraped_at: Optional[datetime],
    source_name: Optional[str],
    now: Optional[datetime] = None,
    event_at: Optional[datetime] = None,
    event_until: Optional[datetime] = None,
    content_score: Optional[int] = None,
    locality: Optional[int] = None,
    title: Optional[str] = None,
    content: Optional[str] = None,
) -> float:
    """
    Waga źródła × świeżość × ocena treści × miejsce.

    Świeżość liczy się od momentu, który dla mieszkańca się liczy: dla zwykłej
    wiadomości to publikacja, dla zapowiedzi — to z dwóch (publikacja, termin),
    co bliżej teraz.

    Trzeci czynnik dołożony 11.08.2026 po audycie tygodnia. Bez niego ranking
    widział tylko to, JAK CZĘSTO źródło publikuje, i pierwsza piątka Dashboardu
    wychodziła gorsza od średniej materiału w lokalności, konkrecie i przyciąganiu.
    Ocenę liczy raz kategoryzacja (`ai/article_processor`), bo ranking chodzi przy
    każdym żądaniu feedu i nie może pytać modelu.

    Czwarty czynnik — miejsce — dołożony 22.08.2026, patrz `locality_factor`.
    Wywołanie bez `title`/`content`/`locality` go nie stosuje: lepiej nie ukarać
    niż ukarać po omacku wpis, którego treści nie widzimy.
    """
    now = now or datetime.utcnow()
    place = locality_factor(locality, source_name, title, content)

    # Zapowiedź żyje dwa razy — w dniu ogłoszenia i przed terminem
    # (`_reference_time`). To „drugie życie" przysługuje jednak wyłącznie
    # sprawom NASZEJ gminy. 3.09.2026 kafel „Ostatnio w gminie" pokazał
    # mieszkańcowi „Planowane wyłączenie prądu 10 września — Mławka"
    # (art. 5784, gmina Iłowo-Osada): komunikat Energi wpadł tego ranka, więc
    # ogłoszenie było bliżej niż termin i wpis liczył się jako świeży mimo
    # kary za miejsce. Cudze wyłączenie za tydzień nie jest wiadomością dnia
    # — dla wpisu spoza gminy liczy się TERMIN, bo tylko on może kiedykolwiek
    # uczynić go pilnym.
    if place < 1.0 and event_at and event_at > now:
        timestamp = event_at
    else:
        timestamp = _reference_time(published_at, scraped_at, event_at, now)
    if timestamp is None:
        return 0.0

    delta_h = (now - timestamp).total_seconds() / 3600
    if delta_h < 0:
        freshness = 0.5 ** (-delta_h / LOOKAHEAD_HALFLIFE_H)
    else:
        freshness = 0.5 ** (delta_h / FRESHNESS_HALFLIFE_H)

    # Zdarzenie, które się skończyło, przestaje konkurować z bieżącymi wiadomościami
    if event_until and now > event_until:
        freshness *= 0.25

    return (
        source_weight(source_name)
        * freshness
        * content_factor(content_score)
        * place
    )


def is_pinned_alert(
    category: Optional[str],
    published_at: Optional[datetime],
    scraped_at: Optional[datetime],
    now: Optional[datetime] = None,
    event_at: Optional[datetime] = None,
    event_until: Optional[datetime] = None,
    title: Optional[str] = None,
    content: Optional[str] = None,
    locality: Optional[int] = None,
) -> bool:
    """
    Na szczycie stoi to, co dotyczy najbliższych godzin I NASZEJ GMINY: awaria
    oraz obowiązujące ostrzeżenie meteorologiczne.

    Ten sam próg rozstrzyga o nagłówku briefingu — feed i briefing nie mogą
    inaczej odpowiadać na pytanie „czy to jest sprawa teraz".

    Bramka miejsca dopisana 21.08.2026. Push miał ją od początku
    (`alert_policy.evaluate`), feed nie miał wcale — i tego dnia pokazał
    mieszkańcom Rybna przypięte „Planowane wyłączenie prądu w Iłowie-Osadzie"
    (art. 5322), a na 24.08 czekały w kolejce dwa wyłączenia w Działdowie.
    Feedy Energi obejmują cały powiat, więc bez tej bramki przypięcie znaczyło
    tylko tyle, że coś jest awarią — nie, że dotyczy czytelnika.
    """
    now = now or datetime.utcnow()

    # Burza, upał i wichura są sprawą najbliższych godzin dokładnie tak samo jak
    # wyłączenie prądu, ale kategoria z AI nazywa je „Pogodą" albo „Wiadomościami",
    # więc warunek na „awari" ich nie obejmował. Rozstrzyga treść, nie etykieta —
    # tym bardziej że kategoria powstaje dopiero o 6:15 i 13:15, a ostrzeżenie
    # trafia do feedu od razu. `weather_alert` zna ważność wpisu (godziny z
    # komunikatu IMGW, w ostateczności DEFAULT_VALIDITY_H), więc alert schodzi
    # z góry sam, gdy przestaje obowiązywać.
    if is_weather_alert(title, content):
        return not weather_alert_expired(title, content, published_at, event_until, now)

    if not category or "awari" not in category.lower():
        return False

    # Miejsce. `locality` pochodzi z kategoryzacji (3 = gmina Rybno) i jest
    # tam już przycięte do nazwy padającej w tekście (`ground_categorization`).
    # Dla wpisów nieocenionych — sprzed 21.08.2026 albo poniżej progu treści —
    # pytamy o to samo wprost, tą samą listą sołectw, co bramka push.
    # Ostrzeżenia meteo wyszły z tej ścieżki wyżej: IMGW ostrzega dla powiatu
    # i nazwa gminy w komunikacie nie pada.
    in_gmina = locality >= 3 if locality is not None else bool(places_in(title, content))
    if not in_gmina:
        return False

    # Godziny bywają w samym komunikacie, choć kategoryzacja ich nie wpisała
    # („W godzinach 8:00 - 15:00" bez daty). Push czyta je od 24.08.2026
    # (`alert_policy.span_from_text`), feed nie czytał ich wcale — więc ta sama
    # awaria bywała na stronie przypięta długo po tym, jak push przestawał ją
    # uznawać za sprawę teraz. Jedna odpowiedź na jedno pytanie, jeden parser.
    if event_at is None and event_until is None:
        event_at, event_until = span_from_text(title, content, published_at)

    if event_at:
        if event_until and now > event_until:
            return False  # po zdarzeniu
        hours_ahead = (event_at - now).total_seconds() / 3600
        return hours_ahead <= PIN_LOOKAHEAD_H

    timestamp = published_at or scraped_at
    if timestamp is None:
        return False
    return (now - timestamp).total_seconds() / 3600 <= AWARIA_PIN_HOURS


# --- deduplikacja ------------------------------------------------------------

# Powyżej tego podobieństwa zbiorów słów uznajemy dwa wpisy za ten sam materiał
SIMILARITY_THRESHOLD = 0.72

# Słowa zbyt częste, by cokolwiek różnicowały
_STOPWORDS = frozenset({
    "the", "i", "w", "we", "z", "ze", "na", "do", "o", "od", "od", "po", "za",
    "u", "a", "e", "przy", "dla", "oraz", "lub", "to", "jest", "sie", "sa",
    "gmina", "gminie", "gminy", "wiejska", "region", "ul", "ulica", "ulice",
})

_WORD_RE = re.compile(r"[0-9a-ząćęłńóśźż]+")


def _tokens(text: str) -> frozenset[str]:
    """
    Zbiór znaczących słów — bez ogonków, emoji i interpunkcji.

    ⚠️ Znaki łączące trzeba ODSIAĆ, nie tylko rozłożyć. NFKD rozkłada „ó" na
    „o" + znak łączący, a ten nie należy do `_WORD_RE`, więc wyrażenie tnie
    słowo w miejscu ogonka: 16.09.2026 „łódź" rozpadała się na „ło" i „dz"
    (oba krótsze niż trzy znaki, więc GINĘŁY), a „wartości" na „wartos" i „ci".
    Tego dnia dwa opisy tej samej łodzi ratowniczej dla OSP Hartowiec (art.
    6028 i 6034) miały przez to podobieństwo tekstu 0,44 przy słowie „łódź"
    w obu tytułach.

    „ł" wymaga osobnej podmiany, bo jako jedyna polska litera nie rozkłada się
    w NFKD — ta sama pułapka i to samo obejście co w `alert_policy._flat`,
    gdzie kosztowała niedziałający wzorzec na „wyłączenie prądu".
    """
    lowered = (text or "").lower().replace("ł", "l")
    stripped = unicodedata.normalize("NFKD", lowered)
    flat = "".join(c for c in stripped if not unicodedata.combining(c))
    words = _WORD_RE.findall(flat)
    return frozenset(w for w in words if len(w) > 2 and w not in _STOPWORDS)


def topic_signature(text: Optional[str]) -> frozenset[str]:
    """
    Temat wpisu w postaci porównywalnej — ten sam zbiór słów, którym feed scala
    duplikaty. Pusty zbiór znaczy „nie da się rozstrzygnąć" i nie jest podobny
    do niczego.

    Energa publikuje każde odświeżenie wyłączenia jako osobny wiersz, więc
    porównanie po ID nie widzi, że to wciąż ta sama zapowiedź: 7, 10 i 11.08.2026
    briefing otworzył się tym samym wyłączeniem pod trzema różnymi ID.
    """
    return _tokens(text or "")


def same_topic(a: frozenset[str], b: frozenset[str]) -> bool:
    """Czy dwie sygnatury opisują ten sam materiał (próg wspólny z deduplikacją)."""
    if not a or not b:
        return False
    return _similarity(a, b) >= SIMILARITY_THRESHOLD


def _similarity(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# Ślady po tym, że NIE MAMY całego tekstu źródła. Dwa różne powody, jeden skutek.
#
# 1. Post z Facebooka trzymamy jako wskaźnik: nagłówek + 300 znaków + odnośnik
#    (`scrapers/apify_facebook.make_social_snippet`). To decyzja prawna — prawo
#    autorskie i RODO — a nie niedoróbka, więc jej tu nie obchodzimy. Skutek jest
#    jednak dotkliwy i zmierzony: 5.09.2026 mieszkaniec pytał o szczegóły biegu,
#    a post gminy urywa się dokładnie na „⏰ Godzina…”. Z 246 wpisów Syli
#    z 30 dni urwanych jest 193, z 12 wpisów gminy — 11.
# 2. Wielokropek na końcu bywa też dziełem samego źródła (skrót RSS).
#
# ⚠️ Sprawdziliśmy, czy da się to obejść dociągnięciem strony: NIE DA SIĘ.
#    Facebook oddaje serwerowi skorupę bez treści posta, a strona powiatu z tym
#    samym ogłoszeniem ma 480 znaków tekstu i żadnego konkretu. Skoro brakującej
#    informacji nie sposób zdobyć, jedyną uczciwą odpowiedzią jest powiedzieć,
#    że jej nie mamy, i wskazać oryginał — a do tego model musi WIEDZIEĆ,
#    że czyta wypis, nie całość.
_TRUNCATION_MARKS = ("pełna treść u źródła", "pelna tresc u zrodla")


def is_truncated(text: Optional[str]) -> bool:
    """Czy ten tekst jest WYPISEM, a nie całym materiałem źródła."""
    if not text:
        return False
    lowered = text.strip().lower()
    if any(mark in lowered for mark in _TRUNCATION_MARKS):
        return True
    return lowered.endswith("…") or lowered.endswith("...")


def dedup_text(article) -> str:
    """
    Materiał wpisu w postaci, w jakiej porównujemy go z innymi.

    Po kategoryzacji porównujemy sam `display_title`: depeszowy nagłówek modelu
    streszcza temat, a summary rozprasza sygnaturę (każde źródło streszcza inny
    aspekt tego samego komunikatu). 12.08.2026 nabór na azbest w czterech
    redakcjach (BIP, strona gminy, dwa profile FB) zajął trzy pierwsze miejsca
    feedu — podobieństwo pełnych tekstów nie przekraczało 0,52 przy progu 0,72.
    Wpisy sprzed kategoryzacji (okno 6:00–6:15) porównujemy po staremu.

    ⚠️ Termin zdarzenia NIE jest już częścią tego tekstu. Do 14.09.2026 wchodził
    jako zwarty token `ev%Y%m%d%H%M` i pełnił rolę weta: wpisy o rozłącznych
    tokenach nie były porównywane wcale. Weto było potrzebne (dwa wyłączenia
    w tej samej wsi mają identyczny tytuł i różnią się wyłącznie datą), ale
    liczone co do MINUTY w UTC zwalniało z deduplikacji każdą zapowiedź, której
    dwa źródła podały z różną dokładnością godziny. Termin ma dziś własną oś
    w `same_story` (`_term_axis`) i jest tam liczony w dobie LOKALNEJ.
    """
    display = getattr(article, "display_title", None)
    if display:
        return display
    body = (article.content or article.summary or "")[:300]
    return f"{article.title or ''} {body}"


D = TypeVar("D")


# Powyżej tego zawierania rdzeni słów tytułu uznajemy dwa wpisy za ten sam
# komunikat w różnych redakcjach. Zawieranie (|∩|/min), nie Jaccard: krótszy
# tytuł ma się mieścić w dłuższym, nadmiarowe słowa dłuższego nie rozwadniają
# wyniku. Zmierzony margines (12.08.2026): te same komunikaty 0,86–1,0;
# różne komunikaty urzędowe tego samego dnia (azbest vs stypendia) ≤ 0,5.
STEM_CONTAINMENT_THRESHOLD = 0.85

# Minimalna liczba rdzeni do testu zawierania — trzysłowne tytuły trafiają
# w wysokie zawieranie przypadkiem
_STEM_MIN_TOKENS = 5

def _stem_tokens(tokens: frozenset[str]) -> frozenset[str]:
    """
    Rdzenie słów — zgrubne ścięcie polskiej fleksji, przez którą „Rybno" i
    „w Rybnie" albo „usuwanie" i „usuwaniu" były różnymi tokenami i ten sam
    komunikat w dwóch redakcjach nie przekraczał progu podobieństwa.
    """
    stems = set()
    for word in tokens:
        stem = word.rstrip("aeiouy")[:6]
        stems.add(stem if len(stem) >= 3 else word)
    return frozenset(stems)


def _containment(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


# ── Orzekanie „to ta sama sprawa" ────────────────────────────────────────────
#
# Powód, dla którego to jest OSOBNA warstwa, a nie kolejny próg: duplikaty
# wracały do feedu czterokrotnie (12.08 azbest w czterech redakcjach, 24.08
# dwa pushe o jednej awarii, 3.09 przedruk Syli, 14.09 pobór krwi i zebranie
# wiejskie po dwa razy), a każda naprawa polegała na dostrojeniu JEDNEJ liczby.
#
# Pomiar 14.09.2026 na 581 artykułach z 30 dni i 30 parach oznaczonych ręcznie
# pokazał, dlaczego to nie mogło zadziałać — ŻADNA pojedyncza oś nie rozdziela
# tych klas:
#
#   zawieranie rdzeni  duplikaty 0,67–1,00   różne wiadomości 0,71–1,00
#   embedding (cosinus) duplikaty 0,70–0,89   różne wiadomości 0,50–0,89
#   odstęp publikacji   duplikaty 2 h–209 h   różne wiadomości 6 h–616 h
#
# Skrajne przykłady, które zamykają drogę każdemu progowi:
#   „Obchody 87. rocznicy … w RYBNIE" vs „OLSZTYN obchodzi 87. rocznicę"
#       → zawieranie rdzeni 1,000 przy dwóch różnych miastach;
#   „Wyłączenie 15.09 08:00 LIPÓWKA" vs „Wyłączenie 15.09 09:30 PRZEŁĘK"
#       → embedding 0,887 przy dwóch różnych wyłączeniach;
#   „Pobór krwi 16 września…" vs „Pobór krwi w Rybnie w dniu 16 września…"
#       → embedding 0,854, ale zawieranie rdzeni tylko 0,714.
#
# Wniosek, który ta warstwa utrwala: DUPLIKAT ORZEKAMY ZE ZBIEŻNOŚCI
# NIEZALEŻNYCH OSI, NIGDY Z JEDNEJ LICZBY. Osie są trzy i są te same, co
# w `alert_policy` dla pusha (RODZAJ → MIEJSCE → CZAS) — wzorzec, który projekt
# uznał za obowiązujący 3.09 przy układzie trzech bramek:
#
#   CZAS    — termin zdarzenia; WETO przy różnych terminach, DOWÓD przy zgodnych
#   MIEJSCE — miejscowości gminy; WETO przy rozłącznych
#   TREŚĆ   — tekst (progi jak dotąd) albo semantyka (embedding)
#
# Każda oś ma prawo WETA i weto jest silniejsze od dowolnie wysokiego
# podobieństwa — tak samo jak weto organu w dedupie wydarzeń (25.08.2026),
# gdzie dwa RÓŻNE posiedzenia miały podobieństwo 0,909, a dwa opisy jednej
# imprezy 0,790.

# Powyżej tego podobieństwa kosinusowego uznajemy dwa wpisy o ZGODNYM TERMINIE
# za jedną sprawę. Próg zmierzony 14.09.2026 na `document_embeddings`
# (source_type='article', chunk 0) na 30 parach z produkcji: wszystkie 14 par
# duplikatów miało ≥ 0,702, przy czym najniższa para to dwie redakcje relacji
# z meczu, a najwyższa 0,891.
#
# ⚠️ Ten próg NIE JEST samodzielnym sędzią i nie wolno go takim uczynić: powyżej
# 0,70 leży 11 z 16 zmierzonych par RÓŻNYCH wiadomości (mecze tego samego klubu,
# kolejne starty tej samej zawodniczki, cotygodniowe danie dnia tej samej
# restauracji). Embedding mierzy TEMAT, a lokalny materiał jest z natury
# tematycznie powtarzalny. Działa wyłącznie w parze ze zgodnym terminem.
SEMANTIC_DUPLICATE = 0.70

# Ten sam dowód dla pary, w której ŻADEN wpis nie ma terminu — a więc dla
# zwykłych wiadomości, nie zapowiedzi. Oś czasu milczy z definicji, więc jej
# rolę przejmuje oś MIEJSCA i musi być POTWIERDZONA: obie strony wymieniają tę
# samą wieś z gminy. Milczenie miejsca (Energa o wsiach spoza gminy, kampanie
# KPP bez nazw) zostawia parę w spokoju, tak jak dotąd.
#
# Próg zmierzony 16.09.2026 na parach z produkcji, osobno dla tej klasy:
#   duplikaty ze wspólną wsią   0,845 (warsztaty Cariboo / jazda na rowerze),
#                               0,889 (świnki dożynkowe), 0,904 (łódź OSP)
#   różne wiadomości ze wspólną wsią  0,753 (dwa mecze Delfina), 0,741
#                               (dwa starty Natalii Zakrzewskiej), 0,579
#                               (znaleziony pies / znaleziona bransoletka)
# Rozstęp 0,753 ↔ 0,845 jest wąski i taki zostanie: wiadomości z jednej wsi są
# tematycznie podobne z natury. Dlatego próg stoi pośrodku, a nie przy dolnej
# krawędzi — i dlatego ta gałąź NIE działa bez potwierdzonego miejsca.
#
# 16.09.2026 przez jej brak feed pokazał dwa razy tę samą łódź ratowniczą dla
# OSP Hartowiec: wpis gminy i wpis z profilu gminy na Facebooku, cosinus 0,904,
# ta sama wieś, ten sam dzień — a model nadał im dwa różne nagłówki, więc oś
# tekstu dała 0,44 i nie miał kto orzec.
SEMANTIC_DUPLICATE_UNDATED = 0.80


@dataclass(frozen=True)
class StoryKey:
    """
    Wpis w postaci, w jakiej pytamy „czy to ta sama sprawa".

    Osobny typ, a nie krotka parametrów, bo ten sam klucz składają cztery
    miejsca (feed, briefing, newsletter, narzędzie agenta) i każde z nich ma
    inny materiał pod ręką: feed zna embedding, newsletter go nie pobiera.
    Brakująca oś ma ZAWĘŻAĆ orzekanie, nie zmieniać reguł — dlatego wszystkie
    pola poza tekstem są opcjonalne.
    """
    tokens: frozenset[str]
    stems: frozenset[str]
    event_at: Optional[datetime] = None
    event_until: Optional[datetime] = None
    places: frozenset[str] = frozenset()
    embedding: Optional[tuple[float, ...]] = None


def story_key(
    article,
    embedding: Optional[Iterable[float]] = None,
) -> StoryKey:
    """Klucz porównania dla artykułu — tekst, termin, miejsca, semantyka."""
    tokens = _tokens(dedup_text(article))
    return StoryKey(
        tokens=tokens,
        stems=_stem_tokens(tokens),
        event_at=getattr(article, "event_at", None),
        event_until=getattr(article, "event_until", None),
        places=frozenset(places_in(
            getattr(article, "display_title", None) or getattr(article, "title", None),
            getattr(article, "content", None),
        )),
        embedding=tuple(embedding) if embedding is not None else None,
    )


def _term_axis(a: StoryKey, b: StoryKey) -> Optional[bool]:
    """
    Oś CZASU. `True` = terminy się zgadzają (dowód ZA), `False` = weto,
    `None` = któryś wpis terminu nie ma, więc oś nic nie mówi.

    Doba LOKALNA, nie moment w UTC — to ta sama reguła, którą dedup wydarzeń
    dostał 25.08.2026, a warstwa czasu utrwaliła 5.09. Feed jej nigdy nie miał
    i to była PIERWSZA z przyczyn nawrotu z 14.09: `dedup_text` wklejał termin
    jako token `ev%Y%m%d%H%M`, więc zapowiedź BEZ godziny (w bazie: lokalna
    północ, czyli 22:00 UTC dnia poprzedniego) miała inny token niż ta sama
    zapowiedź z godziną — i para nie była w ogóle porównywana. Skutek: wpis
    z terminem był w praktyce zwolniony z deduplikacji, a to właśnie zapowiedzi
    mają najwięcej przedruków: każde źródło opisuje je po swojemu, a od 16.09.2026
    wchodzą do feedu wszystkie naraz, w przeddzień wspólnego terminu.

    Godziny wymagamy tylko wtedy, gdy znają ją OBA wpisy — czyli z dokładnością
    SŁABSZEGO z dwóch terminów. Inaczej „pobór krwi 16 września" i „pobór krwi
    16 września o 8:00" pozostałyby dwoma zdarzeniami, a to jedno ogłoszenie
    przepisane przez drugie źródło.
    """
    if a.event_at is None or b.event_at is None:
        return None
    local_a, local_b = to_local(a.event_at), to_local(b.event_at)
    if local_a.date() != local_b.date():
        return False
    if is_all_day(a.event_at, a.event_until) or is_all_day(b.event_at, b.event_until):
        return True
    return (local_a.hour, local_a.minute) == (local_b.hour, local_b.minute)


def _place_axis(a: StoryKey, b: StoryKey) -> Optional[bool]:
    """
    Oś MIEJSCA. `False` = weto (rozłączne miejscowości), `None` = nie wiadomo.

    Pytamy wyłącznie o miejscowości GMINY (`alert_policy.places_in`) — jedna
    lista na projekt, nie druga kopia. Gdy któraś strona nie wymienia żadnej,
    oś milczy: komunikat Energi o Lipówce i o Przełęku ma dwa puste zbiory,
    więc rozstrzyga je oś czasu, nie ta.

    Nazwa gminy odjęta tak samo jak w `alert_policy.same_incident`: „Rybno"
    padające obok innych wsi bywa nazwą NADAWCY („Zakład Gospodarki Komunalnej
    w Rybnie"), nie miejscem zdarzenia.
    """
    places_a, places_b = _incident_places(a.places), _incident_places(b.places)
    if not places_a or not places_b:
        return None
    return not places_a.isdisjoint(places_b)


def _incident_places(places: frozenset[str]) -> frozenset[str]:
    """Miejsca zdarzenia — bez nazwy gminy, gdy padła obok innych wsi."""
    rest = frozenset(p for p in places if p != _GMINA_NAME)
    return rest or places


_GMINA_NAME = "Rybno"


def _cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def _text_says_duplicate(a: StoryKey, b: StoryKey) -> bool:
    """Oś TREŚCI po tekście — progi bez zmian, patrz komentarze przy stałych."""
    if not a.tokens or not b.tokens:
        return False
    if _similarity(a.tokens, b.tokens) >= SIMILARITY_THRESHOLD:
        return True
    return (
        len(a.stems) >= _STEM_MIN_TOKENS
        and len(b.stems) >= _STEM_MIN_TOKENS
        and _containment(a.stems, b.stems) >= STEM_CONTAINMENT_THRESHOLD
    )


async def fetch_article_embeddings(session, article_ids) -> dict:
    """
    Osadzenia artykułów do osi semantycznej — chunk 0, czyli tytuł z leadem.

    Jedno zapytanie na cały feed (~40 wierszy), nie jedno na parę. Wpisy bez
    osadzenia po prostu nie mają tej osi: `embedding_job` chodzi o 6:50 i 13:45,
    więc materiał z późniejszych okien wchodzi do feedu wcześniej, niż zostanie
    osadzony. To jest powód, dla którego semantyka NIE MOŻE być jedynym sędzią
    powtórek — musi zostać dokładką do osi, które działają od pierwszej minuty.

    Chunk 0, bo dalsze fragmenty długiego wpisu opisują szczegóły, a pytamy
    o to, czy dwa wpisy są O TYM SAMYM. Ta sama zasada co przy wydarzeniach,
    gdzie osadzany jest tytuł z opisem, a nie cała treść ogłoszenia.
    """
    from sqlalchemy import text as sql_text

    ids = [int(i) for i in article_ids]
    if not ids:
        return {}

    rows = await session.execute(sql_text("""
        SELECT source_id, embedding::text
        FROM document_embeddings
        WHERE source_type = 'article' AND chunk_index = 0
          AND source_id = ANY(:ids)
    """), {"ids": ids})

    osadzenia = {}
    for source_id, wektor in rows:
        if not wektor:
            continue
        try:
            osadzenia[int(source_id)] = tuple(
                float(x) for x in wektor.strip("[]").split(",")
            )
        except (ValueError, AttributeError):
            continue  # uszkodzony wiersz nie może wywrócić feedu
    return osadzenia


def same_story(a: StoryKey, b: StoryKey) -> bool:
    """
    Czy dwa wpisy opisują tę samą sprawę — jedyne miejsce, gdzie to orzekamy.

    Kolejność jest znacząca: najpierw WETA (bo odcinają bez względu na to, jak
    podobne są teksty), potem dowody. Dowód tekstowy zostaje nietknięty, żeby
    dzisiejsze zachowanie nie zmieniło się tam, gdzie działa; dowód semantyczny
    dokłada się WYŁĄCZNIE do wpisów o zgodnym terminie.
    """
    term = _term_axis(a, b)
    if term is False:
        return False
    if _place_axis(a, b) is False:
        return False

    if _text_says_duplicate(a, b):
        return True

    # Para BEZ terminu po obu stronach — dwie wiadomości, nie zapowiedzi.
    # Oś czasu nie ma tu czego powiedzieć, więc dowodem musi być potwierdzona
    # wspólna miejscowość i wyższy próg semantyczny (`SEMANTIC_DUPLICATE_UNDATED`).
    if a.event_at is None and b.event_at is None:
        if _place_axis(a, b) is not True:
            return False
        if a.embedding is None or b.embedding is None:
            return False
        return _cosine(a.embedding, b.embedding) >= SEMANTIC_DUPLICATE_UNDATED

    # Dowód semantyczny wymaga POTWIERDZENIA obu pozostałych osi: zgodnego
    # terminu ORAZ wspólnej miejscowości. Nie jest to ostrożność na wyrost —
    # to wynik pomiaru. Przy zgodnym terminie, ale MILCZĄCEJ osi miejsca
    # (żaden wpis nie wymienia wsi z gminy) para komunikatów Energi o dwóch
    # różnych wsiach spoza gminy ma cosinus 0,869 i sklejała się w jeden wpis:
    # „Wyłączenie 13.09 17:48–20:30 — Wysoka" i „… — Prioma, Rutkowice"
    # to jedno zdarzenie rozpisane na rejony, ale dla mieszkańca Priomy
    # zniknięcie jego wsi z komunikatu jest utratą informacji.
    #
    # Milczenie osi ZAWĘŻA orzekanie i tak ma być: brak dowodu nie jest dowodem.
    # Para bez wspólnej miejscowości wciąż może zostać zwinięta przez oś tekstu
    # (nabór na „Czek Turystyczny" nie wymienia żadnej wsi, a zwija go Jaccard).
    if term is not True or _place_axis(a, b) is not True:
        return False
    if a.embedding is None or b.embedding is None:
        return False
    return _cosine(a.embedding, b.embedding) >= SEMANTIC_DUPLICATE


def collapse_duplicates(
    items: Iterable[D],
    key_of: Callable[[D], StoryKey],
) -> list[D]:
    """
    Ten sam materiał z dwóch źródeł zostawia raz — wygrywa pozycja wcześniejsza,
    więc kolejność wejściowa musi już być rankingiem.

    Powstało po tym, jak jedno wyłączenie prądu w Rybnie stanęło w feedzie dwa
    razy obok siebie (kanał „planowane" i „bieżące" Energi), oba jako awaria.
    Deduplikacja po `external_id` łapie tylko wpisy o wspólnym identyfikatorze —
    to jest siatka bezpieczeństwa na przedruki między źródłami.

    Samo orzekanie mieszka w `same_story` (trzy osie, każda z prawem weta) —
    tutaj zostaje wyłącznie przebieg po liście.

    ⚠️ `key_of` jest WYMAGANE i nie ma wariantu „sam tekst". Był przez pół dnia
    14.09.2026 i natychmiast pokazał, czemu nie może istnieć: klucz zbudowany
    z samego tekstu nie zna terminu, więc oś czasu milczała, a dwa wyłączenia
    Energi z RÓŻNYCH dni skleiły się w jedno (`test_grounding` złapał to od razu).
    Dwie ścieżki orzekania to dwa różne zachowania tej samej polityki — a cała
    ta warstwa powstała właśnie po to, żeby zachowanie było jedno.
    """
    kept: list[D] = []
    seen: list[StoryKey] = []

    for item in items:
        key = key_of(item)
        if key.tokens and any(same_story(key, other) for other in seen):
            continue
        kept.append(item)
        seen.append(key)

    return kept


T = TypeVar("T")


def diversify(
    items: Iterable[T],
    key: Callable[[T], object],
    gap: int = SOURCE_GAP,
    preceding: Optional[Iterable[T]] = None,
) -> list[T]:
    """
    Przeplata posortowaną listę tak, by dwa wpisy z tego samego źródła dzieliło
    co najmniej `gap` innych. Gdy nie ma alternatywy, bierze następny w kolejności
    — dywersyfikacja nigdy nie usuwa treści, tylko zmienia porządek.

    `preceding` to wpisy już umieszczone przed tą listą (np. przypięte awarie);
    bez nich pierwszy element mógłby powtórzyć źródło poprzedniego wpisu.
    """
    pending = list(items)
    placed: list[T] = list(preceding or [])
    offset = len(placed)
    while pending:
        recent = {key(i) for i in placed[-gap:]} if gap else set()
        idx = next((n for n, item in enumerate(pending) if key(item) not in recent), 0)
        placed.append(pending.pop(idx))
    return placed[offset:]
