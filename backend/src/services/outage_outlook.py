"""
Przegląd awarii na pulpicie — „czy w mojej wsi będzie prąd i woda”.

Pulpit odpowiadał na to pytanie tylko w oknie przypięcia (`is_pinned_alert`,
30 h w przód). Krytyka 11.10.2026: wyłączenie w Grądach zapowiedziane na
14.10 stało czwartym ekranem niżej jako zwykła wiadomość, a w spokojny dzień
strona nigdy nie mówiła „u Ciebie nic nie zapowiedziano”. Ten moduł daje
pulpitowi jedną listę: awarie w gminie, które trwają albo są zapowiedziane
na najbliższe dni, z miejscowościami i godzinami.

Rodzaj, miejsce i czas rozstrzygają TE SAME reguły co push i feed
(`alert_policy.incident_of`, `feed_policy.is_foreign_incident`,
`alert_policy.span_from_text`, `feed_policy.event_end`) — tu nie powstaje
żadna nowa definicja awarii, tylko dłuższe okno w przód.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Optional

from src.services import alert_policy, feed_policy, time_span
from src.services.weather_alert import is_weather_alert

# Jak daleko w przód pulpit pokazuje zapowiedź. Energa ogłasza planowe
# wyłączenia zwykle 5–7 dni wcześniej; tydzień mieści całą zapowiedź.
OUTLOOK_DAYS = 7

# Awaria bez terminu (zgłoszenie: „brak wody w Tuczkach”) — tyle samo, ile
# trzyma ją przypięcie feedu. ZGK nie publikuje „już działa”, więc dłużej
# nie wolno twierdzić, że trwa.
UNDATED_HOURS = feed_policy.AWARIA_PIN_HOURS


@dataclass(frozen=True)
class OutlookItem:
    article_id: int
    title: str
    kind: str
    label: str
    places: tuple[str, ...]
    start: Optional[datetime]
    end: Optional[datetime]
    ongoing: bool
    reported_at: Optional[datetime]


def outlook_item(article, now: datetime) -> Optional[OutlookItem]:
    """Pozycja przeglądu albo `None`, gdy wpis nie jest naszą awarią w oknie."""
    shown = getattr(article, "display_title", None) or article.title
    content = article.content
    category = article.category or ""

    if is_weather_alert(shown, content):
        return None  # pogoda ma własny kanał (przypięcie feedu), to nie „prąd i woda”

    incident = alert_policy.incident_of(shown, content) or alert_policy.incident_of(article.title, content)
    if incident is None and "awari" not in category.lower():
        return None
    if feed_policy.is_foreign_incident(
        article.category, article.title, content, article.locality, getattr(article, "display_title", None)
    ):
        return None

    kind, label = incident or ("inne", "Awaria")
    found = alert_policy.places_in(article.title, content) or alert_policy.places_in(shown, content)
    # „Rybno gmina wiejska” w tytule Energi i „ZGK w Rybnie” w podpisie to nazwa
    # ADMINISTRACYJNA, nie miejsce zdarzenia — ta sama reguła co sygnatura push
    core = alert_policy._incident_places(frozenset(found))
    places = tuple(p for p in found if p in core)

    start, end = article.event_at, article.event_until
    if start is None and end is None:
        start, end = alert_policy.span_from_text(article.title, content, article.published_at)

    if start is not None:
        finish = feed_policy.event_end(start, end)
        if finish is not None and now > finish:
            return None  # po zdarzeniu
        if start - now > timedelta(days=OUTLOOK_DAYS):
            return None  # za daleko — wróci do przeglądu bliżej terminu
        return OutlookItem(article.id, shown, kind, label, places, start, end, start <= now, None)

    reported = article.published_at or article.scraped_at
    if reported is None or now - reported > timedelta(hours=UNDATED_HOURS):
        return None
    return OutlookItem(article.id, shown, kind, label, places, None, None, True, reported)


def build_outlook(articles: Iterable, now: datetime) -> list[OutlookItem]:
    """
    Awarie w gminie: najpierw trwające, potem według terminu.

    Przedruki tej samej awarii (dwa kanały Energi, ZGK i Syla) zwija
    `alert_policy.same_incident` — ta sama reguła, która pilnuje, żeby push
    nie zadzwonił dwa razy.
    """
    items = [item for item in (outlook_item(a, now) for a in articles) if item]
    items.sort(key=lambda i: (not i.ongoing, i.start or i.reported_at or now))

    def sig(item: OutlookItem) -> Optional[tuple]:
        if not item.places:
            return None
        day = time_span.to_local(item.start).date() if item.start else None
        return (item.kind, frozenset(item.places), day)

    kept: list[OutlookItem] = []
    for item in items:
        if any(alert_policy.same_incident(sig(item), sig(k)) for k in kept):
            continue
        kept.append(item)
    return kept


def concerns_village(item: OutlookItem, village: Optional[str]) -> bool:
    """
    Czy pozycja dotyczy wsi czytelnika. W odróżnieniu od `alert_policy.concerns`
    brak nazwy wsi w komunikacie NIE znaczy tu „dotyczy” — pulpit mówi „w Twojej
    wsi spokojnie” tylko o tym, co wiemy, a awarię bez miejsca pokazuje jako
    sprawę gminy, nie wsi.
    """
    if not village or not item.places:
        return False
    return alert_policy.norm_place(village) in {alert_policy.norm_place(p) for p in item.places}
