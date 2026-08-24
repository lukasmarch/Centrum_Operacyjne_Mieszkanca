"""
Jednostki gminy z BIP — adresy, telefony, kierownicy (etap 7 pkt 5, 24.08.2026)

**Po co, skoro „mamy godziny urzędu w kodzie".** Bo nie mieliśmy. Stała
`OFFICE_HOURS` w `ai/tools/daily.py` niosła dwie pozycje i obie były błędne:

    urząd:  7:15–15:15          → naprawdę 8:00–16:00 (gminarybno.pl)
    GOPS:   ul. Lubawska 15,    → naprawdę ul. Zajeziorna 58,
            tel. 23 696 60 55         tel. 23 696 63 39

Adres i telefon GOPS to były dane Urzędu Gminy. Agent podawał je mieszkańcom
z pełnym przekonaniem, bo stała w kodzie nie ma jak zdezaktualizować się
głośno — nie ma daty, nie ma źródła, nikt jej nie odświeża.

**Zakres to jawna lista** (`INSTITUTIONS`), nie pełzanie po drzewie — ta sama
zasada co `DEFAULT_SECTIONS` w `bip_knowledge`. BIP ma pod /2/ dokładnie
dwanaście jednostek i ta lista zmienia się raz na lata; wykrywanie ich w locie
kosztowałoby więcej niż daje.

⚠️ **Godzin pracy tu nie ma i nie będzie.** BIP publikuje je wyłącznie dla
urzędu (a i to na stronie gminy, nie w BIP). Scraper NIE dotyka kolumn `hours`
i `scope` — są ręczne. Nadpisywanie ich pustką przy każdym niedzielnym
przebiegu kasowałoby to, co ktoś wpisał; zmyślanie godzin szkoły jest gorsze
niż przyznanie, że ich nie znamy.

⚠️ **E-mail jest na BIP maskowany** (`<e-mail>` podmieniany JS-em), więc pole
zostaje puste. Nie warto tego obchodzić: telefon i adres wystarczą, a udawany
adres e-mail byłby gorszy od żadnego.

Użycie: `python -m scripts.run_bip_institutions [--dry]`
"""
import asyncio
import hashlib
import html
import re
from dataclasses import dataclass
from typing import Optional

import httpx

from src.scrapers.bip_knowledge import BIP_HEADERS
from src.utils.logger import setup_logger

logger = setup_logger("BipInstitutions")

BIP_BASE = "https://bip.gminarybno.pl"

# Godziny urzędu NIE są na BIP — stoją na stronie gminy. Jedna wartość, jedno
# miejsce; gdyby się zmieniła, tu ją poprawiamy.
GMINA_WWW = "https://gminarybno.pl"


@dataclass
class InstitutionSpec:
    """Jednostka do pobrania: klucz, rodzaj i ścieżka na BIP."""
    slug: str
    kind: str
    path: Optional[str]          # None = brak strony na BIP (dane ręczne)
    fallback_name: str


# Kolejność ma znaczenie tylko dla czytelności logu.
INSTITUTIONS: tuple[InstitutionSpec, ...] = (
    InstitutionSpec("urzad-gminy", "urzad", None, "Urząd Gminy Rybno"),
    InstitutionSpec("gops", "gops", "/134/Gminny_Osrodek_Pomocy_Spolecznej/",
                    "Gminny Ośrodek Pomocy Społecznej w Rybnie"),
    InstitutionSpec("biblioteka", "biblioteka", "/102/Gminna_Biblioteka_Publiczna/",
                    "Gminna Biblioteka Publiczna w Rybnie"),
    InstitutionSpec("osir", "osir", "/133/Osrodek_Sportu_i_Rekreacji/",
                    "Ośrodek Sportu i Rekreacji w Rybnie"),
    InstitutionSpec("sp-rybno", "szkola", "/141/Szkola_Podstawowa_w_Rybnie/",
                    "Szkoła Podstawowa w Rybnie"),
    InstitutionSpec("sp-hartowiec", "szkola", "/137/Szkola_Podstawowa_w_Hartowcu/",
                    "Szkoła Podstawowa w Hartowcu"),
    InstitutionSpec("sp-koszelewy", "szkola", "/139/Szkola_Podstawowa_w_Koszelewach/",
                    "Szkoła Podstawowa w Koszelewach"),
    InstitutionSpec("sp-rumian", "szkola", "/140/Szkola_Podstawowa_w_Rumianie/",
                    "Szkoła Podstawowa w Rumianie"),
    InstitutionSpec("sp-zabiny", "szkola", "/142/Szkola_Podstawowa_w_Zabinach/",
                    "Szkoła Podstawowa w Żabinach"),
    InstitutionSpec("przedszkole", "przedszkole", "/143/Przedszkole_w_Rybnie/",
                    "Przedszkole w Rybnie"),
    InstitutionSpec("zlobek", "zlobek", "/10050/Zlobek_w_Rybnie/",
                    "Żłobek w Rybnie"),
    InstitutionSpec("zoz", "zoz", None,
                    "Samodzielny Publiczny Gminny Zakład Opieki Zdrowotnej w Rybnie"),
)

