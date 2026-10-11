"""
Tekst z kanałów RSS bez śmieci WordPressa (audyt 11.10.2026, F-040).

Scraper RSS zdejmował znaczniki HTML, ale zostawiał encje — 171 wpisów Radia 7
i 17 Radia Olsztyn z 30 dni pokazywało w feedzie „&#8222;Duma Zawkrza&#8221;”
i „&#8230;” — a każdy wpis Radia Olsztyn kończył się stopką „The post … appeared
first on Radio Olsztyn.” Ta sama funkcja działa przy POBIERANIU (nowe wpisy)
i przy WYDAWANIU z API (stare wpisy wyglądają poprawnie bez przepisywania bazy).
"""
import html
import re
from typing import Optional

# Stopka wtyczki WordPressa w kanale RSS: „The post <tytuł> appeared first on <serwis>.”
_WP_FOOTER = re.compile(r"\s*The post .{0,300}? appeared first on .{0,120}?\.?\s*$", re.IGNORECASE | re.DOTALL)
# Skrót WordPressa „[…]” na końcu wypisu
_WP_ELLIPSIS = re.compile(r"\s*\[(?:…|\.\.\.)\]\s*$")


def clean_feed_text(text: Optional[str]) -> Optional[str]:
    """Encje HTML → znaki, bez stopki „The post … appeared first on …” i „[…]”.
    Dwukrotne `unescape`, bo bywa `&amp;#8230;` (encja zakodowana podwójnie)."""
    if not text:
        return text
    cleaned = html.unescape(html.unescape(text))
    cleaned = _WP_FOOTER.sub("", cleaned)
    cleaned = _WP_ELLIPSIS.sub("…", cleaned)
    cleaned = cleaned.replace("\xa0", " ")
    return cleaned.strip()
