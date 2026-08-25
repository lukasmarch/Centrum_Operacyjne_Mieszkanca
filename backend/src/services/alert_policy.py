"""
Polityka alertów push — jedno miejsce, w którym stoi, co budzi telefon.

Feed i push mają różne progi i to jest cała istota tego pliku. Feed może pokazać
wyłączenie prądu w Płośnicy: mieszkaniec sam zdecyduje, czy go to obchodzi.
Push nie pyta — wchodzi na ekran blokady, więc kosztem pomyłki jest wypisanie się
z powiadomień. Dlatego przepuszczamy tylko część tego, co feed oznacza jako
„Awaria": zdarzenie musi być POWAŻNE, musi dotyczyć GMINY RYBNO i musi być
sprawą NAJBLIŻSZYCH GODZIN.

Trzy bramki, wszystkie muszą puścić:

1. RODZAJ  — prąd, woda, pożar, wypadek, gaz/ewakuacja. Zamknięta lista, nie
             kategoria z AI: kategoryzacja chodzi o 6:15 i 13:15, a wyłączenie
             zescrapowane o 18:05 czekałoby na push do rana. Tu decyduje sam
             tekst, więc alert działa niezależnie od tego, czy AI już przeszło.
2. MIEJSCE — w tekście musi paść nazwa z gminy Rybno. Feed Energi jest zawężony
             filtrem źródła do całego powiatu (płośnic, iłowo, lidzbark…), więc
             bez tej bramki mieszkaniec Rybna dostawał budzik o wyłączeniu
             w Płośnicy — dokładnie to zdarzyło się 27.07.2026.
3. CZAS    — zdarzenie przed nami albo trwa. O zakończonej awarii i o pożarze
             sprzed trzech dni nikogo nie powiadamiamy.

Konsument: `scheduler/alert_push_job.py`. Funkcje są czyste (bez bazy i sieci),
żeby dało się je sprawdzić na realnych tytułach — `scripts/test_alert_policy.py`.
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from src.services import time_span

# Zdarzenie z terminem (zapowiedziane wyłączenie prądu) budzi telefon dopiero
# wtedy, gdy da się coś z tym zrobić — naładować telefon, nabrać wody. Zapowiedź
# na przyszły czwartek to sprawa feedu, nie powiadomienia.
PUSH_LOOKAHEAD_H = 36.0

# Zdarzenie bez terminu (pożar, wypadek) — liczy się moment publikacji. Wpis
# starszy niż doba jest relacją, nie ostrzeżeniem.
MAX_AGE_H = 24.0

# Ile godzin po zescrapowaniu wpis BEZ TERMINU może jeszcze wywołać push.
# Zabezpieczenie na wypadek, gdyby job stał (restart, awaria VPS): po powrocie
# ma nie wystrzelić serią powiadomień o zdarzeniach, które dawno minęły.
MAX_SCRAPE_LAG_H = 12.0


@dataclass(frozen=True)
class Alert:
    """Decyzja polityki: co wysyłamy i pod jakim nagłówkiem."""
    kind: str          # prad | woda | pozar | wypadek | gaz
    label: str         # nagłówek powiadomienia, np. „Wyłączenie prądu"
    places: tuple[str, ...]  # nazwy z gminy Rybno, które padły w tekście


def _flat(text: Optional[str]) -> str:
    """
    Tekst bez ogonków i wielkości liter — dopasowania i tak są przybliżone.

    „ł" wymaga osobnej podmiany: jako jedyna polska litera nie rozkłada się
    w NFKD na znak bazowy i znak łączący, więc samo odsianie `combining()`
    zostawiało „wyłączenie" z „ł" i wzorzec na wyłączenia prądu nie trafiał
    w nic. Ten błąd nie miał prawa się ujawnić inaczej niż testem.
    """
    lowered = (text or "").lower().replace("ł", "l")
    stripped = unicodedata.normalize("NFKD", lowered)
    return "".join(c for c in stripped if not unicodedata.combining(c))


# --- bramka 1: rodzaj zdarzenia ---------------------------------------------

# Wzorce działają na tekście BEZ ogonków (patrz `_flat`), stąd „prad", „pozar".
# Kolejność ma znaczenie: pierwszy trafiony rodzaj wygrywa, a wyłączenie prądu
# opisane jako „przerwa w dostawie energii" nie ma być wypadkiem.
_INCIDENTS: tuple[tuple[str, str, str], ...] = (
    (
        "prad",
        "Wyłączenie prądu",
        r"wylaczeni\w*\s+(prad|planow|biezac)|przerw\w*\s+w\s+dostaw\w*\s+(energii|pradu)"
        r"|brak\w*\s+pradu|bez\s+pradu|awari\w*\s+(zasilania|sieci\s+energetycznej|energetyczn\w+)",
    ),
    (
        "woda",
        "Przerwa w dostawie wody",
        r"brak\w*\s+wody|bez\s+wody|przerw\w*\s+w\s+dostaw\w*\s+wody|awari\w*\s+(wodociag\w*|hydrofor\w*|sieci\s+wodociagowej)"
        r"|skazeni\w*\s+wody|zakaz\w*\s+spozy\w*\s+wody|woda\s+niezdatna|nie\s+nadaje\s+sie\s+do\s+spozycia",
    ),
    (
        "gaz",
        "Zagrożenie — ewakuacja",
        r"ulatnian\w*\s+(sie\s+)?gaz|wyciek\w*\s+gazu|ewakuacj|skazeni\w*\s+(powietrza|terenu)|zagrozenie\s+chemiczne",
    ),
    (
        "pozar",
        "Pożar",
        # `(?!n)` odcina „straż pożarna" — inaczej każdy post OSP o zawodach,
        # nowym wozie czy Dniu Strażaka byłby alertem pożarowym.
        r"pozar(?!n)|plon\w*\s+(dom|budynek|stodol|las|poddasz)|zapalil\w*\s+sie|splonel",
    ),
    (
        "wypadek",
        "Wypadek",
        r"wypadek|wypadku|zderzeni\w*\s+(sie\s+)?(dwoch\s+)?(pojazd|samochod|aut)|czolowe\s+zderzenie"
        r"|potracen\w*|potracil|dachowa\w*|karambol|smiertelny\s+wypadek|ofiar\w*\s+wypadku"
        r"|utonie\w*|utonal|utonela|reanimac\w*|smiglowiec\s+lpr|lotnicze\s+pogotowie",
    ),
)

_INCIDENT_RE = tuple((kind, label, re.compile(pattern)) for kind, label, pattern in _INCIDENTS)

# Wpisy, które mówią o zdarzeniu, ale go nie zgłaszają: profilaktyka, relacje,
# zbiórki, zawody OSP. Bez tej listy „Bezpieczna woda — bezpieczne wakacje"
# i „Konkurs plastyczny o tematyce pożarowej" trafiały do powiadomień.
_NOT_AN_INCIDENT = re.compile(
    r"cwiczeni|szkoleni|profilakty|kampani|konkurs|apel\b|porad\w*|pogadank|prelekcj"
    r"|festyn|piknik|zawod\w*\s+(sportowo-)?pozarnicz|turniej|dzien\s+strazaka|jubileusz|rocznic"
    r"|zbiork\w*\s+(pieniedzy|funduszy)|dofinansowani|zakup\w*\s+(wozu|samochodu|sprzetu)|przekazani\w*\s+sprzetu"
    r"|jak\s+(uniknac|zachowac|postepowac)|pamietaj\w*,\s*ze|przypominamy|statystyk"
)


def incident_of(title: Optional[str], content: Optional[str] = None) -> Optional[tuple[str, str]]:
    """Rodzaj zdarzenia (kind, label) albo None, gdy tekst nie jest zgłoszeniem."""
    text = _flat(f"{title or ''} {content or ''}")
    if not text.strip():
        return None
    if _NOT_AN_INCIDENT.search(text):
        return None
    for kind, label, pattern in _INCIDENT_RE:
        if pattern.search(text):
            return kind, label
    return None


# --- bramka 2: miejsce -------------------------------------------------------

# Sołectwa gminy Rybno (za `auth/schemas.py: AVAILABLE_LOCATIONS`), bez „Domki
# letniskowe" i sufiksów stref śmieciowych R1/R2 — to nazwy z harmonogramu
# odbioru odpadów, w tekście prasowym nigdy nie padają.
#
# Formy odmienione wypisane wprost, zamiast doklejać dowolną końcówkę do rdzenia.
# Automat brzmi kusząco, ale na tej liście są nazwy, które w dopełniaczu zlewają
# się ze słowami pospolitymi: „Grądy" z gradem, „Wery" z wersją, „Rumian"
# z rumiankiem, „Prusy" z pruskim. Alert ma budzić ludzi w nocy — wolimy przegapić
# egzotyczną odmianę niż wysłać powiadomienie z powodu opadów gradu.
# Wzorce działają na tekście bez ogonków (`_flat`).
_PLACES: tuple[tuple[str, str], ...] = (
    ("Rybno", r"rybn(o|a|ie|em)"),
    ("Dębień", r"debien(ia|iu)?"),
    ("Grabacz", r"grabacz(a|u|em)?"),
    ("Gralewo", r"gralew(o|a|ie|em)"),
    ("Gronowo", r"gronow(o|a|ie|em)"),
    ("Groszki", r"groszk(i|ach|ow|om|ami)"),
    ("Grądy", r"grad(y|ach|om|ami)"),
    ("Hartowiec", r"hartow(iec|cu|ca|cem)"),
    ("Jeglia", r"jegli(a|ii|i|e)"),
    ("Kopaniarze", r"kopaniarz(e|ach|y|om|ami)"),
    ("Koszelewki", r"koszelewk(i|ach|om|ami)"),
    ("Koszelewy", r"koszelew(y|ach|om|ami)"),
    ("Naguszewo", r"naguszew(o|a|ie|em)"),
    ("Nowa Wieś", r"now(a|ej)\s+w(ies|si)"),
    ("Prusy", r"prus(y|ach|om|ami)"),
    ("Rapaty", r"rapat(y|ach|om|ami)"),
    ("Rumian", r"rumian(ie|a|em|y)?"),
    ("Szczupliny", r"szczuplin(y|ach|om|ami)"),
    ("Truszczyny", r"truszczyn(y|ach|om|ami)"),
    ("Tuczki", r"tuczk(i|ach|om|ami)"),
    ("Wery", r"wer(y|ach|om|ami)"),
    ("Żabiny", r"zabin(y|ach|om|ami)"),
)

GMINA_RYBNO_PLACES: tuple[str, ...] = tuple(place for place, _ in _PLACES)

_PLACE_RE = tuple(
    (place, re.compile(r"\b" + pattern + r"\b")) for place, pattern in _PLACES
)


def places_in(title: Optional[str], content: Optional[str] = None) -> tuple[str, ...]:
    """Nazwy miejscowości z gminy Rybno, które padły w tekście."""
    text = _flat(f"{title or ''} {content or ''}")
    return tuple(place for place, pattern in _PLACE_RE if pattern.search(text))


def norm_place(value: Optional[str]) -> str:
    """
    Nazwa miejscowości do porównania: bez ogonków, wielkości liter i ogona
    rejonu wywozu. Konto potrafi mieć zapisane „Rybno R1" (patrz
    `AVAILABLE_LOCATIONS` — to lista rejonów odbioru odpadów, nie miejscowości),
    a Energa mówi po prostu „Rybno".

    Mieszkało w `push_service`; przeniesione tutaj 25.08.2026, gdy tej samej
    odpowiedzi zaczęła potrzebować karta alertu na stronie głównej. Lista
    miejscowości i tak stoi w tym module — normalizacja należy do niej.
    """
    lowered = (value or "").strip().lower().replace("ł", "l")
    stripped = unicodedata.normalize("NFKD", lowered)
    flat = "".join(c for c in stripped if not unicodedata.combining(c))
    return re.sub(r"\s+r\d+$", "", flat)


def concerns(
    location: Optional[str],
    title: Optional[str],
    content: Optional[str] = None,
) -> bool:
    """
    Czy komunikat dotyczy miejscowości czytelnika.

    Trzy razy „tak, dotyczy": gdy nie wiemy, gdzie mieszka (konto bez
    lokalizacji, gość bez konta), gdy komunikat nie wymienia żadnej wsi
    (ostrzeżenie meteo dla powiatu) i gdy jego wieś jest na liście.
    Domyślne „tak" jest celowe — alert, który nie dotarł, jest gorszy
    niż alert o sąsiedniej wsi. Tę samą regułę stosuje push
    (`push_service.send_to_category`).
    """
    if not location:
        return True
    places = places_in(title, content)
    if not places:
        return True
    return norm_place(location) in {norm_place(p) for p in places}


# Energa opisuje wyłączenia REJONEM ENERGETYCZNYM, nie gminą, i wpisuje go
# w tytuł: „Wyłączenie awaryjne - Region Mława - Rybno gmina wiejska". Powiat
# działdowski leży w całości w Regionie Mława (22.08.2026: 35 wpisów Mława,
# 1 Gostynin — i ten jeden był właśnie fałszywką).
_OUR_REGION = "mlawa"

# Wzorzec celowo wąski — wymaga myślnika po nazwie, czyli dokładnego formatu
# tytułu Energi. Zdanie „w naszym regionie warmińsko-mazurskim" z dowolnego
# innego źródła NIE MOŻE tu wpaść, bo odrzucenie działa na oślep dla wszystkich.
_REGION_RE = re.compile(r"\bregion\s+([a-z]+)\s*-")


def is_foreign_region(title: Optional[str], content: Optional[str] = None) -> bool:
    """
    Czy wpis dotyczy rejonu, którego NIE obsługujemy — mimo że padła w nim
    nazwa z gminy Rybno.

    22.08.2026 o 9:34 poszło powiadomienie „Wyłączenie prądu — Rybno · dziś
    06:21–13:00" z wpisu „Wyłączenie awaryjne - Region Gostynin - Rybno gmina
    wiejska" (Antosin, Koszajec, Matyldów, Rybionek, Wężyki). To gmina Rybno
    w powiecie SOCHACZEWSKIM, 180 km stąd. `places_in` odpowiada na pytanie
    „czy nazwa padła", a nie „gdzie ta nazwa leży", i samą listą tego nie
    rozstrzygnie — nazwa jest dosłownie ta sama. Ta sama pułapka, przez którą
    grupa `gminarybnoforum` okazała się cudzą gminą.

    Odrzucamy WYŁĄCZNIE jawnie obcy rejon. Brak słowa „Region" nie znaczy nic:
    tak wygląda każde źródło poza Energą, a milczenie nie jest zaprzeczeniem.
    """
    match = _REGION_RE.search(_flat(f"{title or ''} {content or ''}"))
    return bool(match) and match.group(1) != _OUR_REGION


# --- bramka 3: czas ----------------------------------------------------------


def is_timely(
    published_at: Optional[datetime],
    scraped_at: Optional[datetime],
    event_at: Optional[datetime] = None,
    event_until: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> bool:
    """Czy to jeszcze sprawa „teraz albo zaraz". Wszystkie czasy naiwne UTC."""
    now = now or datetime.utcnow()

    # Zdarzenie ze znanym terminem — o wszystkim decyduje termin, nie moment
    # ogłoszenia. Wyłączenie zapowiedziane pięć dni wcześniej ma obudzić telefon
    # dopiero dobę przed, więc ten sam wpis bywa oceniany wiele razy, zanim
    # przejdzie: bramka „kiedy zescrapowane" byłaby tu wprost szkodliwa.
    if event_at:
        if event_until and now > event_until:
            return False  # po zdarzeniu
        hours_ahead = (event_at - now).total_seconds() / 3600
        if hours_ahead > PUSH_LOOKAHEAD_H:
            return False  # jeszcze za wcześnie, wróci do oceny za kwadrans
        return hours_ahead > -MAX_AGE_H  # zaczęło się wczoraj i nikt nie zamknął

    # Zdarzenie bez terminu (pożar, wypadek): job stał — restart, awaria VPS —
    # więc po powrocie nie nadrabiamy serii powiadomień o rzeczach minionych.
    if scraped_at and now - scraped_at > timedelta(hours=MAX_SCRAPE_LAG_H):
        return False

    reference = published_at or scraped_at
    if reference is None:
        return False
    return (now - reference).total_seconds() / 3600 <= MAX_AGE_H


