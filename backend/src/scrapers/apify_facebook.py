from typing import List, Dict, Optional
from datetime import datetime
import httpx
import re

from src.config import settings
from src.scrapers.base import BaseScraper

# Model "pointer" dla treści z social mediów (prawo autorskie + RODO):
# przechowujemy nagłówek + snippet i odsyłamy do oryginału.
SOCIAL_SNIPPET_LIMIT = 300


def make_social_snippet(text: str, source_url: str) -> str:
    """Skróć treść posta do snippetu ≤300 znaków (na granicy słowa) + link do oryginału."""
    text = (text or "").strip()
    if len(text) > SOCIAL_SNIPPET_LIMIT:
        cut = text[:SOCIAL_SNIPPET_LIMIT]
        # nie ucinaj w środku słowa
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        text = cut.rstrip(" ,;:.") + "…"
    return f"{text}\n\nPełna treść u źródła: {source_url}"


class ApifyFacebookScraper(BaseScraper):
    """
    Scraper dla postów z Facebooka wykorzystujący Apify API.
    Actor: apify/facebook-posts-scraper

    KONFIGURACJA WYMAGANA:

    1. Załóż konto na Apify: https://apify.com
    2. Pobierz API token z: https://console.apify.com/account/integrations
    3. Wybierz Facebook Posts Scraper actor:
       https://apify.com/apify/facebook-posts-scraper

    4. Dodaj do .env (JEDYNE miejsce na token — do bazy NIE trafia):
       APIFY_API_KEY=apify_api_***********

    5. Utwórz source w bazie z konfiguracją — bez sekretu, same parametry:
       {
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

        # Sprawdź czy mamy wymagane klucze konfiguracji.
        #
        # Token bierzemy ze ŚRODOWISKA, nie z bazy (24.08.2026). Do tej pory leżał
        # jawnym tekstem w `sources.scraping_config` — w pięciu wierszach, ten sam —
        # więc wypływał przy każdym `select * from sources`, w zrzucie bazy i w każdym
        # podglądzie tabeli przez Adminera. Sekret ma jedno miejsce: `.env`.
        #
        # Odczyt z bazy zostaje jako zejście awaryjne, żeby wdrożenie kodu nie musiało
        # być zsynchronizowane co do minuty z migracją czyszczącą. Po przebiegu
        # `scripts.migrations.strip_apify_key_from_sources` ta gałąź nie ma już danych.
        self.apify_api_key = settings.APIFY_API_KEY or self.config.get('apify_api_key')
        self.facebook_page_url = self.config.get('facebook_page_url')
        self.results_limit = self.config.get('results_limit', 20)
        self.caption_text = self.config.get('caption_text', False)
        # UWAGA: Apify API wymaga ~ zamiast / w nazwie actora
        self.actor_id = self.config.get('actor_id', 'apify~facebook-posts-scraper')
        # Pobieraj tylko posty nowsze niż N dni (domyślnie 2 dni)
        self.only_newer_than_days = self.config.get('only_newer_than_days', 2)
        # Posty zawierające którekolwiek ze słów są pomijane (np. autoreklamy strony)
        self.exclude_keywords = [k.lower() for k in self.config.get('exclude_keywords', [])]

        if not self.apify_api_key:
            raise ValueError(
                "Brak tokenu Apify — ustaw APIFY_API_KEY w backend/.env "
                "(na produkcji: backend/.env.production, potem "
                "`docker compose -f docker-compose.prod.yml up -d --force-recreate backend`, "
                "bo samo `up -d` nie przeładowuje środowiska)"
            )
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
            # Data graniczna - pobieraj tylko posty nowsze niż N dni
            from datetime import timedelta
            since_date = (datetime.now() - timedelta(days=self.only_newer_than_days)).strftime("%Y-%m-%d")

            # Konfiguracja Apify actor run dla facebook-posts-scraper
            actor_input = {
                "startUrls": [{"url": self.facebook_page_url}],
                "resultsLimit": self.results_limit,
                "captionText": self.caption_text,
                "onlyPostsNewerThan": since_date,  # filtruj po dacie - brak duplikatów
            }
            self.logger.info(f"Fetching posts newer than: {since_date}")

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

                    if self.exclude_keywords:
                        text_lower = text.lower()
                        matched = next((k for k in self.exclude_keywords if k in text_lower), None)
                        if matched:
                            self.logger.info(f"Post {post_id} odfiltrowany (keyword: '{matched}')")
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

                    # Zdjęć z postów FB nie przechowujemy (wizerunek osób — RODO);
                    # image_url pozostaje None, oryginał dostępny pod linkiem posta.

                    # Data publikacji
                    published_at = None
                    timestamp = post.get('timestamp') or post.get('time') or post.get('createdTime')
                    if timestamp:
                        try:
                            # Apify zwraca Unix timestamp (integer)
                            if isinstance(timestamp, (int, float)):
                                published_at = datetime.fromtimestamp(timestamp)
                            # Lub ISO string
                            elif isinstance(timestamp, str):
                                published_at = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        except Exception as e:
                            self.logger.warning(f"Nieprawidłowy timestamp: {timestamp} ({type(timestamp)})")

                    # Model "pointer" (snippet + link) — prawo autorskie / RODO:
                    # nie przechowujemy pełnych tekstów cudzych postów ani zdjęć
                    # (wizerunek osób); pełna treść wyłącznie u źródła.
                    content = make_social_snippet(text, post_url)

                    article_data = {
                        'title': title,
                        'url': post_url,
                        'content': content,
                        'image_url': None,
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
