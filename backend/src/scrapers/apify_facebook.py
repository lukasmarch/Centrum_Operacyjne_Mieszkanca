from typing import List, Dict, Optional
from datetime import datetime
import httpx
import re

from src.scrapers.base import BaseScraper

class ApifyFacebookScraper(BaseScraper):
    """
    Scraper dla postów z Facebooka wykorzystujący Apify API.
    Actor: apify/facebook-posts-scraper

    KONFIGURACJA WYMAGANA:

    1. Załóż konto na Apify: https://apify.com
    2. Pobierz API token z: https://console.apify.com/account/integrations
    3. Wybierz Facebook Posts Scraper actor:
       https://apify.com/apify/facebook-posts-scraper

    4. Dodaj do .env:
       APIFY_API_KEY=apify_api_***********

    5. Utwórz source w bazie z konfiguracją:
       {
         "apify_api_key": "apify_api_***",
         "facebook_page_url": "https://www.facebook.com/serwis.informacyjny.syla",
         "results_limit": 20,
         "caption_text": false,
         "actor_id": "apify/facebook-posts-scraper"
       }

    UŻYCIE:

    source = Source(
        name="Facebook - Syla",
        type="social_media",
        url="https://www.facebook.com/serwis.informacyjny.syla",
        scraping_config={
            "apify_api_key": "...",
            "facebook_page_url": "https://www.facebook.com/serwis.informacyjny.syla",
            "results_limit": 20,
            "caption_text": false
        }
    )

    scraper = ApifyFacebookScraper(source_id=source.id, config=source.scraping_config)
    async with scraper:
        articles = await scraper.scrape([source.url], session)

    UWAGA:
    - Koszt: ~$0.25 za 1000 postów (sprawdź pricing Apify)
    - Rate limit: zgodnie z planem Apify
    - Facebook może blokować - używaj odpowiednich actor settings
    - Wspiera ~10+ kont FB (każde jako osobne source w bazie)
    """

    def __init__(self, source_id: int, config: Optional[Dict] = None):
        super().__init__(source_id, config)

        # Sprawdź czy mamy wymagane klucze konfiguracji
        self.apify_api_key = self.config.get('apify_api_key')
        self.facebook_page_url = self.config.get('facebook_page_url')
        self.results_limit = self.config.get('results_limit', 20)
        self.caption_text = self.config.get('caption_text', False)
        self.actor_id = self.config.get('actor_id', 'apify/facebook-posts-scraper')

        if not self.apify_api_key:
            raise ValueError("Missing 'apify_api_key' in scraper config")
        if not self.facebook_page_url:
            raise ValueError("Missing 'facebook_page_url' in scraper config")

    async def fetch(self, url: str) -> str:
        """
        Override fetch - zamiast HTML pobieramy JSON z Apify API.

        1. Uruchamiamy Apify actor (task)
        2. Czekamy na zakończenie
        3. Pobieramy wyniki jako JSON
        """
        self.logger.info(f"Starting Apify actor for Facebook page: {self.facebook_page_url}")

        try:
            # Konfiguracja Apify actor run dla facebook-posts-scraper
            actor_input = {
                "startUrls": [{"url": self.facebook_page_url}],
                "resultsLimit": self.results_limit,
                "captionText": self.caption_text,
            }

            # Uruchom actor
            async with httpx.AsyncClient(timeout=300) as client:
                # POST /v2/acts/{actorId}/runs
                run_url = f"https://api.apify.com/v2/acts/{self.actor_id}/runs"
                params = {"token": self.apify_api_key}

                self.logger.info(f"Running Apify actor: {self.actor_id}")
                response = await client.post(
                    run_url,
                    json=actor_input,
                    params=params
                )
                response.raise_for_status()
                run_data = response.json()

                run_id = run_data['data']['id']
                self.logger.info(f"Actor run started: {run_id}")

                # Czekaj na zakończenie (polling)
                # W produkcji: użyj webhooks zamiast pollingu
                import asyncio
                max_wait = 300  # 5 minut
                check_interval = 5  # co 5 sekund
                elapsed = 0

                while elapsed < max_wait:
                    await asyncio.sleep(check_interval)
                    elapsed += check_interval

                    # GET /v2/actor-runs/{runId}
                    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}"
                    status_response = await client.get(status_url, params=params)
                    status_response.raise_for_status()
                    status_data = status_response.json()

                    status = status_data['data']['status']
                    self.logger.info(f"Actor status: {status} (waited {elapsed}s)")

                    if status in ['SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT']:
                        break

                if status != 'SUCCEEDED':
                    raise Exception(f"Actor run failed with status: {status}")

                # Pobierz wyniki
                # GET /v2/actor-runs/{runId}/dataset/items
                dataset_url = f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items"
                dataset_response = await client.get(dataset_url, params=params)
                dataset_response.raise_for_status()

                # Zwróć JSON jako string (parse() oczekuje str)
                import json
                return json.dumps(dataset_response.json())

        except Exception as e:
            self.logger.error(f"Apify API error: {e}")
            raise

    async def parse(self, html: str, url: str) -> List[Dict]:
        """
        Parse JSON response z Apify do formatu Article.

        Apify Facebook scraper zwraca:
        {
          "posts": [
            {
              "postId": "123456789",
              "text": "Post content...",
              "url": "https://facebook.com/...",
              "timestamp": "2024-01-10T12:00:00Z",
              "imageUrl": "https://...",
              "likes": 42,
              "comments": 5,
              "shares": 2
            }
          ]
        }
        """
        import json

        articles = []

        try:
            data = json.loads(html)  # html jest JSON string

            # Apify zwraca listę bezpośrednio lub w kluczu 'posts'
            posts = data if isinstance(data, list) else data.get('posts', [])

            self.logger.info(f"Parsing {len(posts)} Facebook posts from Apify")

            for post in posts:
                try:
                    # Post ID - unique identifier
                    post_id = post.get('postId') or post.get('id')
                    if not post_id:
                        self.logger.warning("Post bez ID, pomijam")
                        continue

                    # Tekst posta
                    text = post.get('text') or post.get('message') or post.get('content')
                    if not text:
                        self.logger.warning(f"Post {post_id} bez tekstu, pomijam")
                        continue

                    # Tytuł - pierwsze 100 znaków tekstu lub pierwsze zdanie
                    title = text[:100]
                    if '. ' in title:
                        title = title.split('. ')[0] + '.'
                    if len(text) > 100:
                        title += '...'

                    # URL posta
                    post_url = post.get('url') or post.get('postUrl')
                    if not post_url:
                        # Fallback: generuj URL z post ID
                        post_url = f"https://facebook.com/{post_id}"

                    # Obrazek
                    image_url = post.get('imageUrl') or post.get('image') or post.get('picture')

                    # Data publikacji
                    published_at = None
                    timestamp = post.get('timestamp') or post.get('time') or post.get('createdTime')
                    if timestamp:
                        try:
                            published_at = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        except Exception as e:
                            self.logger.warning(f"Nieprawidłowy timestamp: {timestamp}")

                    # Dodatkowe metadata jako content
                    likes = post.get('likes', 0)
                    comments = post.get('comments', 0)
                    shares = post.get('shares', 0)

                    content = text
                    if likes or comments or shares:
                        content += f"\n\n[{likes} polubień, {comments} komentarzy, {shares} udostępnień]"

                    article_data = {
                        'title': title,
                        'url': post_url,
                        'content': content,
                        'image_url': image_url,
                        'external_id': f"fb_{post_id}",
                        'author': 'Facebook',  # lub post.get('from', {}).get('name')
                    }

                    if published_at:
                        article_data['published_at'] = published_at

                    articles.append(article_data)
                    self.logger.debug(f"Sparsowano post: {title[:50]}...")

                except (KeyError, TypeError, ValueError) as e:
                    self.logger.warning(f"Parse error dla posta: {e}")
                    continue

            self.logger.info(f"Znaleziono {len(articles)} postów z Facebooka")
            return articles

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response from Apify: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Parse error: {e}")
            return []

    async def scrape(self, urls: List[str], session) -> List[int]:
        """
        Override scrape - dla Apify nie iterujemy po URLs,
        tylko wywołujemy raz dla skonfigurowanej strony FB.
        """
        try:
            # Dla Facebook scraper ignorujemy urls parametr,
            # używamy self.facebook_page_url z config
            self.logger.info(f"Scraping Facebook page: {self.facebook_page_url}")

            # Fetch JSON z Apify
            json_data = await self.fetch(self.facebook_page_url)

            # Parse JSON do articles
            articles = await self.parse(json_data, self.facebook_page_url)

            # Save to DB
            saved_ids = await self.save_to_db(articles, session)

            return saved_ids

        except Exception as e:
            self.logger.error(f"Error scraping Facebook via Apify: {e}")
            return []
