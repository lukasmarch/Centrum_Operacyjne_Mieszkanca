"""
Scraper Registry Pattern

Centralny rejestr wszystkich scraperów w systemie.
Mapuje nazwę źródła (Source.name) na odpowiednią klasę scrapera.
"""
from typing import Dict, Type, Optional
from src.scrapers.base import BaseScraper
from src.scrapers.klikajinfo import KlikajInfoScraper
from src.scrapers.gmina_rybno import GminaRybnoScraper
from src.scrapers.mojedzialdowo import MojeDzialdowoScraper
from src.scrapers.apify_facebook import ApifyFacebookScraper
from src.scrapers.rss_scraper import RSSFeedScraper
from src.scrapers.bip_rybno import BipRybnoScraper
from src.utils.logger import setup_logger

logger = setup_logger("ScraperRegistry")

# Rejestr: nazwa źródła -> klasa scrapera
SCRAPER_REGISTRY: Dict[str, Type[BaseScraper]] = {
    "Klikaj.info": KlikajInfoScraper,
    "Gmina Rybno": GminaRybnoScraper,
    "Moje Działdowo": MojeDzialdowoScraper,
    "Facebook - Syla": ApifyFacebookScraper,
    "Nasze Miasto Działdowo": RSSFeedScraper,
    "BIP Gminy Rybno": BipRybnoScraper,
}


def get_scraper(source_name: str) -> Optional[Type[BaseScraper]]:
    """
    Pobiera klasę scrapera dla danego źródła.

    Obsługuje:
    - Dokładne dopasowanie nazwy (np. "Klikaj.info")
    - Pattern matching dla Facebook (wszystkie "Facebook - *" używają ApifyFacebookScraper)
    - Pattern matching dla RSS (wszystkie "*RSS" używają RSSFeedScraper)

    Args:
        source_name: Nazwa źródła z tabeli sources (np. "Klikaj.info", "Facebook - Syla")

    Returns:
        Klasa scrapera lub None jeśli nie znaleziono
    """
    # Najpierw sprawdź dokładne dopasowanie
    scraper_class = SCRAPER_REGISTRY.get(source_name)

    # Jeśli nie znaleziono, sprawdź pattern matching
    if not scraper_class:
        # Wszystkie źródła Facebook używają ApifyFacebookScraper
        if source_name.startswith("Facebook - "):
            scraper_class = ApifyFacebookScraper
            logger.debug(f"Matched Facebook pattern for: {source_name}")
        # Wszystkie źródła RSS (kończące się na "RSS" lub zawierające "RSS")
        elif "RSS" in source_name or source_name.endswith("(RSS)"):
            scraper_class = RSSFeedScraper
            logger.debug(f"Matched RSS pattern for: {source_name}")
        else:
            logger.warning(f"No scraper found for source: {source_name}")
            return None

    logger.debug(f"Found scraper {scraper_class.__name__} for source: {source_name}")
    return scraper_class


def register_scraper(source_name: str, scraper_class: Type[BaseScraper]):
    """
    Rejestruje nowy scraper w systemie.

    Args:
        source_name: Nazwa źródła
        scraper_class: Klasa scrapera dziedzicząca po BaseScraper
    """
    if not issubclass(scraper_class, BaseScraper):
        raise TypeError(f"{scraper_class.__name__} must inherit from BaseScraper")

    SCRAPER_REGISTRY[source_name] = scraper_class
    logger.info(f"Registered scraper {scraper_class.__name__} for source: {source_name}")


def list_scrapers() -> Dict[str, str]:
    """
    Zwraca listę wszystkich zarejestrowanych scraperów.

    Returns:
        Dict mapujący nazwę źródła na nazwę klasy scrapera
    """
    return {
        source_name: scraper_class.__name__
        for source_name, scraper_class in SCRAPER_REGISTRY.items()
    }
