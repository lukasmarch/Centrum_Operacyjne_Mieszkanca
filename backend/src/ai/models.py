"""
Pydantic Models dla AI Agents

Response models dla strukturyzowanych odpowiedzi z Pydantic AI
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

# Dozwolone kategorie - Literal wymusza walidację przez Pydantic AI
ArticleCategoryName = Literal[
    'Awaria', 'Urząd', 'Zdrowie', 'Edukacja', 'Biznes',
    'Transport', 'Kultura', 'Sport', 'Rekreacja', 'Nieruchomości'
]


class ArticleCategory(BaseModel):
    """Response z kategoryzacji artykułu"""

    primary_category: ArticleCategoryName = Field(
        description="JEDNA z dozwolonych kategorii: Awaria, Urząd, Zdrowie, Edukacja, Biznes, Transport, Kultura, Sport, Rekreacja, Nieruchomości. NIE używaj innych nazw."
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Pewność klasyfikacji (0-1)"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tagi tematyczne (3-5 słów kluczowych)"
    )
    locations_mentioned: List[str] = Field(
        default_factory=list,
        description="Wymienione miejscowości z Powiatu Działdowskiego"
    )
    key_entities: List[str] = Field(
        default_factory=list,
        description="Kluczowe podmioty (osoby, instytucje, firmy)"
    )
    summary: str = Field(
        max_length=500,
        description="Podsumowanie 2-3 zdania po polsku"
    )
    display_title: str = Field(
        max_length=120,
        description=(
            "WŁASNY nagłówek informacyjny (max 100 znaków) napisany od zera na podstawie treści. "
            "Styl depeszy: konkret na początku, bez emoji, bez wykrzykników, bez CAPS LOCKA, "
            "bez kopiowania sformułowań ze źródła."
        )
    )
    is_filler: bool = Field(
        default=False,
        description=(
            "True, gdy wpis NIE jest wiadomością: powitania typu 'Dzień dobry, dziś...', "
            "życzenia, kalendarium, horoskopy, grafiki dnia, posty czysto towarzyskie. "
            "False dla każdej realnej informacji lokalnej."
        )
    )
    is_promotional: bool = Field(
        default=False,
        description=(
            "True, gdy wpis jest reklamą komercyjną prywatnej firmy: oferta usługi lub "
            "produktu, promocja, cennik, zaproszenie na stoisko, 'polecamy', dane kontaktowe "
            "sprzedawcy. False dla komunikatów instytucji, ofert pracy, otwarcia nowej firmy "
            "i wszystkiego, co jest informacją, a nie ofertą sprzedaży."
        )
    )
    locality: int = Field(
        default=0, ge=0, le=3,
        description=(
            "Na ile wpis dotyczy gminy Rybno i jej mieszkańców. "
            "3 = dzieje się w gminie Rybno lub bezpośrednio jej dotyczy; "
            "2 = sąsiednia gmina powiatu działdowskiego, mieszkaniec Rybna to odczuje "
            "(Działdowo, Lidzbark, Płośnica, Iłowo); "
            "1 = powiat lub region bez związku z gminą; "
            "0 = poza powiatem (Żuromin, Mława, Olsztyn) albo temat ogólnopolski."
        )
    )
    usefulness: int = Field(
        default=0, ge=0, le=3,
        description=(
            "Czy mieszkaniec może z tym wpisem coś zrobić. "
            "3 = wymaga działania lub decyzji (termin, awaria, nabór, zmiana godzin); "
            "2 = konkret przydatny (co, gdzie, kiedy — wydarzenie, inwestycja, oferta pracy); "
            "1 = warto wiedzieć, ale nic z tego nie wynika (relacja, wynik, ciekawostka); "
            "0 = nic nie wnosi."
        )
    )
    event_start: Optional[str] = Field(
        default=None,
        description=(
            "Termin ZAPOWIADANEGO zdarzenia w formacie ISO 'YYYY-MM-DDTHH:MM' (czas lokalny). "
            "Wypełnij TYLKO, gdy wpis zapowiada coś, co dopiero nastąpi, i podaje datę: "
            "festyn, zebranie wiejskie, dyżur, zbiórka, zapisy z terminem, zamknięcie drogi. "
            "Gdy godziny nie podano, wpisz 'YYYY-MM-DDT00:00'. "
            "null dla relacji z tego, co już było, i dla wiadomości bez terminu."
        )
    )
    event_end: Optional[str] = Field(
        default=None,
        description=(
            "Koniec zapowiadanego zdarzenia w tym samym formacie — TYLKO gdy godzina "
            "zakończenia jest wprost w tekście. Inaczej null."
        )
    )


class ExtractedEvent(BaseModel):
    """Wydarzenie wyekstrahowane z artykułu"""

    is_event: bool = Field(
        description="Czy artykuł opisuje konkretne wydarzenie"
    )
    title: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = Field(
        max_length=300,
        default=None
    )
    event_date: Optional[datetime] = None
    event_time: Optional[str] = Field(
        max_length=10,
        default=None,
        description="Format HH:MM"
    )
    end_date: Optional[datetime] = None
    location: Optional[str] = None
    address: Optional[str] = None
    organizer: Optional[str] = None
    price_info: Optional[str] = None
    contact_info: Optional[str] = None


class DailySummary(BaseModel):
    """Dzienne podsumowanie wiadomości"""

    date: str = Field(description="Data w formacie YYYY-MM-DD")
    headline: str = Field(
        max_length=200,
        description="Główny nagłówek dnia - chwytliwy, przyciągający uwagę"
    )
    highlights: str = Field(
        max_length=1000,
        description="Akapit opisowy (4-6 zdań) z najważniejszymi wiadomościami, pogodą i wydarzeniami. Najważniejsze info w **bold** (markdown)"
    )
    summary_by_category: dict[str, str] = Field(
        default_factory=dict,
        description="Podsumowanie per moduł (klucz: kategoria, wartość: opis)"
    )
    upcoming_events: List[str] = Field(
        default_factory=list,
        description="Nadchodzące wydarzenia"
    )
    air_quality_summary: str = Field(
        description="Podsumowanie jakości powietrza i warunków pogodowych (dane z czujnika w Rybnie)"
    )
    headline_importance_score: int = Field(
        ge=1, le=10,
        description=(
            "Ocena ważności nagłówka 1-10: "
            "10=awaria/kryzys LOKALNY (Rybno/Działdowo/powiat); "
            "9=awaria/kryzys REGIONALNY bezpośrednio wpływający na mieszkańców powiatu (lotnisko Szymany, DK7/DK15, alert RCB dla woj., szpital w Działdowie); "
            "7-8=pilne LOKALNE (zdrowie, transport, urząd); "
            "5-6=ważne LOKALNE (biznes, edukacja, inwestycje); "
            "3-4=kultura/sport LOKALNY, festyny; "
            "2=tylko regionalne bez wpływu na lokalnych; "
            "1=brak istotnych wiadomości"
        )
    )
    cited_article_ids: List[int] = Field(
        default_factory=list,
        description="IDs artykułów (z pola [ID:xxx]) które są cytowane lub stanowią podstawę headline i highlights. Max 5. PIERWSZY ID = artykuł będący podstawą headline."
    )
