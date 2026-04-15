from .base import BaseScraper
from .gmina_rybno import GminaRybnoScraper
from .mojedzialdowo import MojeDzialdowoScraper
from .apify_facebook import ApifyFacebookScraper
from .registry import SCRAPER_REGISTRY, get_scraper, register_scraper, list_scrapers

__all__ = [
    "BaseScraper",
    "GminaRybnoScraper",
    "MojeDzialdowoScraper",
    "ApifyFacebookScraper",
    "SCRAPER_REGISTRY",
    "get_scraper",
    "register_scraper",
    "list_scrapers",
]
