"""
Tryb sztormowy — dzień, w którym rytm dwóch przebiegów nie wystarcza (2026-08-22)

22.08.2026 przez gminę przeszła nawałnica. Energa zgłosiła wyłączenia w Gralewie,
Grądach i Kopaniarzach, mieszkańcy pisali o braku wody, sołtysi i profil Syli
publikowały komunikaty — a strona milczała. Nie dlatego, że coś się zepsuło:
Facebook czytamy o 6:00, a poza profilem gminy i ZGK nie czytamy go w ciągu dnia
w ogóle, bo Apify kosztuje. Komunikat Syli z 9:00 wszedłby do systemu nazajutrz.

Wniosek nie brzmi „scrapować częściej", bo 360 dni w roku dwa przebiegi wystarczają
i płacenie za trzeci byłoby marnotrawstwem. Brzmi: **system ma rozpoznać dzień,
w którym nie wystarczają**, i tylko wtedy sięgnąć po płatne źródło.

Sygnał bierzemy z tego, co i tak mamy za darmo:
- feed Energi (RSS, odświeżany co 3 h) — kilka wyłączeń w gminie naraz to nie
  awaria pojedynczego transformatora, tylko pogoda;
- ostrzeżenia IMGW, które już dziś rozpoznaje `weather_alert`.

Trzy hamulce, bo tryb sztormowy wydaje pieniądze:
- ODSTĘP — minimum `MIN_GAP_H` od ostatniego pobrania profili FB. Liczony
  z `sources.last_scraped`, czyli ze stanu bazy: przeżywa restart kontenera
  i nie wymaga własnego licznika, którego deploy by wyzerował;
- GODZINY — tylko `ACTIVE_HOURS`, bo o czwartej nad ranem nikt tego nie przeczyta,
  a Apify policzy tak samo;
- PRÓG — `LOCAL_OUTAGE_THRESHOLD` wyłączeń NASZEJ gminy. Pojedyncze wyłączenie
  zdarza się co tydzień i nie jest sztormem.

Po pobraniu nie trzeba nic więcej: `alert_push_job` chodzi co 15 minut i czyta
TEKST, nie kategorię (`_candidates` nie wymaga `processed`), więc świeży komunikat
o braku wody może obudzić telefon jeszcze przed kategoryzacją o 13:15.
"""
from datetime import datetime, timedelta
from typing import Optional

# Ile wyłączeń w gminie naraz przestaje być zbiegiem okoliczności. Jedno zdarza
# się co tydzień; dwa w oknie trzech godzin to już front atmosferyczny.
LOCAL_OUTAGE_THRESHOLD = 2

# Okno, w którym liczymy wyłączenia „naraz"
LOOKBACK_H = 3

# Ile godzin do przodu wyłączenie jeszcze uznajemy za „dzieje się teraz".
# Bez tego progu liczyły się zapowiedzi: Energa re-scrapuje wpisy planowane
# co 3 h, więc wyłączenie ogłoszone na 28 sierpnia ma dziś świeży `scraped_at`
# i wyglądało jak awaria trwająca (pomiar 22.08 — sześć „wyłączeń w gminie",
# z czego trzy dotyczyły przyszłego tygodnia).
ONGOING_MARGIN_H = 2

# Minimalny odstęp między płatnymi przebiegami. Dwie godziny, nie jedna:
# przy sześciogodzinnej wichurze daje to trzy dodatkowe pobrania, a nie sześć.
MIN_GAP_H = 2.0

# Godziny lokalne, w których tryb sztormowy w ogóle się uruchamia
ACTIVE_HOURS = (6, 22)


def within_active_hours(now_local: datetime) -> bool:
    """Czy to pora, o której ktoś jeszcze przeczyta komunikat."""
    start, end = ACTIVE_HOURS
    return start <= now_local.hour < end


def enough_gap(last_scraped: Optional[datetime], now: Optional[datetime] = None) -> bool:
    """
    Czy minęło dość czasu od ostatniego pobrania płatnych profili.

    `None` znaczy „nigdy nie pobierano" — wtedy nie ma czego oszczędzać.
    Oba czasy naiwne UTC, jak reszta projektu.
    """
    if last_scraped is None:
        return True
    now = now or datetime.utcnow()
    return (now - last_scraped) >= timedelta(hours=MIN_GAP_H)


def is_ongoing(
    event_at: Optional[datetime],
    event_until: Optional[datetime],
    now: Optional[datetime] = None,
) -> bool:
    """
    Czy wyłączenie dzieje się TERAZ (albo zacznie się lada chwila).

    Sztorm poznajemy po awariach trwających, nie po zapowiedziach. Wpis bez
    terminu traktujemy jak trwający — kanał „bieżące" Energi tak właśnie
    zgłasza awarie, o których jeszcze nic nie wiadomo poza tym, że są.
    """
    now = now or datetime.utcnow()
    if event_at is None and event_until is None:
        return True
    if event_at and event_at > now + timedelta(hours=ONGOING_MARGIN_H):
        return False  # zapowiedź na inny dzień
    if event_until and event_until < now:
        return False  # już po wszystkim
    return True


def storm_reason(local_outages: int, weather_alert: bool) -> Optional[str]:
    """
    Powód uruchomienia trybu sztormowego albo `None`, gdy dzień jest zwyczajny.

    Zwracamy TEKST, nie `bool`: ten powód trafia do logu i do maila, a przy
    pytaniu „czemu wczoraj poszły trzy dodatkowe przebiegi Apify" odpowiedź
    ma być w logu, nie w rekonstrukcji ze stanu bazy.
    """
    if local_outages >= LOCAL_OUTAGE_THRESHOLD:
        return f"{local_outages} wyłączenia prądu w gminie w ciągu {LOOKBACK_H} h"
    if weather_alert:
        return "obowiązujące ostrzeżenie meteorologiczne"
    return None
