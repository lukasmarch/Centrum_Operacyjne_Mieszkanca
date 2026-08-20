from datetime import datetime, date
from typing import Optional, List
from sqlmodel import SQLModel, Field, Column, JSON, ARRAY, String, Index
from sqlalchemy.dialects.postgresql import JSONB
from enum import Enum


# ======================
# Enums for User System
# ======================

class UserTier(str, Enum):
    FREE = "free"
    PREMIUM = "premium"
    BUSINESS = "business"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PENDING = "pending"


class NewsletterFrequency(str, Enum):
    WEEKLY = "weekly"
    DAILY = "daily"


class NewsletterStatus(str, Enum):
    ACTIVE = "active"
    UNSUBSCRIBED = "unsubscribed"
    BOUNCED = "bounced"


class CouncilSessionStatus(str, Enum):
    """
    Droga skrótu sesji Rady od wykrycia nagrania do strony.

    `PENDING` jest stanem docelowym joba, nie stanem przejściowym: skrót obrad
    czeka na człowieka i sam z siebie nigdzie nie pojedzie. Powód siedzi
    w `ai/council_summary.py` — cytat da się sprawdzić twardo (jest w transkrypcie
    albo go nie ma), ale `description` już nie: sędzia-LLM na tym samym materiale
    raz łapie dopisany cel działki, raz go przepuszcza. Zdania podejrzane są więc
    tylko oznaczane, a decyzję podejmuje człowiek.
    """
    NEW = "new"                # wykryte nagranie, jeszcze nieprzepisane
    PROCESSING = "processing"  # trwa transkrypcja albo skrót
    PENDING = "pending"        # skrót gotowy, czeka na akceptację człowieka
    PUBLISHED = "published"    # zaakceptowany, widoczny publicznie
    REJECTED = "rejected"      # odrzucony przez człowieka, nie wraca
    ERROR = "error"            # przebieg padł; wraca do kolejki do `MAX_ATTEMPTS`


# ======================
# User System Tables (Sprint 1)
# ======================

class User(SQLModel, table=True):
    """Użytkownicy systemu"""
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(max_length=255, unique=True, index=True)
    password_hash: str = Field(max_length=255)
    full_name: str = Field(max_length=100)
    location: str = Field(max_length=100, default="Rybno")  # Domyślna miejscowość
    tier: str = Field(default=UserTier.FREE.value, max_length=20)  # free, premium, business

    # Preferences (JSONB) - kategorie, powiadomienia, etc.
    preferences: Optional[dict] = Field(default_factory=dict, sa_column=Column(JSONB))

    # Trial Premium (30 dni po rejestracji, bez karty)
    trial_ends_at: Optional[datetime] = None
    # Który mail o kończącym się trialu już poszedł: week → last_day → ended.
    # Job chodzi codziennie, więc bez tego znacznika wysłałby to samo siedem razy.
    trial_reminder_stage: Optional[str] = Field(default=None, max_length=20)
    trial_reminder_sent_at: Optional[datetime] = None

    # Referral program
    referral_code: Optional[str] = Field(default=None, max_length=20, unique=True)
    referred_by: Optional[int] = Field(default=None, foreign_key="users.id")

    # Status flags
    email_verified: bool = Field(default=False)
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)  # rola administratora (moderacja, operacje serwisowe) — niezależna od tieru płatności

    # Zgody RODO (art. 7 — rozliczalność)
    consent_terms_at: Optional[datetime] = None          # kiedy zaakceptowano regulamin + politykę prywatności
    consent_marketing: bool = Field(default=False)       # zgoda marketingowa (newsletter, oferty)
    consent_privacy_version: Optional[str] = Field(default=None, max_length=20)  # wersja zaakceptowanych dokumentów

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None


class Subscription(SQLModel, table=True):
    """Subskrypcje Premium/Business"""
    __tablename__ = "subscriptions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    tier: str = Field(max_length=20)  # premium, business
    status: str = Field(default=SubscriptionStatus.ACTIVE.value, max_length=20)  # active, cancelled, expired

    # Przelewy24 integration
    p24_order_id: Optional[str] = Field(default=None, max_length=100)
    p24_session_id: Optional[str] = Field(default=None, max_length=100)

    # Dates
    started_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    # Który mail o kończącym się okresie opłaconym już poszedł: week → last_day → ended.
    # Ten sam mechanizm co `users.trial_reminder_stage`, tylko dla płatnych: job chodzi
    # codziennie, więc bez znacznika wysłałby to samo przypomnienie siedem razy.
    # Plan nie odnawia się automatycznie (regulamin §6.5), więc cisza przed wygaśnięciem
    # oznaczała, że płacący klient tracił dostęp bez ostrzeżenia.
    reminder_stage: Optional[str] = Field(default=None, max_length=20)
    reminder_sent_at: Optional[datetime] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ======================
# Newsletter Tables (Sprint 2)
# ======================

