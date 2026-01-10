# Nowe Scrapery - Dokumentacja

## Przegląd

Dodano 3 nowe scrapery do projektu Centrum Operacyjne Mieszkańca:

1. **GminaRybnoScraper** - oficjalny portal Gminy Rybno
2. **MojeDzialdowoScraper** - portal informacyjny Działdowa
3. **ApifyFacebookScraper** - posty z Facebooka przez Apify API

---

## 1. GminaRybnoScraper

### Źródło
- **URL**: https://gminarybno.pl/aktualnosci.html
- **Typ**: Urząd miejski
- **Format**: HTML scraping

### Implementacja

```python
from src.scrapers import GminaRybnoScraper

scraper = GminaRybnoScraper(source_id=1)
async with scraper:
    articles = await scraper.scrape(
        ["https://gminarybno.pl/aktualnosci.html"],
        session
    )
```

### Struktura HTML

Scraper rozpoznaje następujące struktury:
- `<article>` tags
- `<div class="aktualn*|news*|post*">`
- Linki: `/aktualnosc/[id]/[slug]`

### Ekstrakcja danych

- **Tytuł**: `<h2>`, `<h3>`, lub atrybut `title` linku
- **URL**: względny link konwertowany do absolutnego
- **Obrazek**: `<img src>` lub `data-src`
- **External ID**: regex z URL (format: `/aktualnosc/123/`)

### Konfiguracja

```json
{
  "scraper_class": "GminaRybnoScraper",
  "rate_limit": 0.5,
  "user_agent": "Mozilla/5.0 (compatible; CentrumOperacyjneMieszkanca/1.0)"
}
```

---

## 2. MojeDzialdowoScraper

### Źródło
- **URL**: https://mojedzialdowo.pl
- **Typ**: Media lokalne
- **Format**: HTML scraping

### Implementacja

```python
from src.scrapers import MojeDzialdowoScraper

scraper = MojeDzialdowoScraper(source_id=2)
async with scraper:
    articles = await scraper.scrape(
        ["https://mojedzialdowo.pl"],
        session
    )
```

### Struktura HTML

Scraper obsługuje:
- `<article>` tags (HTML5)
- `<div class="article*|post*|news*">`
- Linki: `/artykul/[id]/[slug]`, `/wiadomosc/[id]`
- WordPress style: `?p=[id]`

### Ekstrakcja danych

- **Tytuł**: nagłówki `<h1>`-`<h5>`, klasy `.title`, `.headline`
- **URL**: względny/absolutny, ignoruje kategorie/tagi
- **Obrazek**: `<img src|data-src|data-lazy-src>`
- **Content**: excerpt/summary (max 500 znaków)
- **External ID**: regex z URL lub hash

### Filtrowanie

Ignoruje linki do:
- `/kategoria/`
- `/tag/`
- `/komentarz/`
- `/autor/`
- `#` (anchors)

### Konfiguracja

```json
{
  "scraper_class": "MojeDzialdowoScraper",
  "rate_limit": 0.5,
  "user_agent": "Mozilla/5.0 (compatible; CentrumOperacyjneMieszkanca/1.0)"
}
```

---

## 3. ApifyFacebookScraper

### Źródło
- **URL**: https://facebook.com/[page]
- **Typ**: Social Media
- **Format**: Apify API (JSON)

### Wymagania

1. **Konto Apify**: https://apify.com
2. **API Token**: https://console.apify.com/account/integrations
3. **Actor**: `apify/facebook-pages-scraper`

### Implementacja

```python
from src.scrapers import ApifyFacebookScraper

config = {
    "apify_api_key": "apify_api_***********",
    "facebook_page_url": "https://facebook.com/GminaDzialdowo",
    "max_posts": 20,
    "actor_id": "apify/facebook-pages-scraper"
}

scraper = ApifyFacebookScraper(source_id=3, config=config)
async with scraper:
    articles = await scraper.scrape(
        ["https://facebook.com/GminaDzialdowo"],
        session
    )
```

### Workflow

1. **Uruchom Apify actor** - POST `/v2/acts/{actorId}/runs`
2. **Polling status** - co 5s sprawdza czy zakończony (max 5 minut)
3. **Pobierz dataset** - GET `/v2/actor-runs/{runId}/dataset/items`
4. **Parse JSON** - konwersja do Article format

### JSON Response (Apify)

