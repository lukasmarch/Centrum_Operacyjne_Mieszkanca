"""
Stan źródeł: błąd nie udaje świeżości, alarm tylko przy zmianie (audyt 11.10.2026, F-019/F-020).

Bez bazy i sieci — dlatego idzie do CI:
  1. przejścia stanu (`source_health.transition`) i treść alarmu,
  2. RSS: nieudane pobranie RZUCA wyjątek (do 11.10 zwracało [] → „zeskanowane”),
     a poprawny, pusty kanał wciąż jest sukcesem,
  3. BIP: błąd pierwszej strony RZUCA (do 11.10 `break` → pusta lista → sukces),
     błąd dalszej strony zostawia częściowy wynik.

    cd backend && python -m scripts.test_source_health
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import feedparser

from src.services import source_health as sh

results: list[bool] = []


def check(label: str, ok: bool, detail="") -> None:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + str(detail)) if detail else ''}")
    results.append(bool(ok))


def section_transitions() -> None:
    print("\n1️⃣  Przejścia stanu i alarm")
    t0 = datetime(2026, 10, 1, 6, 0)
    t1 = t0 + timedelta(hours=7)
    check("nowe źródło + sukces → bez alarmu", sh.transition(None, None, True) is None)
    check("nowe źródło + błąd → „przestało odpowiadać”", sh.transition(None, None, False) == sh.FAILED)
    check("działało + błąd → alarm", sh.transition(t0, None, False) == sh.FAILED)
    check("już leży + kolejny błąd → BEZ alarmu (BIP nie spamuje 2× dziennie)",
          sh.transition(t0, t1, False) is None)
    check("leżało + sukces → „znów odpowiada”", sh.transition(t0, t1, True) == sh.RECOVERED)
    check("działa + sukces → bez alarmu", sh.transition(t1, t0, True) is None)
    text = sh.alert_text([("BIP Rybno", sh.FAILED, "403 Forbidden"), ("Radio 7", sh.RECOVERED, None)])
    check("jedna wiadomość z oboma kierunkami",
          text and "BIP Rybno — 403" in text and "Radio 7" in text and text.count("🔴") == 1, text)
    check("brak zmian → brak wiadomości", sh.alert_text([]) is None)


def section_rss() -> None:
    print("\n2️⃣  RSS: błąd pobrania ≠ pusty kanał")
    from src.scrapers.rss_scraper import RSSFeedScraper
    scraper = RSSFeedScraper.__new__(RSSFeedScraper)
    import logging
    scraper.logger = logging.getLogger("test")
    scraper.config = {}

    async def failed_fetch(url):
        return feedparser.FeedParserDict()  # tak `_fetch_feed` oddaje błąd sieci
    scraper._fetch_feed = failed_fetch
    try:
        asyncio.run(scraper.scrape_feed("https://example.invalid/feed"))
        check("nieudane pobranie rzuca wyjątek", False, "zwróciło wynik")
    except Exception as e:
        check("nieudane pobranie rzuca wyjątek", True, type(e).__name__)

    async def empty_feed(url):
        return feedparser.parse(b"<rss version='2.0'><channel><title>x</title></channel></rss>")
    scraper._fetch_feed = empty_feed
    try:
        out = asyncio.run(scraper.scrape_feed("https://example.invalid/feed"))
        check("poprawny, pusty kanał to sukces z pustą listą", out == [], out)
    except Exception as e:
        check("poprawny, pusty kanał to sukces z pustą listą", False, e)


def section_bip() -> None:
    print("\n3️⃣  BIP: błąd pierwszej strony ≠ brak aktualności")
    from src.scrapers.bip_rybno import BipRybnoScraper
    scraper = BipRybnoScraper(source_id=12, config={})  # prawdziwy konstruktor, bez sieci
    scraper.news_url = "https://example.invalid/112/"

    async def forbidden(url):
        raise RuntimeError("403 Forbidden")
    scraper.fetch = forbidden
    try:
        asyncio.run(scraper.scrape_bip(None))
        check("403 na pierwszej stronie rzuca wyjątek", False, "zwróciło wynik")
    except Exception as e:
        check("403 na pierwszej stronie rzuca wyjątek", "403" in str(e), e)


if __name__ == "__main__":
    section_transitions()
    section_rss()
    section_bip()
    failed = results.count(False)
    print(f"\n{'✅' if not failed else '❌'} {len(results) - failed}/{len(results)} sprawdzeń")
    sys.exit(1 if failed else 0)
