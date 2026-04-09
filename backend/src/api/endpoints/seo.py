"""
SEO endpoints — sitemap.xml auto-generated from articles.
Google fetches /sitemap.xml to discover content URLs.
"""
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import Response
from sqlalchemy import text

from src.database import get_session
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["seo"])

BASE_URL = "https://rybno.pl"

STATIC_PAGES = [
    {"loc": f"{BASE_URL}/",         "priority": "1.0", "changefreq": "daily"},
    {"loc": f"{BASE_URL}/news",     "priority": "0.9", "changefreq": "hourly"},
    {"loc": f"{BASE_URL}/events",   "priority": "0.7", "changefreq": "daily"},
    {"loc": f"{BASE_URL}/weather",  "priority": "0.5", "changefreq": "hourly"},
    {"loc": f"{BASE_URL}/stats",    "priority": "0.6", "changefreq": "monthly"},
    {"loc": f"{BASE_URL}/business", "priority": "0.5", "changefreq": "weekly"},
]


@router.get("/sitemap.xml", response_class=Response)
async def sitemap(session: AsyncSession = Depends(get_session)):
    """
    Auto-generated XML sitemap with all published articles.
    Standard location: /sitemap.xml (no /api/ prefix).
    """
    result = await session.execute(
        text("""
            SELECT id, title, published_at, scraped_at
            FROM articles
            WHERE processed = true
            ORDER BY COALESCE(published_at, scraped_at) DESC
            LIMIT 2000
        """)
    )
    rows = result.fetchall()

    urls: list[str] = []

    # Static pages
    for page in STATIC_PAGES:
        urls.append(
            f"  <url>\n"
            f"    <loc>{page['loc']}</loc>\n"
            f"    <changefreq>{page['changefreq']}</changefreq>\n"
            f"    <priority>{page['priority']}</priority>\n"
            f"  </url>"
        )

    # Article pages
    for row in rows:
        article_id, title, published_at, scraped_at = row
        lastmod_dt = published_at or scraped_at or datetime.utcnow()
        lastmod = lastmod_dt.strftime("%Y-%m-%d")
        loc = f"{BASE_URL}/artykul/{article_id}"
        urls.append(
            f"  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>never</changefreq>\n"
            f"    <priority>0.6</priority>\n"
            f"  </url>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )

    return Response(content=xml, media_type="application/xml")
