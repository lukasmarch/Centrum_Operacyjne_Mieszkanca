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
from datetime import datetime, time, timedelta
from typing import Callable, Iterable, Optional, TypeVar
from zoneinfo import ZoneInfo

from sqlalchemy import and_, cast, or_
from sqlalchemy.types import Time

from src.services.alert_policy import is_foreign_region, places_in
from src.services.weather_alert import expired as weather_alert_expired
from src.services.weather_alert import is_weather_alert

# Rozpad połowiczny świeżości: po 18 h wpis waży połowę tego, co świeży
FRESHNESS_HALFLIFE_H = 18.0

# Zdarzenia przyszłe (wyłączenie prądu za trzy dni) też tracą na wadze, tylko
# wolniej — zapowiedź na jutro musi wygrywać z zapowiedzią na przyszły tydzień
LOOKAHEAD_HALFLIFE_H = 48.0

# Ile innych wpisów musi dzielić dwa wpisy z tego samego źródła
SOURCE_GAP = 2

# Awaria bez znanego terminu trafia na górę feedu tylko dopóki jest „teraz"
AWARIA_PIN_HOURS = 24

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


def publishable_conditions(article_model):
    """
    Warunki SQL „to nadaje się do pokazania mieszkańcowi" — wspólne dla feedu
    i briefingu. Dopisanie kolejnej reguły ma działać w obu miejscach naraz.
    """
    return [
        article_model.is_filler == False,        # noqa: E712 — SQLAlchemy
        article_model.is_promotional == False,   # noqa: E712
    ]


