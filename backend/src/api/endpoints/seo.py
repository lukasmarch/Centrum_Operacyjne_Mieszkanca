"""
SEO — sitemap.xml dla rybnolive.pl.

Serwowana przez backend, bo lista tras i daty świeżości żyją tu, nie w bundlu
frontendu. Na domenie głównej wystawia ją Caddy (blok rybnolive.pl proxuje
/sitemap.xml do backendu) — plik NIE może lecieć z SPA-fallbacku, bo wtedy
Google dostaje HTML aplikacji zamiast XML-a.

Sitemapa wymienia WYŁĄCZNIE adresy, które SPA naprawdę obsługuje
(SECTION_TO_PATH w frontend/App.tsx). Wpis o nieistniejącej stronie jest
gorszy niż brak wpisu: crawler dostaje na nim SPA-fallback z cudzym tytułem
i uczy się, że sitemapa kłamie. Stąd brak adresów per artykuł — feed nie ma
stron szczegółu, wpisy linkują do źródeł.
"""
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session

router = APIRouter(tags=["seo"])

BASE_URL = "https://rybnolive.pl"

# Ścieżki muszą być lustrem SECTION_TO_PATH z frontend/App.tsx — rozjazd
# oznacza wpisy prowadzące na dashboard z ogólnym tytułem.
#
# ⚠️ Lista jest krótka CELOWO i odpowiada frontowi, który stoi na produkcji.
# Adresy `/wiadomosci`, `/wydarzenia`, `/pogoda`, `/statystyki`, `/firmy`,
# `/asystent`, `/harmonogram-odpadow` i `/autobus` istnieją dopiero w przebudowie
# strony głównej (commit c9d18cf), która czeka na akceptację i NIE jest wdrożona.
# Dopisanie ich tutaj wcześniej robi dokładnie to, przed czym ostrzega nagłówek
# tego pliku: crawler dostaje SPA-fallback z cudzym tytułem i uczy się, że
# sitemapa kłamie. Przy wdrażaniu przebudowy przywrócić je RAZEM z frontem.
STATIC_PAGES = [
    {"loc": "/",                      "priority": "1.0", "changefreq": "hourly"},
    {"loc": "/cennik",                "priority": "0.5", "changefreq": "monthly"},
    {"loc": "/zgloszenia",            "priority": "0.5", "changefreq": "weekly"},
    {"loc": "/regulamin",             "priority": "0.3", "changefreq": "yearly"},
    {"loc": "/polityka-prywatnosci",  "priority": "0.3", "changefreq": "yearly"},
    {"loc": "/polityka-cookies",      "priority": "0.3", "changefreq": "yearly"},
]

# Strony aktualizowane wraz z treścią serwisu — dostają lastmod z najnowszego
# artykułu, żeby crawler widział, że jest po co wracać.
CONTENT_PATHS = {"/", "/wiadomosci", "/wydarzenia"}  # /wiadomosci, /wydarzenia — po wdrożeniu przebudowy


@router.get("/sitemap.xml", response_class=Response)
async def sitemap(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        text("""
            SELECT COALESCE(MAX(COALESCE(published_at, scraped_at)), NOW())
            FROM articles
            WHERE processed = true
        """)
    )
    newest = result.scalar() or datetime.utcnow()
    content_lastmod = newest.strftime("%Y-%m-%d")

    urls: list[str] = []
    for page in STATIC_PAGES:
        lines = [f"    <loc>{BASE_URL}{page['loc'].rstrip('/') or '/'}</loc>"]
        if page["loc"] in CONTENT_PATHS:
            lines.append(f"    <lastmod>{content_lastmod}</lastmod>")
        lines.append(f"    <changefreq>{page['changefreq']}</changefreq>")
        lines.append(f"    <priority>{page['priority']}</priority>")
        urls.append("  <url>\n" + "\n".join(lines) + "\n  </url>")

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )
    return Response(content=xml, media_type="application/xml")