# Dane, których na BIP nie ma (urząd nie ma tam własnej wizytówki, ZOZ prowadzi
# osobny serwis). Wpisane raz, ze wskazaniem źródła — i tak samo jak wszystko
# inne wolno je potem poprawić w bazie.
MANUAL: dict[str, dict] = {
    "urzad-gminy": {
        "address": "ul. Lubawska 15, 13-220 Rybno",
        "phone": "23 696 60 55",
        "email": "rybno@gminarybno.pl",
        "website": GMINA_WWW,
        # ⚠️ 8:00–16:00, nie 7:15–15:15 jak głosiła stała w kodzie.
        "hours": "poniedziałek–piątek 8:00–16:00",
        "scope": (
            "Sprawy gminne. Sprawy powiatowe (prawo jazdy, rejestracja pojazdów, "
            "pozwolenia na budowę) załatwia Starostwo Powiatowe w Działdowie. "
            "ePUAP: /2803062/SkrytkaESP, fax 23 696 68 11."
        ),
        "bip_url": f"{BIP_BASE}/",
    },
    "zoz": {
        "website": "https://spgzozrybno.pl",
        "scope": (
            "Podstawowa opieka zdrowotna, poradnie specjalistyczne. Godziny "
            "przyjęć lekarzy sprawdzaj narzędziem clinic_schedule."
        ),
    },
    "gops": {
        "scope": (
            "Pomoc społeczna, świadczenia rodzinne, dodatek mieszkaniowy, "
            "Karta Dużej Rodziny, praca socjalna."
        ),
    },
}

_TEL_RE = re.compile(r"tel[.:]?\s*:?\s*\(?0?(\d{2})\)?[\s-]*([\d\s-]{7,12})", re.I)
_WWW_RE = re.compile(r"www\s*:\s*(https?://\S+|[\w.-]+\.[a-z]{2,}\S*)", re.I)
# Imię + nazwisko, DOKŁADNIE dwa człony. Przy trzech („{1,2}") wzorzec zjadał
# nazwę miejscowości z następnego zdania: „Dyrektor: Agnieszka Kowalkowska
# Hartowiec" — bo na BIP adres idzie zaraz po nazwisku, bez kropki.
_MANAGER_RE = re.compile(
    r"(Dyrektor|Kierownik|Wójt)\s*:?\s*"
    r"([A-ZŁŚŻŹĆŃÓĄĘ][\wóąęćśżźłń'\-]+\s+[A-ZŁŚŻŹĆŃÓĄĘ][\wóąęćśżźłń'\-]+)"
)
# Adres w dwóch wariantach, bo tylko tak wychodzi bez śmieci:
#   z „ul." — do trzech słów nazwy i opcjonalny numer („ul. Sportowa,” w OSiR
#             numeru nie ma wcale);
#   bez „ul." — DOKŁADNIE jedno słowo i numer obowiązkowy („Hartowiec 40”).
# Wariant swobodny („{0,2}” słowa bez „ul.”) doklejał ostatni wyraz nazwy
# jednostki: „Szkoła Podstawowa w Hartowcu Hartowiec 40”.
_ADDR_RE = re.compile(
    r"("
    r"ul\.\s*[\wóąęćśżźłń'\-]+(?:\s+[\wóąęćśżźłń'\-]+){0,2}\s*\d*[A-Za-z]?"
    r"|[A-ZŁŚŻŹĆŃÓĄĘ][\wóąęćśżźłń'\-]*\s+\d+[A-Za-z]?"
    r")"
    r"\s*,?\s*(\d{2}\s*-\s*\d{3})\s+([A-ZŁŚŻŹĆŃÓĄĘ][\wóąęćśżźłń'\-]+)"
)