# --- termin wyczytany z treści ------------------------------------------------


def span_from_text(
    title: Optional[str],
    content: Optional[str],
    published_at: Optional[datetime],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Godziny zdarzenia wyjęte z komunikatu, gdy kategoryzacja ich nie wpisała.

    24.08.2026 o 6:08 push wysłał alarm o wyłączeniu prądu, które skończyło się
    poprzedniego wieczoru. Post ZGK mówił „W godzinach 16.00 - 19.00", ale bez
    daty — model nie zaryzykował `event_at`, więc `is_timely` mierzyła wiek od
    publikacji (24 h) i o świcie wpis wciąż był „na czasie". Bramka „po
    zdarzeniu" istniała; brakowało jej wyłącznie `event_until`.

    Liczymy TUTAJ, a nie w `is_timely`, bo zapis „w godzinach 8:00–16:00" bywa
    godzinami urzędowania. Zanim tu dojdziemy, wpis przeszedł już bramkę rodzaju
    i miejsca — mówi więc o awarii w gminie Rybno, nie o biurze.

    Drugi bezpiecznik: zakres kończący się PRZED publikacją odrzucamy. Awarię
    ogłasza się przed nią albo w trakcie; „awaria trwała od 8:00 do 15:00"
    w poście z 18:00 to relacja, a relacji nie wysyłamy pushem.
    """
    start, end = time_span.parse_span(f"{title or ''}\n{content or ''}", published_at)
    if end is not None and published_at is not None and end < published_at:
        return None, None
    return start, end


# --- decyzja -----------------------------------------------------------------


def signature(
    title: Optional[str],
    content: Optional[str] = None,
    published_at: Optional[datetime] = None,
    event_at: Optional[datetime] = None,
    event_until: Optional[datetime] = None,
) -> Optional[tuple]:
    """
    Klucz „to jest ten sam alert" — rodzaj, miejsca i termin zdarzenia.

    24.08.2026 o 6:08 poszły dwa powiadomienia sekundę po sobie: komunikat ZGK
    o wyłączeniu prądu i jego przedruk na profilu Syli. Zwijanie po tekście
    (`feed_policy.collapse_duplicates`) tej pary nie łączy — kategoryzacja
    napisała im różne nagłówki („Wyłączenie prądu w Rybnie" i „Przerwa
    w dostawie prądu w Rybnie"), a to podobieństwo 0,43 przy progu 0,72.
    Progi feedu są skalibrowane dla feedu i nie ma powodu ich pod push naginać.

    Push i tak wie więcej niż wyszukiwarka podobieństw: dla mieszkańca liczy się
    CO, GDZIE i KIEDY. Dwa wpisy o tym samym rodzaju zdarzenia, w tych samych
    miejscowościach i o tym samym terminie to jedno powiadomienie, choćby
    napisano je zupełnie innymi słowami.

    Termin liczy się tak samo jak w `evaluate` — z treści, gdy w bazie go nie ma.
    Bez tego przedruk z pustym `event_at` miałby inny klucz niż oryginał.

    `None` = wpis nie jest alertem (nie ma czego zwijać).
    """
    incident = incident_of(title, content)
    if incident is None:
        return None

    places = places_in(title, content)
    if not places:
        return None

    if event_at is None and event_until is None:
        event_at, _ = span_from_text(title, content, published_at)

    # Termin do DOBY, nie do minuty. Energa zapowiada jeden dzień kilkoma
    # wpisami — 23.08 wieczorem poszły dwa powiadomienia o wyłączeniach 25.08
    # w Rybnie (09:30 i 10:00, różne ulice). Dla mieszkańca to jedna wiadomość:
    # „25 sierpnia nie będzie prądu, szczegóły w serwisie". Miejscowości zostają
    # w kluczu, więc wyłączenie w Koszelewach tego samego dnia to nadal osobny
    # alert.
    #
    # Doba LOKALNA, nie UTC: zdarzenie o 00:30 czasu polskiego wypada w bazie
    # na dzień wcześniejszy i inaczej rozjechałoby się z sąsiednim wpisem.
    #
    # ⚠️ Cena tej decyzji: awaria poranna i wieczorna w tej samej wsi mają jeden
    # klucz, więc druga nie obudzi telefonu (pamięć trwa RECENT_PUSH_MEMORY_H).
    event_day = time_span.to_local(event_at).date() if event_at else None

    return (incident[0], frozenset(places), event_day)


def evaluate(
    title: Optional[str],
    content: Optional[str] = None,
    published_at: Optional[datetime] = None,
    scraped_at: Optional[datetime] = None,
    event_at: Optional[datetime] = None,
    event_until: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> Optional[Alert]:
    """
    Czy ten wpis ma obudzić telefon. `None` = nie wysyłamy.

    Kolejność bramek jest celowa — najpierw najtańsza i najczęściej odrzucająca.
    """
    incident = incident_of(title, content)
    if incident is None:
        return None

    places = places_in(title, content)
    if not places:
        return None  # zdarzenie spoza gminy Rybno (Płośnica, Iłowo, Lidzbark…)

    if is_foreign_region(title, content):
        return None  # cudze Rybno — patrz `is_foreign_region`

    if event_at is None and event_until is None:
        event_at, event_until = span_from_text(title, content, published_at)

    if not is_timely(published_at, scraped_at, event_at, event_until, now):
        return None

    kind, label = incident
    return Alert(kind=kind, label=label, places=places)
