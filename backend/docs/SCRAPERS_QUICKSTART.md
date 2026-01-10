# Scrapery - Quick Start Guide

## Szybki Start

### 1. Przetestuj nowe scrapery

```bash
cd backend
python scripts/test_new_scrapers.py
```

**Oczekiwany output:**
```
✓ GminaRybnoScraper: 30 artykułów
✓ MojeDzialdowoScraper: 1 artykułów
✓ ApifyFacebookScraper (mock): 2 postów
SUCCESS: Łącznie 33 artykułów/postów
```

### 2. Dodaj źródła do bazy danych

```bash
cd backend
python scripts/init_new_sources.py
```

To utworzy 3 nowe źródła:
- Gmina Rybno (aktywny)
- Moje Działdowo (aktywny)
- Facebook/Apify (nieaktywny - wymaga konfiguracji)

### 3. Sprawdź źródła w bazie

```sql
SELECT id, name, type, status, url
FROM sources
ORDER BY id;
```

### 4. Uruchom scraping ręcznie (test)

```python
import asyncio
from src.database.connection import get_session
from src.scrapers import GminaRybnoScraper

async def test():
    scraper = GminaRybnoScraper(source_id=2)  # ID z bazy
    async with scraper, get_session() as session:
        saved = await scraper.scrape(
            ["https://gminarybno.pl/aktualnosci.html"],
            session
        )
        print(f"Zapisano {len(saved)} artykułów")

asyncio.run(test())
```

---

## Dostępne Scrapery

### 1. KlikajInfoScraper
- **Status**: Działa (31 artykułów w bazie)
- **URL**: https://klikajinfo.pl
- **Częstotliwość**: co 6h

### 2. GminaRybnoScraper (NOWY)
- **Status**: Gotowy do użycia
- **URL**: https://gminarybno.pl/aktualnosci.html
- **Wykrywanie**: ~30 artykułów
- **Ekstrakcja**: title, url, image_url, external_id

### 3. MojeDzialdowoScraper (NOWY)
- **Status**: Gotowy do użycia
- **URL**: https://mojedzialdowo.pl
- **Ekstrakcja**: title, url, image_url, content (excerpt), external_id

### 4. ApifyFacebookScraper (NOWY)
- **Status**: Wymaga konfiguracji Apify API
- **URL**: Facebook pages
- **Koszty**: ~$0.25 za 1000 postów

---

## Integracja z Schedulerem

### Opcja A: Ręczna integracja

Edytuj `/backend/src/scheduler/article_job.py`:

```python
from src.scrapers import (
    KlikajInfoScraper,
    GminaRybnoScraper,
    MojeDzialdowoScraper,
)

# Dodaj do słownika:
SCRAPER_REGISTRY = {
    "KlikajInfoScraper": KlikajInfoScraper,
    "GminaRybnoScraper": GminaRybnoScraper,
    "MojeDzialdowoScraper": MojeDzialdowoScraper,
}
```

### Opcja B: Auto-discovery (TODO)

W przyszłości: automatyczne wykrywanie scraperów przez registry pattern.

---

## Konfiguracja Apify (Facebook)

### Wymagane kroki:

1. **Załóż konto Apify**
   - https://apify.com

2. **Pobierz API Token**
   - https://console.apify.com/account/integrations

3. **Dodaj do .env**
   ```bash
   APIFY_API_KEY=apify_api_***********
   ```

4. **Zaktualizuj źródło w bazie**
   ```sql
   UPDATE sources
   SET
     scraping_config = jsonb_set(
       scraping_config,
       '{apify_api_key}',
       '"apify_api_***"'
     ),
     status = 'active'
   WHERE name = 'Gmina Działdowo Facebook';
   ```

5. **Test scraper**
   ```bash
   python scripts/test_apify.py  # TODO: create this
   ```

---

## Troubleshooting

### "No articles found"

**Rozwiązanie:**
1. Sprawdź HTML: `curl https://gminarybno.pl/aktualnosci.html | less`
2. Dodaj debug logging w metodzie `parse()`
3. Zweryfikuj selektory CSS/regex

### "Rate limited (429)"

**Rozwiązanie:**
1. Zmniejsz `rate_limit` w config (np. 0.2 zamiast 0.5)
2. BaseScraper automatycznie retry z backoff

### "Duplicate URL error"

**To normalne!** BaseScraper sprawdza duplikaty przed zapisem.

---

## Następne Kroki

### Dodaj więcej scraperów:

1. **BIPRybnoScraper** - ogłoszenia BIP
2. **GminaDzialdowoScraper** - urząd miejski
3. **DzialdowskieInfoScraper** - media

### Szablon nowego scrapera:

```python
from src.scrapers.base import BaseScraper
from bs4 import BeautifulSoup
import re

class NewScraper(BaseScraper):
    async def parse(self, html: str, url: str) -> List[Dict]:
        soup = BeautifulSoup(html, 'html.parser')
        articles = []
        seen_urls = set()

        # Find containers
        containers = soup.find_all('article')

        for container in containers:
            try:
                # Extract data
                link = container.find('a')
                title = link.get_text(strip=True)
                href = link['href']

                # Build article
                article = {
                    'title': title,
                    'url': f"https://example.com{href}",
                    'external_id': re.search(r'/(\d+)/', href).group(1)
                }
                articles.append(article)
            except Exception as e:
                self.logger.warning(f"Parse error: {e}")
                continue

        return articles
```

---

## Dokumentacja

- **Pełna dokumentacja**: `/backend/docs/NEW_SCRAPERS.md`
- **BaseScraper**: `/backend/src/scrapers/base.py`
- **Database Schema**: `/backend/src/database/schema.py`
- **Plan projektu**: `/CLAUDE.md`

---

**Utworzono**: 2026-01-10
**Wersja**: 1.0