def still_relevant_event(article_model, now: Optional[datetime] = None):
    """
    Warunek SQL „termin tego wpisu jeszcze nie minął" — dla okna feedu.

    `event_until` bywa puste: zna je Energa (z komunikatu) i alert meteo,
    nie zna go zapowiedź czytana przez model, bo źródło podaje samą godzinę
    rozpoczęcia. Bez domyślnego czasu trwania taka zapowiedź wypadała z feedu
    w dniu, w którym była aktualna — patrz `DEFAULT_EVENT_DURATION_H`.

    Wpis bez godziny (`event_at` o północy) trwa do końca swojego dnia, nie
    trzy godziny: „Wielkie Otwarcie 22 sierpnia" nie kończy się o 3 nad ranem.
    Ta sama reguła co `utils/eventTime.isAllDay` na froncie.

    Odejmujemy od `now`, zamiast dodawać do kolumny: warunek zostaje wtedy
    porównaniem kolumny ze stałą, więc indeks na `event_at` nadal działa.
    """
    now = now or datetime.utcnow()
    return or_(
        article_model.event_until >= now,
        and_(
            article_model.event_until.is_(None),
            article_model.event_at.isnot(None),
            or_(
                article_model.event_at >= now - timedelta(hours=DEFAULT_EVENT_DURATION_H),
                and_(
                    cast(article_model.event_at, Time) == time(0, 0),
                    article_model.event_at >= now - timedelta(days=1),
                ),
            ),
        ),
    )


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
_DAY_WORDS = {-1: "wczoraj", 0: "dziś", 1: "jutro", 2: "pojutrze"}


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

    ⚠️ `summary_generator._time_label` robi to samo w nawiasach kwadratowych.
    Scalenie wymaga przebiegu `scripts.test_summary_headline` — briefing jest
    wrażliwy na brzmienie znaczników, więc nie robimy tego przy okazji.
    """
    now = now or datetime.utcnow()
    today = _local(now).date()

    if event_at:
        start = _local(event_at)
        span = f"{start:%H:%M}"
        if event_until:
            span += f"–{_local(event_until):%H:%M}"
        word = _DAY_WORDS.get((start.date() - today).days)
        when = f"{word} {span}" if word else f"{start:%d.%m.%Y} {span}"
        if event_until and event_at <= now <= event_until:
            return f"ZDARZENIE {when} — TRWA TERAZ"
        if (event_until or event_at) < now:
            return f"ZDARZENIE {when} — już się zakończyło"
        return f"ZDARZENIE {when}"

    if not published_at:
        return "bez daty"

    stamp = _local(published_at)
    word = _DAY_WORDS.get((stamp.date() - today).days)
    when = f"{word} {stamp:%H:%M}" if word else f"{stamp:%d.%m.%Y}"
    return f"{published_prefix}{when}"


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
    Olsztyn nie był karany za to, że źródło jest wojewódzkie. Ocena może wpis
    wyłącznie PODNIEŚĆ: model bywa skąpy, a `is_local_article` zna źródła.
    """
    if locality is None and title is None and content is None:
        return 1.0  # wywołanie bez materiału — nie zgadujemy

    if is_foreign_region(title, content):
        return LOCALITY_FACTOR_FOREIGN  # cudze Rybno

    local = (
        (locality is not None and locality >= 3)
        or is_local_article(source_name, title, content)
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
        * locality_factor(locality, source_name, title, content)
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
    """Zbiór znaczących słów — bez ogonków, emoji i interpunkcji."""
    flat = unicodedata.normalize("NFKD", (text or "").lower())
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


def dedup_text(article) -> str:
    """
    Materiał wpisu w postaci, w jakiej porównujemy go z innymi.

    Po kategoryzacji porównujemy sam `display_title`: depeszowy nagłówek modelu
    streszcza temat, a summary rozprasza sygnaturę (każde źródło streszcza inny
    aspekt tego samego komunikatu). 12.08.2026 nabór na azbest w czterech
    redakcjach (BIP, strona gminy, dwa profile FB) zajął trzy pierwsze miejsca
    feedu — podobieństwo pełnych tekstów nie przekraczało 0,52 przy progu 0,72.
    Wpisy sprzed kategoryzacji (okno 6:00–6:15) porównujemy po staremu.

    Termin zdarzenia wchodzi jako zwarty token `ev…` — dwa wyłączenia w Rybnie
    mają identyczny tytuł i różnią się wyłącznie datą; poprzedni format
    `%Y-%m-%d %H:%M` rozpadał się w `_tokens` na dwuznaki i ginął w filtrze
    długości, więc daty realnie nie było w sygnaturze.
    """
    display = getattr(article, "display_title", None)
    if display:
        base = display
    else:
        body = (article.content or article.summary or "")[:300]
        base = f"{article.title or ''} {body}"
    event_at = getattr(article, "event_at", None)
    return f"ev{event_at:%Y%m%d%H%M} {base}" if event_at else base


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

_EVENT_TOKEN_RE = re.compile(r"^ev\d{12}$")


def _stem_tokens(tokens: frozenset[str]) -> frozenset[str]:
    """
    Rdzenie słów — zgrubne ścięcie polskiej fleksji, przez którą „Rybno" i
    „w Rybnie" albo „usuwanie" i „usuwaniu" były różnymi tokenami i ten sam
    komunikat w dwóch redakcjach nie przekraczał progu podobieństwa.
    """
    stems = set()
    for word in tokens:
        if _EVENT_TOKEN_RE.match(word):
            continue  # termin porównujemy osobno, nie jako słowo
        stem = word.rstrip("aeiouy")[:6]
        stems.add(stem if len(stem) >= 3 else word)
    return frozenset(stems)


def _containment(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def collapse_duplicates(items: Iterable[D], text_of: Callable[[D], str]) -> list[D]:
    """
    Ten sam materiał z dwóch źródeł zostawia raz — wygrywa pozycja wcześniejsza,
    więc kolejność wejściowa musi już być rankingiem.

    Powstało po tym, jak jedno wyłączenie prądu w Rybnie stanęło w feedzie dwa
    razy obok siebie (kanał „planowane" i „bieżące" Energi), oba jako awaria.
    Deduplikacja po `external_id` łapie tylko wpisy o wspólnym identyfikatorze —
    to jest siatka bezpieczeństwa na przedruki między źródłami.

    Dwa testy podobieństwa: Jaccard pełnych tokenów (przedruki niemal dosłowne)
    oraz zawieranie rdzeni słów (ten sam komunikat w różnych redakcjach —
    12.08.2026 nabór na azbest z BIP, strony gminy i FB zajął trzy pierwsze
    miejsca feedu naraz). Blokada nadrzędna: wpisy z RÓŻNYMI terminami zdarzeń
    nie są duplikatami nigdy — dwa wyłączenia Energi w tej samej wsi mają
    identyczne tytuły i różnią się wyłącznie datą.
    """
    kept: list[D] = []
    seen: list[tuple[frozenset[str], frozenset[str], frozenset[str]]] = []

    for item in items:
        tokens = _tokens(text_of(item))
        events = frozenset(t for t in tokens if _EVENT_TOKEN_RE.match(t))
        stems = _stem_tokens(tokens)

        duplicate = False
        if tokens:
            for seen_tokens, seen_stems, seen_events in seen:
                if events and seen_events and events.isdisjoint(seen_events):
                    continue  # różne terminy = różne zdarzenia
                if _similarity(tokens, seen_tokens) >= SIMILARITY_THRESHOLD:
                    duplicate = True
                    break
                if (
                    len(stems) >= _STEM_MIN_TOKENS
                    and len(seen_stems) >= _STEM_MIN_TOKENS
                    and _containment(stems, seen_stems) >= STEM_CONTAINMENT_THRESHOLD
                ):
                    duplicate = True
                    break
        if duplicate:
            continue
        kept.append(item)
        seen.append((tokens, stems, events))

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