```json
[
  {
    "postId": "123456789",
    "text": "Treść posta...",
    "url": "https://facebook.com/...",
    "timestamp": "2026-01-10T12:00:00Z",
    "imageUrl": "https://...",
    "likes": 42,
    "comments": 5,
    "shares": 2
  }
]
```

### Ekstrakcja danych

- **Tytuł**: pierwsze 100 znaków tekstu lub pierwsze zdanie
- **URL**: `url` z API lub fallback `facebook.com/{postId}`
- **Content**: pełny tekst + metadata (likes/comments/shares)
- **Obrazek**: `imageUrl` z API
- **External ID**: `fb_{postId}`
- **Published At**: timestamp z ISO format

### Koszty (Apify)

- **Pricing**: ~$0.25 za 1000 postów
- **Rate Limit**: zgodnie z planem Apify
- **Free Tier**: $5 credits/miesiąc

### Konfiguracja w bazie

```json
{
  "scraper_class": "ApifyFacebookScraper",
  "apify_api_key": "UZUPEŁNIJ_TOKEN",
  "facebook_page_url": "https://facebook.com/GminaDzialdowo",
  "max_posts": 20,
  "actor_id": "apify/facebook-pages-scraper"
}
```

**UWAGA**: Status źródła powinien być `inactive` dopóki nie skonfigurujesz prawdziwego API key.

---

## Testing

### Uruchom testy wszystkich scraperów

```bash
cd backend
python scripts/test_new_scrapers.py
```

Testy obejmują:
- ✓ GminaRybnoScraper - live scraping
- ✓ MojeDzialdowoScraper - live scraping
- ✓ ApifyFacebookScraper - mock test (bez API)

### Oczekiwany output

```
TEST: GminaRybnoScraper
Pobrano HTML: 45123 znaków
Sparsowano 15 artykułów

TEST: MojeDzialdowoScraper
Pobrano HTML: 87456 znaków
Sparsowano 20 artykułów

TEST: ApifyFacebookScraper (MOCK)
Sparsowano 2 postów z mock JSON

PODSUMOWANIE:
- GminaRybnoScraper: 15 artykułów
- MojeDzialdowoScraper: 20 artykułów
- ApifyFacebookScraper: 2 posty
SUCCESS: Łącznie 37 artykułów/postów
```

---

## Inicjalizacja w bazie danych

### Dodaj źródła do DB

```bash
cd backend
python scripts/init_new_sources.py
```

To stworzy 3 nowe wpisy w tabeli `sources`:

1. **Gmina Rybno** - status: `active`
2. **Moje Działdowo** - status: `active`
3. **Gmina Działdowo Facebook** - status: `inactive` (wymaga config)

### Sprawdź w bazie

```sql
SELECT id, name, type, status, url
FROM sources
ORDER BY id;
```

---

## Integracja ze schedulerem

### Dodaj do article_job.py

```python
from src.scrapers import (
    KlikajInfoScraper,
    GminaRybnoScraper,
    MojeDzialdowoScraper,
    ApifyFacebookScraper
)

SCRAPER_REGISTRY = {
    "KlikajInfoScraper": KlikajInfoScraper,
    "GminaRybnoScraper": GminaRybnoScraper,
    "MojeDzialdowoScraper": MojeDzialdowoScraper,
    "ApifyFacebookScraper": ApifyFacebookScraper,
}

async def scrape_articles_job():
    async with get_session() as session:
        statement = select(Source).where(Source.status == "active")
        result = await session.execute(statement)
        sources = result.scalars().all()

        for source in sources:
            scraper_class_name = source.scraping_config.get("scraper_class")
            scraper_class = SCRAPER_REGISTRY.get(scraper_class_name)

            if not scraper_class:
                logger.warning(f"Unknown scraper: {scraper_class_name}")
                continue

            scraper = scraper_class(source.id, source.scraping_config)
            async with scraper:
                saved_ids = await scraper.scrape([source.url], session)
                logger.info(f"{source.name}: saved {len(saved_ids)} articles")
```

---

## Architektura

### Dziedziczenie

```
BaseScraper (abstract)
    ├── KlikajInfoScraper
    ├── GminaRybnoScraper
    ├── MojeDzialdowoScraper
    └── ApifyFacebookScraper
```

### Metody wymagane

Każdy scraper **MUSI** zaimplementować:

```python
async def parse(self, html: str, url: str) -> List[Dict]:
    """
    Args:
        html: HTML content (lub JSON dla API scraperów)
        url: Source URL

    Returns:
        List[Dict] zgodny z Article model:
        {
            "title": str,           # REQUIRED
            "url": str,            # REQUIRED (unique)
            "content": str,        # optional
            "image_url": str,      # optional
            "author": str,         # optional
            "published_at": datetime,  # optional
            "external_id": str     # optional (recommended)
        }
    """
```

### Metody opcjonalne (override)

```python
async def fetch(self, url: str) -> str:
    """Override dla API scraperów (jak Apify)"""

async def scrape(self, urls: List[str], session) -> List[int]:
    """Override dla niestandardowych workflows"""
```

---

## Best Practices

### 1. Deduplikacja URL

```python
seen_urls = set()
for container in containers:
    url = container.find('a')['href']
    if url in seen_urls:
        continue
    seen_urls.add(url)
```

### 2. External ID

Zawsze próbuj wyekstrahować ID z URL:

```python
# Preferuj regex
id_match = re.search(r'/artykul/(\d+)/', href)
external_id = id_match.group(1) if id_match else None

# Fallback: hash URL
if not external_id:
    external_id = f"source_{hash(url) & 0x7FFFFFFF}"
```

### 3. Robust parsing

```python
try:
    # Multiple strategies dla tytułu
    title = link.get('title') or \
            link.find('h2').get_text() or \
            link.get_text(strip=True)
except (AttributeError, KeyError):
    logger.warning(f"No title for {url}")
    continue
```

### 4. Rate limiting

```python
# BaseScraper automatycznie dodaje delay między requestami
delay = 1.0 / self.rate_limit  # np. 0.5 req/s = 2s delay
await asyncio.sleep(delay)
```

### 5. Error handling

```python
try:
    articles.append(article_data)
except (AttributeError, KeyError, TypeError) as e:
    self.logger.warning(f"Parse error: {e}")
    continue  # nie przerywaj całego scraping
```

---

## Troubleshooting

### Problem: "No articles found"

**Przyczyny**:
- Zmieniła się struktura HTML strony
- Niewłaściwe selektory CSS/regex
- Strona wymaga JavaScript (użyj Playwright)

**Rozwiązanie**:
1. Sprawdź HTML ręcznie: `curl https://example.com | less`
2. Zaktualizuj selektory w metodzie `parse()`
3. Dodaj debug logging: `self.logger.debug(f"Found {len(containers)} containers")`

### Problem: "Rate limited (429)"

**Przyczyny**:
- Za wysoki `rate_limit` w config
- Strona ma aggressive rate limiting

**Rozwiązanie**:
1. Zmniejsz `rate_limit` (np. z 1.0 do 0.2)
2. Dodaj `User-Agent` w config
3. BaseScraper automatycznie retry z exponential backoff

### Problem: "Duplicate URL error"

**Przyczyny**:
- Artykuł już istnieje w bazie
- Brak deduplikacji w parse()

**Rozwiązanie**:
- To normalne - BaseScraper sprawdza `Article.url` przed zapisem
- Dodaj `seen_urls` set w parse() dla wydajności

### Problem: Apify "Actor run failed"

**Przyczyny**:
- Niewłaściwy API key
- Facebook zablokował scraping
- Timeout (actor >5 minut)

**Rozwiązanie**:
1. Sprawdź API key w Apify console
2. Użyj webhooks zamiast pollingu
3. Zwiększ `max_wait` w `fetch()`

---

## Roadmap

### Następne scrapery (Faza 2)

- [ ] **BIPRybnoScraper** - ogłoszenia urzędowe BIP
- [ ] **GminaDzialdowoScraper** - oficjalny portal
- [ ] **DzialdowskieInfoScraper** - lokalne media
- [ ] **GazetaDzialdowskaScraper** - gazeta lokalna

### Ulepszenia (Faza 3)

- [ ] Scraper Registry pattern z auto-discovery
- [ ] Full article content scraping (nie tylko listy)
- [ ] Image download + local storage
- [ ] Playwright integration dla JS-heavy sites
- [ ] Webhooks dla Apify (zamiast pollingu)

---

## Kontakt

Pytania? Zobacz:
- **BaseScraper**: `/backend/src/scrapers/base.py`
- **Database Schema**: `/backend/src/database/schema.py`
- **CLAUDE.md**: Plan projektu i status

---

**Utworzono**: 2026-01-10
**Autor**: Claude Code
**Projekt**: Centrum Operacyjne Mieszkańca