class NewsletterSubscriber(SQLModel, table=True):
    """Subskrybenci newslettera"""
    __tablename__ = "newsletter_subscribers"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(max_length=255, unique=True, index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")  # Może być NULL dla anonimowych
    frequency: str = Field(default=NewsletterFrequency.WEEKLY.value, max_length=20)  # weekly, daily
    status: str = Field(default=NewsletterStatus.ACTIVE.value, max_length=20)  # active, unsubscribed, bounced
    location: str = Field(default="Rybno", max_length=100)  # Lokalizacja dla spersonalizowanej treści

    # Confirmation
    confirmation_token: Optional[str] = Field(default=None, max_length=100)
    confirmed_at: Optional[datetime] = None

    # Unsubscribe
    unsubscribe_token: str = Field(max_length=100)  # Unique token for unsubscribe link
    unsubscribed_at: Optional[datetime] = None

    # Stats
    emails_sent: int = Field(default=0)
    emails_opened: int = Field(default=0)
    last_sent_at: Optional[datetime] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class NewsletterLog(SQLModel, table=True):
    """Log wysłanych newsletterów"""
    __tablename__ = "newsletter_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    subscriber_id: int = Field(foreign_key="newsletter_subscribers.id", index=True)
    newsletter_type: str = Field(max_length=20)  # weekly, daily
    subject: str = Field(max_length=255)
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    status: str = Field(default="sent", max_length=20)  # sent, opened, bounced, failed


class Source(SQLModel, table=True):
    __tablename__ = "sources"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, index=True)
    type: str = Field(max_length=50)
    url: Optional[str] = None
    scraping_config: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    last_scraped: Optional[datetime] = None
    status: str = Field(default="active", max_length=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Article(SQLModel, table=True):
    __tablename__ = "articles"

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.id", index=True)
    external_id: Optional[str] = Field(default=None, max_length=255, unique=True)
    title: str
    content: Optional[str] = None
    summary: Optional[str] = None
    url: str = Field(unique=True, index=True)
    image_url: Optional[str] = None
    author: Optional[str] = Field(default=None, max_length=255)
    published_at: Optional[datetime] = None
    # Termin zdarzenia, którego wpis dotyczy (wyłączenie prądu) — inny niż data
    # publikacji. Bez niego ranking liczył wiek OGŁOSZENIA, więc zapowiedź na
    # przyszły tydzień wypadała z feedu, zanim zdarzenie nastąpiło.
    event_at: Optional[datetime] = None
    event_until: Optional[datetime] = None
    # Ocena treści z kategoryzacji (lokalność + użyteczność, 0–6). NULL = nieocenione
    # i daje mnożnik neutralny w `feed_policy.article_score`. Bez tego czynnika
    # ranking widział wyłącznie wagę źródła i świeżość, więc wygrywał kanał
    # publikujący najczęściej — pomiar 11.08.2026: pierwsza piątka Dashboardu
    # gorsza od średniej materiału w trzech wymiarach na cztery.
    content_score: Optional[int] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    category: Optional[str] = Field(default=None, max_length=100)
    tags: Optional[List[str]] = Field(default=None, sa_column=Column(ARRAY(String)))
    location_mentioned: Optional[List[str]] = Field(default=None, sa_column=Column(ARRAY(String)))
    processed: bool = Field(default=False)
    embedded: bool = Field(default=False)  # True when RAG embeddings generated (Sprint 6)
    display_title: Optional[str] = Field(default=None, max_length=200)  # nagłówek AI (bez kopii źródła)
    is_filler: bool = Field(default=False)  # posty powitalne/zapychacze — ukryte w feedzie
    is_promotional: bool = Field(default=False)  # cudza reklama komercyjna — ukryta w feedzie
    # Moment wysłania alertu push. Znacznik, nie log: Energa aktualizuje ten sam
    # wpis co 3h (wspólny external_id), więc bez niego każde odświeżenie źródła
    # wysyłałoby powiadomienie o tym samym wyłączeniu od nowa.
    alert_pushed_at: Optional[datetime] = Field(default=None)

class Event(SQLModel, table=True):
    __tablename__ = "events"
    __table_args__ = (
        Index('idx_event_unique', 'title', 'event_date', 'location', unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(max_length=500)
    description: Optional[str] = None
    short_description: Optional[str] = Field(default=None, max_length=300)
    event_date: datetime
    event_time: Optional[str] = Field(default=None, max_length=10)
    end_date: Optional[datetime] = None
    location: Optional[str] = Field(default=None, max_length=255)
    address: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=100)
    source_article_id: Optional[int] = Field(default=None, foreign_key="articles.id")
    external_url: Optional[str] = None
    image_url: Optional[str] = None
    organizer: Optional[str] = Field(default=None, max_length=255)
    price_info: Optional[str] = Field(default=None, max_length=255)
    contact_info: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_featured: bool = Field(default=False)
    views_count: int = Field(default=0)
    embedded: bool = Field(default=False)  # True when RAG embeddings generated

class Weather(SQLModel, table=True):
    __tablename__ = "weather"

    id: Optional[int] = Field(default=None, primary_key=True)
    location: str = Field(max_length=100, index=True)  # "Rybno", "Działdowo"
    latitude: float
    longitude: float

    # Current weather
    temperature: float  # °C
    feels_like: float  # °C
    temp_min: float  # °C
    temp_max: float  # °C

    # Conditions
    description: str = Field(max_length=200)  # "pochmurno", "słonecznie"
    icon: str = Field(max_length=10)  # OpenWeather icon code
    main: str = Field(max_length=50)  # "Clouds", "Clear", "Rain"

    # Additional data
    humidity: int  # %
    pressure: int  # hPa
    wind_speed: float  # m/s
    wind_deg: Optional[int] = None  # degrees
    clouds: int  # %

    # Visibility & rain
    visibility: Optional[int] = None  # meters
    rain_1h: Optional[float] = None  # mm
    rain_3h: Optional[float] = None  # mm

    # Sun times
    sunrise: Optional[datetime] = None
    sunset: Optional[datetime] = None

    # Forecast (optional JSONB for 5-day forecast)
    forecast: Optional[dict] = Field(default=None, sa_column=Column(JSONB))

    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    is_current: bool = Field(default=True)  # flag for latest record

class AirQuality(SQLModel, table=True):
    """Jakość powietrza z Airly"""
    __tablename__ = "air_quality"

    id: Optional[int] = Field(default=None, primary_key=True)
    location: str = Field(max_length=100, index=True)  # "Rybno"
    
    # Indexes
    pm25: float  # µg/m³
    pm10: float  # µg/m³
    caqi: float  # Airly CAQI index
    caqi_level: str = Field(max_length=50) # VERY_LOW, LOW, etc.
    
    # Weather conditions from sensor
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    
    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    is_current: bool = Field(default=True)

class DailySummary(SQLModel, table=True):
    """Dzienne podsumowania generowane przez AI"""
    __tablename__ = "daily_summaries"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: datetime = Field(unique=True, index=True)  # Data podsumowania
    headline: str  # Główny nagłówek dnia
    content: dict = Field(sa_column=Column(JSONB))  # Pełne podsumowanie (DailySummary model)
    generated_at: datetime = Field(default_factory=datetime.utcnow)  # Kiedy wygenerowano


class CinemaShowtime(SQLModel, table=True):
    """Repertuar kin - Dzialdowo i Lubawa (scraped daily)"""
    __tablename__ = "cinema_showtimes"
    __table_args__ = (
        Index('idx_cinema_date_title', 'cinema_name', 'date', 'title'),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Cinema & Schedule
    cinema_name: str = Field(max_length=100, index=True)  # "Kino Dzialdowo", "Kino Lubawa"
    date: str = Field(max_length=10, index=True)  # "DD.MM.YYYY" format (matches scraper)

    # Movie Details
    title: str = Field(max_length=200)  # Film title
    genre: str = Field(max_length=50, default="Film")  # Genre
    showtimes: List[str] = Field(sa_column=Column(ARRAY(String)))  # ["16:50", "20:30"]
    poster_url: str = Field(max_length=500)  # Poster image URL
    rating: str = Field(max_length=10, default="N/A")  # Rating (usually "N/A")
    link: Optional[str] = Field(default=None, max_length=500)  # Link to movie page

    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class TrafficCache(SQLModel, table=True):
    """Cache danych o ruchu drogowym - Gemini Grounding API (refreshed every 4h)"""
    __tablename__ = "traffic_cache"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Traffic data (JSONB for flexibility)
    # Structure: {"roads": [...], "sources": [...]}
    data: dict = Field(sa_column=Column(JSONB))

    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    is_current: bool = Field(default=True)  # Flag for latest record
    ttl_seconds: int = Field(default=14400)  # TTL: 4 hours


# Legacy GUSStatistic model removed (2026-02-17)
# Replaced by: GUSGminaStats, GUSNationalAverages, GUSDataRefreshLog
# See: backend/src/api/endpoints/gus.py for new database-first architecture

class GUSGminaStats(SQLModel, table=True):
    """Cache danych GUS dla gmin - pobierane raz miesięcznie"""
    __tablename__ = "gus_gmina_stats"
    __table_args__ = (
        Index('idx_gus_gmina_unit_var_year', 'unit_id', 'var_id', 'year', unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Identyfikacja
    unit_id: str = Field(max_length=20, index=True)  # ID jednostki GUS (np. "042815403062")
    unit_name: str = Field(max_length=100)  # Nazwa gminy (np. "Rybno")
    var_id: str = Field(max_length=20, index=True)  # ID zmiennej GUS (np. "60530")
    var_name: str = Field(max_length=200)  # Nazwa zmiennej (np. "Podmioty REGON na 10k")
    category: Optional[str] = Field(default=None, max_length=50, index=True)  # Kategoria (demografia, finanse_gminy, etc.)

    # Dane
    year: int = Field(index=True)  # Rok danych
    value: Optional[float] = None  # Wartość

    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow)  # Kiedy pobrano z API GUS


# ======================
# CEIDG Business Tables
# ======================

class CEIDGBusiness(SQLModel, table=True):
    """Firmy z rejestru CEIDG dla Gminy Rybno"""
    __tablename__ = "ceidg_businesses"
    __table_args__ = (
        Index('idx_ceidg_nip', 'nip'),
        Index('idx_ceidg_miasto', 'miasto'),
        Index('idx_ceidg_gmina_powiat', 'gmina', 'powiat'),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    ceidg_id: str = Field(max_length=50, unique=True, index=True)  # UUID from CEIDG API
    
    # Business data
    nazwa: str = Field(max_length=500)
    nip: str = Field(max_length=20, index=True)
    regon: Optional[str] = Field(default=None, max_length=20)
    
    # PKD codes
    pkd_main: Optional[str] = Field(default=None, max_length=20, index=True)
    pkd_list: Optional[List[dict]] = Field(default=None, sa_column=Column(JSONB))

    status: str = Field(max_length=30, default="AKTYWNY")  # AKTYWNY, ZAWIESZONY, WYKRESLONY
    data_rozpoczecia: Optional[datetime] = None

    # Śledzenie zmian statusu — źródło danych dla „Radaru rynku lokalnego"
    # (nowe / zawieszone / wykreślone firmy w danym miesiącu)
    previous_status: Optional[str] = Field(default=None, max_length=30)
    status_changed_at: Optional[datetime] = Field(default=None, index=True)
    
    # Owner
    wlasciciel_imie: Optional[str] = Field(default=None, max_length=100)
    wlasciciel_nazwisko: Optional[str] = Field(default=None, max_length=100)
    
    # Address (denormalized for quick queries)
    ulica: Optional[str] = Field(default=None, max_length=200)
    budynek: Optional[str] = Field(default=None, max_length=20)
    lokal: Optional[str] = Field(default=None, max_length=20)
    miasto: str = Field(max_length=100, index=True)
    kod_pocztowy: str = Field(max_length=10)
    gmina: str = Field(max_length=100)
    powiat: str = Field(max_length=100)
    wojewodztwo: Optional[str] = Field(default=None, max_length=100)
    
    # Minimalizacja danych (RODO art. 5): kolumna wyczyszczona i nieuzupełniana
    # od 07.2026 — pełny JSON rejestru wykraczał poza cel katalogu firm.
    raw_data: Optional[dict] = Field(default=None, sa_column=Column(JSONB))

    # Sprzeciw wobec przetwarzania (RODO art. 21): karta ukryta publicznie.
    # Flaga musi przetrwać każdą synchronizację CEIDG.
    opted_out: bool = Field(default=False, index=True)

    # Skąd wziął się wiersz: 'ceidg' (rejestr) albo 'manual' (firma dopisana
    # przez właściciela — spółka, oddział, działalność zarejestrowana pod innym
    # adresem, koło gospodyń).
    #
    # ⚠️ To NIE jest kolumna informacyjna. `ceidg_job` oznacza statusem
    # WYKRESLONY każdy wiersz, którego nie ma w odpowiedzi API, a wpis ręczny
    # z definicji nie ma tam odpowiednika — bez tego znacznika zniknąłby
    # z katalogu w pierwszą niedzielę po dodaniu. Sync musi też wykluczyć te
    # wiersze z mianownika pokrycia, inaczej rosnąca liczba wpisów ręcznych
    # zbija `coverage` poniżej progu i prawdziwe wykreślenia przestają działać.
    source: str = Field(default="ceidg", max_length=20, index=True)
    
    # External link
    ceidg_link: Optional[str] = Field(default=None, max_length=500)
    
    # Detailed Data (fetched from /firma/{id})
    # Minimalizacja danych (RODO art. 5 ust. 1 lit. c): kolumny wyczyszczone
    # i nieuzupełniane — pozostawione, żeby nie przepisywać schematu. Kontakt
    # rejestrowy dołączył do nich w 07.2026: nic go nie odczytywało, a katalog
    # publikuje wyłącznie kontakt podany przez firmę (business_profiles).
    adres_korespondencyjny: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    spolki: Optional[List[dict]] = Field(default=None, sa_column=Column(JSONB))
    obywatelstwa: Optional[List[dict]] = Field(default=None, sa_column=Column(JSONB))
    email: Optional[str] = Field(default=None, max_length=255)
    www: Optional[str] = Field(default=None, max_length=500)
    telefon: Optional[str] = Field(default=None, max_length=50)
    
    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BusinessProfile(SQLModel, table=True):
    """Wizytówka firmy — dane podane przez właściciela po przejęciu karty
    (zgoda = podstawa prawna publikacji kontaktu). Model 3 poziomów:
    rejestrowa (brak profilu) → przejęta (claim_status=verified) →
    Firma lokalna (is_premium=True, 49 zł/mc)."""
    __tablename__ = "business_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(foreign_key="ceidg_businesses.id", unique=True, index=True)
    user_id: int = Field(foreign_key="users.id", index=True)

    # Przejęcie wizytówki (weryfikacja ręczna przez admina w MVP)
    claim_status: str = Field(default="pending", max_length=20)  # pending / verified / rejected
    claim_note: Optional[str] = Field(default=None, max_length=500)  # uzasadnienie od firmy

    # Dane wizytówki — podane przez firmę
    description: Optional[str] = Field(default=None, max_length=600)
    telefon: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    www: Optional[str] = Field(default=None, max_length=500)
    godziny: Optional[str] = Field(default=None, max_length=200)  # np. "pn-pt 8-17, sb 8-13"
    logo_url: Optional[str] = Field(default=None, max_length=500)

    # Plan "Firma lokalna" (premium; w MVP włączane przez admina po opłacie)
    is_premium: bool = Field(default=False, index=True)
    premium_until: Optional[datetime] = None

    # Statystyki (argument sprzedażowy) — DWIE różne miary, patrz migracja
    # `add_business_impressions` (12.08.2026). Do tej daty `views_count` liczył
    # w istocie pokazy karty: katalog wywoływał licznik przy renderowaniu, więc
    # jedno wejście na zakładkę Firmy podbijało wynik wszystkim wizytówkom naraz.
    #
    # `impressions_count` — karta pojawiła się na ekranie (zasięg)
    # `views_count`       — ktoś kliknął telefon, www albo e-mail (zainteresowanie)
    #
    # Sprzedawać wolno tylko to drugie. Pierwsze mówi, ile razy ktoś PRZESZEDŁ
    # obok wystawy; dopiero kliknięcie znaczy, że się zatrzymał.
    impressions_count: int = Field(default=0)
    impressions_last_report: int = Field(default=0)
    views_count: int = Field(default=0)
    # Snapshot licznika z ostatniego raportu — pozwala liczyć przyrost
    # "od ostatniego maila" bez tabeli historii
    views_last_report: int = Field(default=0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    verified_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BusinessAnnouncement(SQLModel, table=True):
    """Ogłoszenia i okazje firm (plan Firma lokalna) — „Radar Lokalnego Biznesu".
    Dwa typy: 'ogloszenie' (dłuższa treść, ekspozycja w feedzie, limit 2/mc)
    i 'okazja' ("tu i teraz", wymagane valid_until ≤ 7 dni, limit 8/mc).
    Publikacja wymaga is_premium=True na business_profiles."""
    __tablename__ = "business_announcements"

    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(foreign_key="ceidg_businesses.id", index=True)

    type: str = Field(default="ogloszenie", max_length=20)  # ogloszenie / okazja
    title: str = Field(max_length=120)
    body: str = Field(max_length=500)
    valid_until: Optional[datetime] = Field(default=None, index=True)

    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class BusinessClaimLog(SQLModel, table=True):
    """Ślad po decyzjach w sprawie przejęcia wizytówki — kto, o którą firmę
    i z jakim skutkiem.

    Dlaczego osobna tabela, skoro jest `business_profiles`. Odrzucenie KASUJE
    profil (`moderate_claim`), i musi kasować: zostawiony wiersz „rejected"
    blokowałby firmę przed przejęciem przez prawdziwego właściciela. Razem
    z profilem znikał jednak jedyny ślad, że ktokolwiek próbował — nie było
    jak odróżnić pierwszej próby od piątej ani powiedzieć zgłaszającemu,
    że jego wniosek rozpatrzono odmownie.

    Trzymamy MINIMUM: kto, która firma, jaka decyzja, kiedy. Bez telefonu,
    e-maila i uzasadnienia — te znikają razem z profilem i nie mają tu wracać.
    `business_name` jest wyjątkiem koniecznym: wpis ręczny bywa kasowany razem
    z odrzuceniem, więc bez zapisanej nazwy nie da się pokazać człowiekowi,
    CZEGO dotyczyła odmowa. Przy usunięciu konta (DSAR) kasujemy te wiersze
    razem z resztą — prawo do usunięcia jest ważniejsze niż nasz audyt.

    Brak kluczy obcych jest zamierzony: firma z `source='manual'` i konto
    użytkownika bywają usuwane, a log ma je przeżyć do czasu DSAR.
    """
    __tablename__ = "business_claim_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    business_id: int = Field(index=True)
    user_id: int = Field(index=True)

    # claimed / approved / rejected
    action: str = Field(max_length=20, index=True)
    # Nazwa firmy w chwili decyzji — patrz docstring
    business_name: str = Field(max_length=300)
    # Kto podjął decyzję (puste przy 'claimed')
    admin_email: Optional[str] = Field(default=None, max_length=255)

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class CEIDGSyncStats(SQLModel, table=True):
    """Statystyki synchronizacji CEIDG"""
    __tablename__ = "ceidg_sync_stats"

    id: Optional[int] = Field(default=None, primary_key=True)
    gmina: str = Field(max_length=100, unique=True, index=True)
    powiat: str = Field(max_length=100)

    # Counts
    total_count: int = Field(default=0)
    active_count: int = Field(default=0)

    # Breakdown by locality (JSONB)
    by_miejscowosc: dict = Field(default_factory=dict, sa_column=Column(JSONB))

    # Sync metadata
    last_sync: datetime = Field(default_factory=datetime.utcnow)
    sync_status: str = Field(max_length=20, default="success")  # success, failed, in_progress


# ======================
# GUS Database-First Tables (2026-02-06)
# ======================

class GUSDataRefreshLog(SQLModel, table=True):
    """
    Tracking odświeżania danych GUS - kiedy ostatnio zaktualizowano każdą zmienną.
    Używane przez scheduler do monitorowania monthly refresh jobs.
    """
    __tablename__ = "gus_data_refresh_log"
    __table_args__ = (
        Index('idx_gus_refresh_var_key', 'var_key', unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Variable identification
    var_key: str = Field(max_length=100, unique=True, index=True)  # Key from gus_variables.py
    var_id: str = Field(max_length=20)  # GUS BDL variable ID

    # Refresh tracking
    last_refresh: datetime = Field(default_factory=datetime.utcnow)  # Ostatni successful refresh
    records_updated: int = Field(default=0)  # Liczba zaktualizowanych rekordów

    # Status
    status: str = Field(max_length=20, default="success")  # success, failed, in_progress
    error_message: Optional[str] = Field(default=None, max_length=500)  # Jeśli failed

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GUSNationalAverages(SQLModel, table=True):
    """
    Średnie krajowe i wojewódzkie dla zmiennych GUS.
    Używane do porównań: "Rybno: 6,837 PLN (79.2% średniej krajowej)".
    Populowane przez scheduler wraz z danymi gminnymi.
    """
    __tablename__ = "gus_national_averages"
    __table_args__ = (
        Index('idx_gus_avg_var_year_level', 'var_id', 'year', 'level', unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Variable identification
    var_id: str = Field(max_length=20, index=True)  # GUS BDL variable ID
    var_key: str = Field(max_length=100, index=True)  # Key from gus_variables.py

    # Data
    year: int = Field(index=True)  # Rok danych
    level: str = Field(max_length=20, index=True)  # "national" | "voivodeship"
    value: Optional[float] = None  # Wartość średniej

    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow)  # Kiedy pobrano z API


class GUSInsight(SQLModel, table=True):
    """
    AI-generowane analizy statystyk GUS dla Business tier.
    Generowane raz w miesiącu przez scheduler + GPT-4o-mini.

    UWAGA: Niższy priorytet - implementacja w późniejszym sprincie.
    """
    __tablename__ = "gus_insights"
    __table_args__ = (
        Index('idx_gus_insight_category', 'category'),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Classification
    category: str = Field(max_length=50, index=True)  # demografia, rynek_pracy, etc.
    insight_type: str = Field(max_length=50)  # trend, comparison, recommendation

    # Content
    content: str = Field(max_length=2000)  # Treść insightu po polsku (3-5 bullet points)
    data_context: dict = Field(default_factory=dict, sa_column=Column(JSONB))  # Dane źródłowe

    # Validity
    generated_at: datetime = Field(default_factory=datetime.utcnow)  # Kiedy wygenerowano
    valid_until: datetime  # Do kiedy aktualny (typically +1 month)


# ======================
# Zgłoszenie24 – Centrum Powiadamiania (Sprint Reports)
# ======================

class ReportStatus(str, Enum):
    PENDING = "pending"  # czeka na moderację — niewidoczne publicznie
    NEW = "new"
    VERIFIED = "verified"
    FORWARDED = "forwarded"  # przekazane do urzędu — publiczny pasek interwencji
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class ReportCategory(str, Enum):
    EMERGENCY = "emergency"            # Wypadki, tonięcie, zawalenie
    FIRE = "fire"                      # Pożary
    INFRASTRUCTURE = "infrastructure"  # Roads, sidewalks, lighting
    WASTE = "waste"                    # Waste, trash, overflowing bins
    GREENERY = "greenery"              # Greenery, parks
    SAFETY = "safety"                  # Safety, road signs, barriers
    WATER = "water"                    # Water, sewage, leaks
    OTHER = "other"                    # Other issues


class Report(SQLModel, table=True):
    """Zgłoszenia mieszkańców – usterki, awarie, zdarzenia"""
    __tablename__ = "reports"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Autor (opcjonalnie zalogowany)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    author_name: Optional[str] = Field(default=None, max_length=100)
    author_email: Optional[str] = Field(default=None, max_length=255)
    author_phone: Optional[str] = Field(default=None, max_length=50)

    # Treść
    title: str = Field(max_length=200)
    description: str
    ai_summary: Optional[str] = None

    # Kategoryzacja (AI)
    category: str = Field(default=ReportCategory.OTHER.value, max_length=50, index=True)
    ai_detected_objects: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    ai_condition_assessment: Optional[str] = Field(default=None, max_length=500)
    ai_severity: Optional[str] = Field(default=None, max_length=20)  # low, medium, high, critical

    # Media
    image_url: Optional[str] = Field(default=None, max_length=500)
    generated_image_url: Optional[str] = Field(default=None, max_length=500)

    # Geolokalizacja
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = Field(default=None, max_length=300)
    location_name: Optional[str] = Field(default=None, max_length=100)

    # Status
    status: str = Field(default=ReportStatus.NEW.value, max_length=20, index=True)
    is_spam: bool = Field(default=False)

    # Interakcja
    upvotes: int = Field(default=0)
    views_count: int = Field(default=0)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


# ======================
# Push Notifications (Sprint 5C)
# ======================

class PushSubscription(SQLModel, table=True):
    """Subskrypcje Web Push Notifications"""
    __tablename__ = "push_subscriptions"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Powiązanie z użytkownikiem (opcjonalne)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    email: Optional[str] = Field(default=None, max_length=255)  # dla niezalogowanych

    # Web Push Protocol fields
    endpoint: str = Field(max_length=1000, unique=True, index=True)  # URL push service
    p256dh: str = Field(max_length=200)   # klucz szyfrowania
    auth: str = Field(max_length=100)     # auth secret

    # Kategorie powiadomień: alerty, powietrze, artykuly, wydarzenia
    categories: list = Field(default_factory=list, sa_column=Column(JSONB))

    # Metadata urządzenia
    user_agent: Optional[str] = Field(default=None, max_length=500)

    # Status
    active: bool = Field(default=True)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None


# ======================
# Waste Schedule (Sprint 7 - Organizator.ai)
# ======================

class WasteSchedule(SQLModel, table=True):
    """Harmonogram wywozu śmieci dla miejscowości Gminy Rybno"""
    __tablename__ = "waste_schedule"

    id: Optional[int] = Field(default=None, primary_key=True)
    town: str = Field(index=True)
    waste_type: str
    collection_date: date = Field(index=True)
    year: int = Field(index=True, default=0)


# ======================
# Local Places (Gemini Maps grounding)
# ======================

class LocalPlace(SQLModel, table=True):
    """Lokalne miejsca z Google Maps (restauracje, atrakcje, hotele itp.)"""
    __tablename__ = "local_places"

    id: Optional[int] = Field(default=None, primary_key=True)
    place_id: str = Field(max_length=200, unique=True, index=True)
    name: str = Field(max_length=300)
    category: str = Field(max_length=50, index=True)
    description: Optional[str] = Field(default=None, max_length=2000)
    address: Optional[str] = Field(default=None, max_length=500)
    maps_uri: Optional[str] = Field(default=None, max_length=500)
    extra_data: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    active: bool = Field(default=True)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ======================
# Anonymous Chat Usage (Rate Limiting)
# ======================

# ======================
# Health Module (Clinic Schedules + Pharmacy Duty)
# ======================

class ClinicSchedule(SQLModel, table=True):
    """Harmonogram przyjęć poradni SPGZOZ Rybno"""
    __tablename__ = "clinic_schedules"
    __table_args__ = (
        Index('idx_clinic_day', 'clinic_name', 'day_of_week'),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    clinic_name: str = Field(max_length=100, index=True)  # "POZ", "Stomatologiczna", etc.
    doctor_name: Optional[str] = Field(default=None, max_length=200)
    doctor_role: Optional[str] = Field(default=None, max_length=100)
    day_of_week: Optional[int] = None  # 0=Pon ... 6=Nd (for weekly schedules)
    specific_date: Optional[date] = None  # for USG (specific dates)
    hours_from: str = Field(max_length=10)  # "08:00"
    hours_to: str = Field(max_length=10)  # "18:00"
    notes: Optional[str] = Field(default=None, max_length=500)
    source_url: str = Field(max_length=500)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class PharmacyDuty(SQLModel, table=True):
    """Dyżury aptek w powiecie działdowskim"""
    __tablename__ = "pharmacy_duties"

    id: Optional[int] = Field(default=None, primary_key=True)
    pharmacy_name: str = Field(max_length=200, index=True)
    address: str = Field(max_length=300)
    phone: Optional[str] = Field(default=None, max_length=50)
    duty_type: str = Field(max_length=20)  # "weekday", "weekend", "holiday"
    day_of_week: Optional[int] = None  # 0-6 for regular duties
    specific_dates: Optional[List[str]] = Field(default=None, sa_column=Column(ARRAY(String)))
    hours_from: str = Field(max_length=10)
    hours_to: str = Field(max_length=10)
    valid_year: int
    notes: Optional[str] = Field(default=None, max_length=500)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class AnonymousChatUsage(SQLModel, table=True):
    """Śledzenie użycia chatu przez anonimowych użytkowników (po IP)"""
    __tablename__ = "anonymous_chat_usage"
    __table_args__ = (
        Index('idx_anon_ip_date', 'ip_address', 'usage_date', unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    ip_address: str = Field(index=True, max_length=50)
    usage_date: date = Field(index=True)
    count: int = Field(default=0)


# ======================
# Bus Timetable (Linia RYBNO–DZIAŁDOWO przez Płośnicę)
# ======================

class BusStop(SQLModel, table=True):
    """Przystanki autobusowe na trasie Rybno–Działdowo"""
    __tablename__ = "bus_stops"

    id: Optional[int] = Field(default=None, primary_key=True)
    stop_id: str = Field(max_length=50, unique=True, index=True)  # np. "rybno", "plosnica"
    name: str = Field(max_length=100)                              # "Rybno (Centrum)"
    lat: float
    lng: float
    sequence: int  # kolejność w kierunku RYB→DZA (1–13)


class BusTrip(SQLModel, table=True):
    """Kurs autobusowy – jeden przejazd w danym kierunku"""
    __tablename__ = "bus_trips"

    id: Optional[int] = Field(default=None, primary_key=True)
    direction: str = Field(max_length=30, index=True)   # RYBNO_DZIALDOWO | DZIALDOWO_RYBNO
    departure_time: str = Field(max_length=5)           # godzina odjazdu z pierwszego przystanku HH:MM
    service_type: str = Field(max_length=2)             # GS | S | G


class BusStopTime(SQLModel, table=True):
    """Godziny przyjazdu autobusu na każdy przystanek"""
    __tablename__ = "bus_stop_times"
    __table_args__ = (
        Index('idx_bus_stop_times_trip_seq', 'trip_id', 'stop_sequence'),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    trip_id: int = Field(foreign_key="bus_trips.id", index=True)
    stop_id: str = Field(max_length=50, index=True)  # odpowiada BusStop.stop_id
    stop_sequence: int                                # 1-based kolejność w tym kursie
    arrival_time: str = Field(max_length=5)           # HH:MM


# ======================
# Referral Program (Monetyzacja)
# ======================

class Referral(SQLModel, table=True):
    """Program poleceń — poleć znajomemu, oboje dostają +14 dni Premium"""
    __tablename__ = "referrals"
    __table_args__ = (
        Index('idx_referral_referrer', 'referrer_id'),
        Index('idx_referral_referred', 'referred_id', unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Kto polecił
    referrer_id: int = Field(foreign_key="users.id", index=True)

    # Kto dołączył przez polecenie
    referred_id: int = Field(foreign_key="users.id", index=True)

    # Nagroda
    rewarded_at: Optional[datetime] = None  # NULL = jeszcze nie nagrodzony
    reward_days: int = Field(default=14)    # Ile dni Premium dostają oboje

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ======================
# BIP — wiedza stała (2026-08-03)
# ======================

class BipDocument(SQLModel, table=True):
    """
    Dokument ze stałych działów BIP: statut, procedury, podatki, ochrona
    środowiska, fundusz sołecki.

    Osobna tabela, a nie `articles`, i to jest cała istota tego modelu.
    Artykuły trafiają do feedu, a `feed_policy.LOCAL_SOURCES` zalicza BIP
    Gminy Rybno do źródeł lokalnych — statut uchwalony w 2016 r. wjechałby
    mieszkańcowi na Dashboard jako świeża wiadomość z gminy. Wiedza stała
    nie jest newsem: ma odpowiadać agentowi, gdy ktoś zapyta, i nie pokazywać
    się nigdzie indziej.

    Drugi powód: te dokumenty się nie starzeją, więc nie obowiązuje ich
    cutoff dwóch dni ani limit 1000 znaków ze scrapera aktualności.
    `content_hash` decyduje o ponownym osadzeniu — BIP odświeża strony bez
    zmiany treści, a embedding kosztuje.
    """
    __tablename__ = "bip_documents"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Skąd — `section_id` to numer działu w URL (np. 105 = Podatki i opłaty)
    section_id: str = Field(max_length=20, index=True)
    section_name: str = Field(max_length=200)

    url: str = Field(max_length=1000, unique=True, index=True)
    title: str = Field(max_length=500)

    # Pełna treść: HTML strony + tekst wyciągnięty ze WSZYSTKICH załączników PDF
    content: Optional[str] = None
    content_hash: str = Field(max_length=64, index=True)
    pdf_count: int = Field(default=0)

    # Data z BIP („Data wytworzenia informacji") — bywa sprzed lat i to jest OK
    document_date: Optional[datetime] = None

    embedded: bool = Field(default=False, index=True)
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_checked_at: datetime = Field(default_factory=datetime.utcnow)
    content_changed_at: Optional[datetime] = None


# ======================
# Sesje Rady Gminy — transkrypcja obrad (2026-08-09)
# ======================

class CouncilSession(SQLModel, table=True):
    """
    Jedna sesja Rady Gminy: nagranie, transkrypt, skrót i decyzja człowieka.

    Osobna tabela, a nie `articles` — z tego samego powodu co `bip_documents`,
    tylko odwrotnie ustawionego. BIP nie może wjechać do feedu, bo jest stary.
    Skrót sesji nie może wjechać do feedu, bo **nie jest jeszcze zatwierdzony**:
    powstaje automatycznie i do czasu akceptacji nie istnieje dla nikogo poza
    adminem. Dopiero `status = published` czyni z niego treść.

    **Transkrypt zostaje w bazie na stałe** i to nie jest zapasowa kopia.
    Weryfikacja cytatu (`Transcript.locate`) wymaga segmentów ze znacznikami
    czasu, więc bez nich nie da się później ani sprawdzić, czy zdanie przypisane
    radnemu naprawdę padło, ani osadzić obrad w RAG. Przepisanie nagrania od
    nowa kosztuje $0,52 — trzymanie ~70 kB JSON-a nie kosztuje nic.

    Tożsamość niesie `external_id` = `page_id` z galerii gminy, nie URL:
    slug podstrony zmienia się przy korekcie literówki w tytule, numer nie.
    """
    __tablename__ = "council_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)

    # --- skąd (galeria gminy → YouTube) ---
    external_id: str = Field(max_length=32, unique=True, index=True)
    title: str = Field(max_length=500)
    session_number: Optional[str] = Field(default=None, max_length=20)  # rzymski, z tytułu
    session_date: Optional[datetime] = Field(default=None, index=True)
    page_url: str = Field(max_length=1000)
    youtube_id: Optional[str] = Field(default=None, max_length=20)

    # --- materiał źródłowy ---
    duration_s: float = Field(default=0.0)
    transcript_chars: int = Field(default=0)
    transcript_json: Optional[str] = None  # {"segments": [{start, end, text}], ...}

    # --- skrót (CouncilSummaryModel po weryfikacji, JSON) ---
    summary_json: Optional[str] = None

    # --- raport jakości; po tym admin decyduje, czy w ogóle warto czytać ---
    quotes_total: int = Field(default=0)
    quotes_verified: int = Field(default=0)
    quotes_dropped: int = Field(default=0)
    timestamps_fixed: int = Field(default=0)
    # Druga bramka: zdania opisów konfrontowane z fragmentem nagrania.
    # `claims_flagged_text` trzyma usunięte zdania — admin musi zobaczyć, CO
    # model zmyślił, a nie tylko ile razy; sam licznik niczego nie uczy.
    claims_total: int = Field(default=0)
    claims_flagged: int = Field(default=0)
    claims_flagged_text: Optional[str] = None
    # Obie bramki przeszły bez zastrzeżeń. Nadal NIE znaczy „opublikuj bez
    # czytania" — sędzia opisów przepuszcza zdania niejednoznaczne z rozmysłem
    # (fałszywy alarm uczy ignorować ostrzeżenia), a wybór tematów do skrótu
    # nie jest weryfikowany przez nic.
    quotes_clean: bool = Field(default=False)

    # --- decyzja człowieka ---
    status: str = Field(default=CouncilSessionStatus.NEW.value, max_length=20, index=True)
    # Losowy token z maila do admina. Osobno od JWT, żeby akceptacja działała
    # z telefonu bez logowania — ten sam wzorzec co wypis z newslettera.
    review_token: Optional[str] = Field(default=None, max_length=64, unique=True, index=True)
    review_note: Optional[str] = Field(default=None, max_length=1000)
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[int] = Field(default=None, foreign_key="users.id")
    published_at: Optional[datetime] = None

    # --- przebieg ---
    attempts: int = Field(default=0)
    last_error: Optional[str] = Field(default=None, max_length=1000)
    cost_usd: float = Field(default=0.0)
    embedded: bool = Field(default=False, index=True)  # transkrypt w RAG (kolejny etap)

    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
