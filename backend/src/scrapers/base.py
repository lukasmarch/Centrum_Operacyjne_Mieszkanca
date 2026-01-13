import asyncio
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.utils.logger import setup_logger
from src.database.schema import Article, Source

class BaseScraper(ABC):
    def __init__(self, source_id: int, config: Optional[Dict] = None):
        self.source_id = source_id
        self.config = config or {}
        self.logger = setup_logger(self.__class__.__name__)
        self.client: Optional[httpx.AsyncClient] = None

        self.user_agent = self.config.get('user_agent', settings.SCRAPER_USER_AGENT)
        self.timeout = self.config.get('timeout', settings.SCRAPER_TIMEOUT)
        self.rate_limit = self.config.get('rate_limit', settings.SCRAPER_RATE_LIMIT)
        self.max_retries = self.config.get('max_retries', settings.SCRAPER_MAX_RETRIES)

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            headers={'User-Agent': self.user_agent},
            timeout=self.timeout,
            follow_redirects=True
        )
        return self

    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()

    async def fetch(self, url: str) -> str:
        """Fetch HTML with retry logic and exponential backoff"""
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Fetching {url} (attempt {attempt + 1})")
                response = await self.client.get(url)

                if response.status_code == 429:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"Rate limited. Waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.text

            except httpx.TimeoutException:
                self.logger.error(f"Timeout on attempt {attempt + 1}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                self.logger.error(f"Error fetching {url}: {e}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

        raise Exception(f"Failed to fetch {url} after {self.max_retries} attempts")

    @abstractmethod
    async def parse(self, html: str, url: str) -> List[Dict]:
        """Parse HTML into structured article data. Override in subclasses."""
        pass

    async def save_to_db(self, articles: List[Dict], session: AsyncSession) -> List[int]:
        saved_ids = []

        for article_data in articles:
            try:
                # Check existence by URL OR external_id
                query = select(Article).where(Article.url == article_data['url'])
                
                if article_data.get('external_id'):
                    query = select(Article).where(
                        (Article.url == article_data['url']) | 
                        (Article.external_id == article_data['external_id'])
                    )

                existing = await session.execute(query)
                # Use first() in case we match multiple (e.g. old url + new url separate entries? shouldn't happen if unique)
                # specific to our logic, let's take one.
                existing_article = existing.scalars().first()

                if existing_article:
                    self.logger.info(f"Updating article: {article_data['url']} (ID: {existing_article.id})")
                    # Update fields
                    for key, value in article_data.items():
                        if value is not None:
                            setattr(existing_article, key, value)
                    
                    # Update metadata
                    existing_article.scraped_at = datetime.utcnow()
                    # Optional: reset processed status if we want to re-process content with AI
                    # existing_article.processed = False 
                    
                    session.add(existing_article)
                    await session.commit()
                    await session.refresh(existing_article)
                    saved_ids.append(existing_article.id)
                else:
                    article = Article(
                        source_id=self.source_id,
                        **article_data
                    )
                    session.add(article)
                    await session.commit()
                    await session.refresh(article)
                    saved_ids.append(article.id)
                    self.logger.info(f"Saved new article: {article.title}")

            except Exception as e:
                self.logger.error(f"Error saving article {article_data.get('url')}: {e}")
                await session.rollback()

        return saved_ids

    async def scrape(self, urls: List[str], session: AsyncSession) -> List[int]:
        """Main scraping orchestration"""
        all_saved_ids = []
        delay = 1.0 / self.rate_limit

        for url in urls:
            try:
                await asyncio.sleep(delay)
                html = await self.fetch(url)
                articles = await self.parse(html, url)
                saved_ids = await self.save_to_db(articles, session)
                all_saved_ids.extend(saved_ids)

            except Exception as e:
                self.logger.error(f"Error scraping {url}: {e}")

        return all_saved_ids
