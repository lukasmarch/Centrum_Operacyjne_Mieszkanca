# Backend - Centrum Operacyjne Mieszkańca

## Setup Lokalne

```bash
# 1. Uruchom bazy danych
docker-compose up -d

# 2. Zainstaluj zależności
pip install -r requirements.txt

# 3. Skopiuj .env
cp .env.example .env
# Edytuj .env z prawdziwymi wartościami

# 4. Uruchom migracje
alembic upgrade head

# 5. Uruchom API
uvicorn src.api.main:app --reload
```

## Struktura

```
src/
├── scrapers/base.py      - BaseScraper (dziedzicz z tego)
├── database/schema.py    - SQLModel tables
├── models/               - Pydantic models (API)
├── api/main.py          - FastAPI endpoints
└── config.py            - Settings
```

## Tworzenie Nowego Scrapera

```python
from src.scrapers import BaseScraper

class MojScraper(BaseScraper):
    async def parse(self, html: str, url: str) -> List[Dict]:
        soup = BeautifulSoup(html, 'html.parser')
        # ... parsing logic
        return [{"title": "...", "url": "...", ...}]
```
