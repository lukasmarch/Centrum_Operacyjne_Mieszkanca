"""
Firecrawl API Client (Sprint 5D)

Integracja z Firecrawl API (https://api.firecrawl.dev) do:
1. Scrapowania stron HTML z konwersją do Markdown
2. Ekstrakcji tekstu z PDF (formats=["markdown"])
3. Crawlowania całych stron (jednorazowy initial crawl BIP)

Klucz API: FIRECRAWL_API_KEY w .env
"""
import asyncio
from typing import Optional, List, Dict, Any

import httpx

from src.config import settings
from src.utils.logger import setup_logger

logger = setup_logger("FirecrawlClient")

FIRECRAWL_BASE_URL = "https://api.firecrawl.dev/v1"
FIRECRAWL_TIMEOUT = 60  # seconds


class FirecrawlClient:
    """
    Async Firecrawl API client.
    Używany jako fallback gdy lokalny scraper lub pdfplumber zawiedzie.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.FIRECRAWL_API_KEY
        if not self.api_key:
            logger.warning("FIRECRAWL_API_KEY not configured")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def scrape_page(
        self,
        url: str,
        formats: List[str] = None,
        only_main_content: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Pobierz i przetwórz stronę do Markdown.
        Działa też dla PDF (url kończący się na .pdf).

        Args:
            url: URL strony lub PDF
            formats: ["markdown"] (domyślnie) lub ["markdown", "html"]
            only_main_content: Wyciągnij tylko główną treść (usuń nav, footer)

        Returns:
            Dict z kluczami: markdown, html, metadata lub None przy błędzie
        """
        if not self._is_configured():
            logger.error("Firecrawl API key not configured")
            return None

        if formats is None:
            formats = ["markdown"]

        payload = {
            "url": url,
            "formats": formats,
            "onlyMainContent": only_main_content,
        }

        try:
            async with httpx.AsyncClient(timeout=FIRECRAWL_TIMEOUT) as client:
                response = await client.post(
                    f"{FIRECRAWL_BASE_URL}/scrape",
                    headers=self._headers(),
                    json=payload,
                )

                if response.status_code == 402:
                    logger.error("Firecrawl: payment required (quota exceeded)")
                    return None
                if response.status_code == 429:
                    logger.warning("Firecrawl: rate limited")
                    await asyncio.sleep(5)
                    return None

                response.raise_for_status()
                data = response.json()

                if data.get("success"):
                    return data.get("data", {})
                else:
                    logger.error(f"Firecrawl scrape failed: {data}")
                    return None

        except httpx.TimeoutException:
            logger.error(f"Firecrawl timeout for URL: {url}")
            return None
        except Exception as e:
            logger.error(f"Firecrawl error for {url}: {e}")
            return None

    async def extract_pdf_text(self, pdf_url: str) -> Optional[str]:
        """
        Wyciągnij tekst z PDF via Firecrawl.

        Args:
            pdf_url: Bezpośredni URL do pliku PDF

        Returns:
            Tekst w Markdown lub None przy błędzie
        """
        result = await self.scrape_page(pdf_url, formats=["markdown"])
        if result:
            return result.get("markdown")
        return None

    async def crawl_site(
        self,
        url: str,
        limit: int = 100,
        include_paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Crawluj całą stronę (jednorazowy initial crawl dla RAG).

        Args:
            url: Starting URL
            limit: Max liczba stron do crawlowania
            include_paths: Tylko te ścieżki (np. ["/112/"])
            exclude_paths: Pomiń te ścieżki

        Returns:
            Lista dict z markdown i metadanymi dla każdej strony
        """
        if not self._is_configured():
            logger.error("Firecrawl API key not configured")
            return []

        payload: Dict[str, Any] = {
            "url": url,
            "limit": limit,
            "scrapeOptions": {
                "formats": ["markdown"],
                "onlyMainContent": True,
            }
        }
        if include_paths:
            payload["includePaths"] = include_paths
        if exclude_paths:
            payload["excludePaths"] = exclude_paths

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Start crawl job
                response = await client.post(
                    f"{FIRECRAWL_BASE_URL}/crawl",
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
                crawl_data = response.json()

                if not crawl_data.get("success"):
                    logger.error(f"Firecrawl crawl init failed: {crawl_data}")
                    return []

                crawl_id = crawl_data.get("id")
                if not crawl_id:
                    logger.error("Firecrawl: no crawl ID returned")
                    return []

                logger.info(f"Firecrawl crawl started: {crawl_id}")

            # Poll for results
            return await self._poll_crawl_results(crawl_id)

        except Exception as e:
            logger.error(f"Firecrawl crawl error: {e}")
            return []

    async def _poll_crawl_results(
        self, crawl_id: str, max_wait: int = 300
    ) -> List[Dict[str, Any]]:
        """Poll for crawl results until complete or timeout."""
        elapsed = 0
        poll_interval = 5

        async with httpx.AsyncClient(timeout=30) as client:
            while elapsed < max_wait:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

                try:
                    response = await client.get(
                        f"{FIRECRAWL_BASE_URL}/crawl/{crawl_id}",
                        headers=self._headers(),
                    )
                    response.raise_for_status()
                    data = response.json()

                    status = data.get("status")
                    logger.info(
                        f"Crawl {crawl_id}: status={status}, "
                        f"completed={data.get('completed', 0)}/{data.get('total', '?')}"
                    )

                    if status == "completed":
                        return data.get("data", [])
                    elif status == "failed":
                        logger.error(f"Crawl {crawl_id} failed")
                        return []
                    # else: still "scraping" – continue polling

                except Exception as e:
                    logger.error(f"Poll error for crawl {crawl_id}: {e}")
                    break

        logger.warning(f"Crawl {crawl_id} timed out after {max_wait}s")
        return []


# Singleton
firecrawl_client = FirecrawlClient()