def _plain_text(raw_html: str) -> str:
    """Treść bloku `div.information` jako jeden ciąg z pojedynczymi spacjami."""
    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw_html, flags=re.S | re.I)
    match = re.search(r'class="information"(.*?)(</div>\s*</div>|<footer)', body, re.S | re.I)
    chunk = match.group(1) if match else body
    text = html.unescape(re.sub(r"<[^>]+>", " ", chunk))
    return re.sub(r"\s+", " ", text).strip()


def parse_institution(text: str) -> dict:
    """Wyciąga dane teleadresowe z tekstu strony jednostki.

    Wzorce są celowo tolerancyjne: każda z dwunastu stron jest formatowana
    trochę inaczej („Dyrektor :" ze spacją, „(023)" z zerem, kod pocztowy
    rozstrzelony jako „13 - 220"). Pole, którego nie da się rozpoznać, zostaje
    `None` — to uczciwszy wynik niż zgadywanie.
    """
    out: dict = {}

    tel = _TEL_RE.search(text)
    if tel:
        digits = re.sub(r"\D", "", tel.group(2))[:7]
        if len(digits) >= 7:
            # Zapis polski: kierunkowy + 696 63 39, nie „696 633 9".
            out["phone"] = f"{tel.group(1)} {digits[:3]} {digits[3:5]} {digits[5:7]}"
        elif len(digits) >= 6:
            out["phone"] = f"{tel.group(1)} {digits[:3]} {digits[3:]}"

    who = _MANAGER_RE.search(text)
    if who:
        out["manager"] = f"{who.group(1)}: {who.group(2)}"

    # Adresu szukamy w tekście BEZ nazwiska dyrektora. Na stronach szkół adres
    # stoi tuż za nazwiskiem („Dyrektor : Hanna Kirchhof Rumian 12”), więc
    # wzorzec adresu brał nazwisko za nazwę ulicy.
    haystack = text.replace(who.group(0), " ") if who else text

    addr = _ADDR_RE.search(haystack)
    if addr:
        street = re.sub(r"\s+", " ", addr.group(1)).strip()
        code = addr.group(2).replace(" ", "")
        out["address"] = f"{street}, {code} {addr.group(3)}"

    www = _WWW_RE.search(text)
    if www:
        url = www.group(1).rstrip(".,;")
        out["website"] = url if url.startswith("http") else f"http://{url}"

    return out


def content_hash(data: dict) -> str:
    """Skrót z pól pobranych z BIP — decyduje, czy wpis wymagał zapisu."""
    parts = [str(data.get(k) or "") for k in ("name", "address", "phone", "manager", "website")]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


class BipInstitutionsScraper:
    def __init__(self, timeout: int = 30, delay: float = 0.4):
        self.timeout = timeout
        self.delay = delay
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            headers=BIP_HEADERS, timeout=self.timeout, follow_redirects=True
        )
        return self

    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()

    async def fetch_all(self) -> list[dict]:
        """Komplet jednostek: dane z BIP nadpisane ręcznymi tam, gdzie są.

        ⚠️ Blokada IP serwerowni dotyczy TEGO scrapera tak samo jak reszty BIP
        (patrz CLAUDE.md, 24.08). Przebieg z produkcji dostanie 403 — wtedy
        uruchamiamy go lokalnie i wynik idzie tunelem SSH do bazy.
        """
        results = []
        for spec in INSTITUTIONS:
            data = {"slug": spec.slug, "kind": spec.kind, "name": spec.fallback_name}

            if spec.path:
                url = f"{BIP_BASE}{spec.path}"
                data["bip_url"] = url
                try:
                    response = await self.client.get(url)
                    response.raise_for_status()
                    text = _plain_text(response.text)
                    data.update(parse_institution(text))
                    # Pełna nazwa ze strony bywa bogatsza niż nasza etykieta
                    # („im. Kawalerów Orderu Uśmiechu") — bierzemy ją, jeśli jest.
                    heading = re.match(r">?\s*([^>]{10,180}?)\s+Akapit nr", text)
                    if heading:
                        data["name"] = heading.group(1).strip()
                except Exception as e:
                    logger.error(f"{spec.slug}: nie pobrano ({e})")
                    data["_error"] = str(e)
                await asyncio.sleep(self.delay)

            data["content_hash"] = content_hash(data)
            # Ręczne NA KOŃCU: to one rozstrzygają, bo opisują rzeczy, których
            # BIP nie publikuje albo publikuje gorzej.
            data.update(MANUAL.get(spec.slug, {}))
            results.append(data)

        return results
