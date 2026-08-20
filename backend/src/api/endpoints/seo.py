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
# 20.08.2026: przebudowa strony głównej JEST na produkcji, więc lista wraca do
# pełnej. Od 12.08 stało tu sześć adresów, bo pozostałe trasy nie istniały jeszcze
# w SPA — wpis o stronie, której front nie obsługuje, daje crawlerowi SPA-fallback
# z cudzym tytułem i uczy go, że sitemapa kłamie.
#
# Warunek przywrócenia był jeden i jest spełniony: każdy adres z tej listy ma
# własny wpis w `frontend/src/data/seoMeta.json`, czyli po `npm run build` dostaje
# statyczny `title`, `description` i `canonical` (`scripts/prerender-meta.mjs`).
# Sprawdzenie po deployu: `curl -s https://rybnolive.pl/<trasa> | grep '<title>'`
# musi zwrócić tytuł tej trasy, nie strony głównej.
#
# `/profil` i `/zamowienie` zostają POZA sitemapą celowo — robots.txt ich zabrania:
# jedno wymaga logowania, drugie jest krokiem zakupu bez samodzielnej treści.
STATIC_PAGES = [
    {"loc": "/",                      "priority": "1.0", "changefreq": "hourly"},
    {"loc": "/wiadomosci",            "priority": "0.9", "changefreq": "hourly"},
    # Dwie strony evergreen — odpowiadają na najczęstsze pytania w gminie
    # i na frazy bez konkurencji („harmonogram wywozu odpadów Rybno")
    {"loc": "/harmonogram-odpadow",   "priority": "0.9", "changefreq": "monthly"},
    {"loc": "/autobus",               "priority": "0.8", "changefreq": "monthly"},
    {"loc": "/wydarzenia",            "priority": "0.8", "changefreq": "daily"},
    {"loc": "/asystent",              "priority": "0.7", "changefreq": "monthly"},
    # Repertuar zmienia się co tydzień, ale adres jest stały — dla kogoś, kto
    # szuka „kino Działdowo repertuar", to jedyna strona z gminy w wynikach
    {"loc": "/kino",                  "priority": "0.7", "changefreq": "daily"},
    {"loc": "/pogoda",                "priority": "0.6", "changefreq": "hourly"},
    {"loc": "/statystyki",            "priority": "0.6", "changefreq": "monthly"},
    {"loc": "/firmy",                 "priority": "0.6", "changefreq": "weekly"},
    {"loc": "/cennik",                "priority": "0.5", "changefreq": "monthly"},
    {"loc": "/zgloszenia",            "priority": "0.5", "changefreq": "weekly"},
    {"loc": "/regulamin",             "priority": "0.3", "changefreq": "yearly"},
    {"loc": "/polityka-prywatnosci",  "priority": "0.3", "changefreq": "yearly"},
    {"loc": "/polityka-cookies",      "priority": "0.3", "changefreq": "yearly"},
]

# Strony aktualizowane wraz z treścią serwisu — dostają lastmod z najnowszego
# artykułu, żeby crawler widział, że jest po co wracać.
CONTENT_PATHS = {"/", "/wiadomosci", "/wydarzenia"}


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
