"""
Pochodzenie faktu — skąd agent wie to, co mówi (31.08.2026)

**Skąd to się wzięło.** 30.08 Przewodnik odpowiedział na pytanie „nad jakim
jeziorem leży Rybno": „Rybno leży nad jeziorem Rumian. To malownicze jezioro
jest popularnym miejscem wypoczynku". Rumian to osobna wieś w gminie, kilka
kilometrów dalej. Nazwy jezior LEŻĄ w `bip_documents` (Zarybinek, Hartowieckie,
Neliwa, Grądy) — agent ich nie przeczytał, bo `search_documents` należy do
Urzędnika, i napisał zdanie z pamięci modelu, dokładając ozdobniki. W tym samym
przebiegu „ile km do Warszawy" dostało „około 180 kilometrów" tą samą drogą.

**Na czym polega problem.** Dla mieszkańca „6682 osoby (GUS 2024)" i „około
180 kilometrów (z niczego)" wyglądają identycznie — to dwa zdania oznajmujące
w jednej odpowiedzi. Model też ich nie odróżnia, bo wynik narzędzia przychodzi
do niego jako goły JSON, bez informacji, czyje to zdanie. Ta sama pułapka co
przy widgecie ruchu: Gemini puszczony po Google podał zmyśloną datę remontu
DW538, a brzmiało to jak komunikat drogowy (`services/road_context.py`).

**Co robi ta warstwa.** Nazywa, KTO ODPOWIADA ZA TREŚĆ — nie, jak bardzo jej
ufamy. Zaufanie jest wnioskiem, nie danymi: uchwała Rady bywa nieaktualna,
a post na Facebooku prawdziwy. Etykieta mówi tylko, u kogo mieszkaniec może
to sprawdzić, i to wystarcza, żeby model przestał zestawiać rejestr publiczny
z własną pamięcią jako równorzędne.

⚠️ **Warstwa `MODEL` nie jest źródłem i celowo nie ma narzędzia.** Istnieje po
to, żeby dało się o niej napisać w regule precedencji — fakt bez pokrycia
w wyniku narzędzia albo w karcie gminy nie jest wiedzą, tylko zgadywaniem.

⚠️ Nowe narzędzie MUSI dostać warstwę. Domyślną jest `MEDIA`, bo to najostrożniejsze
z tego, co realnie mamy — ale `scripts/test_provenance.py` wymaga jawnej deklaracji
i nie przepuści narzędzia, które o niej zapomniało.
"""
from typing import Final, Optional

# Kto odpowiada za treść. Kolejność stałych = malejąca możliwość sprawdzenia
# faktu u kogoś, kto za niego odpowiada urzędowo.
URZEDOWE: Final = "urzedowe"
POMIAR: Final = "pomiar"
MEDIA: Final = "media"
MIESZKANCY: Final = "mieszkancy"
# Serwis komercyjny spoza naszych danych. Dziś jedyny taki jest cache Google Maps
# w `local_places`; to również właściwe miejsce dla wyszukiwania w sieci, gdy
# dojdzie — warstwa istnieje, więc narzędzie nie będzie musiało jej wymyślać.
ZEWNETRZNE: Final = "zewnetrzne"
MODEL: Final = "model"
# Narzędzie sterujące (`przekaz_dalej`, `zapytaj_*`) nie zwraca faktów o gminie,
# tylko przenosi pytanie. Etykieta źródła byłaby przy nim myląca, więc się jej
# nie dokleja — patrz warunek w `base_agent._tool_message`.
STEROWANIE: Final = "sterowanie"

LAYERS: Final[tuple[str, ...]] = (
    URZEDOWE, POMIAR, MEDIA, MIESZKANCY, ZEWNETRZNE, MODEL, STEROWANIE,
)

# Opis idzie PROSTO DO MODELU przy każdym wyniku narzędzia, więc jest krótki
# i mówi rzecz sprawdzalną (u kogo to zweryfikować), a nie ocenę wiarygodności.
_LABELS: Final[dict[str, str]] = {
    URZEDOWE: "urzędowe — organ gminy (BIP, uchwały, protokoły, dane jednostek)",
    POMIAR: "pomiar lub rejestr publiczny (GUS, stacja pogodowa, harmonogram operatora)",
    MEDIA: "media lokalne — portal lub Facebook, treść nieurzędowa",
    MIESZKANCY: "zgłoszenie mieszkańca — niezweryfikowane przez urząd",
    ZEWNETRZNE: "serwis zewnętrzny — dane komercyjne, nie urzędowe i nie nasz pomiar",
    MODEL: "BRAK ŹRÓDŁA — wiedza własna modelu, nie wolno podawać jako fakt o gminie",
}


def label(layer: str) -> Optional[str]:
    """Etykieta warstwy dla modelu.

    `None` dla narzędzi sterujących — nie mają czego oznaczać. Nieznana warstwa
    dostaje etykietę `MEDIA`, bo pomyłka w tę stronę czyni odpowiedź ostrożniejszą,
    a w drugą — pewniejszą, niż na to zasługuje.
    """
    if layer == STEROWANIE:
        return None
    return _LABELS.get(layer, _LABELS[MEDIA])


# Reguła precedencji — jedna, dla wszystkich agentów, wstrzykiwana raz przez
# `base_agent.base_context_messages()`. Nie idzie do promptów agentów: siedmiu
# kopii nikt nie utrzyma zgodnych, a rozjazd między nimi byłby niewidoczny.
#
# Zdanie o rozbieżności jest tu celowo, mimo że dziś żadne narzędzie nie sięga
# poza nasze dane: gdy dojdzie wyszukiwanie w sieci, reguła ma już obowiązywać,
# zamiast powstawać razem z narzędziem, które ją najbardziej obciąża.
PRECEDENCE: Final = """POCHODZENIE INFORMACJI (obowiązuje w każdej odpowiedzi):
- Każdy wynik narzędzia ma pole `zrodlo`. Ono mówi, kto odpowiada za tę treść.
- Fakt o gminie Rybno podawaj WYŁĄCZNIE wtedy, gdy pochodzi z wyniku narzędzia
  albo z faktów podstawowych o gminie. Nazwa jeziora, odległość, powierzchnia,
  rok założenia czy liczba mieszkańców wsi wzięte z własnej pamięci są
  zgadywaniem, nawet gdy brzmią sensownie — wtedy napisz wprost, że tego nie wiesz,
  i wskaż, gdzie mieszkaniec to sprawdzi.
- Gdy dwa źródła mówią co innego: pierwszeństwo ma urzędowe, potem pomiar/rejestr,
  potem media. Jeśli rozbieżność dotyczy rzeczy istotnej (termin, kwota, adres),
  powiedz o niej mieszkańcowi wprost i podaj obie wersje z ich źródłami —
  zamilczenie sprzeczności jest gorsze niż jej pokazanie.
- Nie dopisuj do faktu źródła, którego nie było w wyniku narzędzia."""


def precedence_message() -> dict:
    """Reguła precedencji jako wiadomość `system`."""
    return {"role": "system", "content": PRECEDENCE}
