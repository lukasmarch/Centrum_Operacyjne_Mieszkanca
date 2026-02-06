import os
from firecrawl import FirecrawlApp

class FirecrawlClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        if not self.api_key:
            raise ValueError("API key must be provided or set in FIRECRAWL_API_KEY environment variable")
        
        self.app = FirecrawlApp(api_key=self.api_key)

    def scrape_url(self, url, params=None):
        """
        Scrapes a single URL.
        :param url: The URL to scrape.
        :param params: Optional dictionary of parameters for the scrape request.
        :return: The scraped data.
        """
        try:
            print(f"Scraping URL: {url}")
            # Try newer SDK method first (flattened kwargs)
            if params:
                return self.app.scrape(url, **params)
            else:
                return self.app.scrape(url)
        except AttributeError:
             # Fallback for older SDK versions (nested params dict)
             print(f"Scraping URL (legacy): {url}")
             return self.app.scrape_url(url, params=params)
        except Exception as e:
            print(f"Error scraping URL {url}: {e}")
            raise

    def crawl_url(self, url, limit=20, scrape_options=None, poll_interval=30):
        """
        Crawls a URL and all linked pages.
        :param url: The starting URL to crawl.
        :param limit: Maximum number of pages to crawl.
        :param scrape_options: Optional ScrapeOptions object.
        :param poll_interval: Polling interval in seconds.
        :return: The crawl status/results with list of Document objects.
        """
        try:
            print(f"Starting crawl for URL: {url} (limit={limit})")
            # New SDK uses `crawl` with keyword arguments
            crawl_result = self.app.crawl(
                url=url,
                limit=limit,
                scrape_options=scrape_options,
                poll_interval=poll_interval
            )
            return crawl_result
        except TypeError:
            # Fallback if SDK version doesn't support these kwargs
            print(f"Crawling URL (legacy mode): {url}")
            params = {'limit': limit}
            if scrape_options:
                params['scrape_options'] = scrape_options
            try:
                return self.app.crawl_url(url, params=params)
            except AttributeError:
                return self.app.crawl(url, params=params)
        except Exception as e:
            print(f"Error crawling URL {url}: {e}")
            raise

