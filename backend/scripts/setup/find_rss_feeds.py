"""
Znajdź dostępne RSS feeds dla lokalnych portali
"""
import httpx
import feedparser

# Lista lokalnych portali
portals = [
    {"name": "Działdowo.pl", "base": "https://www.dzialdowo.pl"},
    {"name": "Moje Działdowo", "base": "https://mojedzialdowo.pl"},
    {"name": "Radio 7 Działdowo", "base": "https://radio7.pl"},
    {"name": "Gazeta Olsztyńska", "base": "https://gazetaolsztynska.pl"},
    {"name": "Klikaj.info", "base": "https://www.klikajinfo.pl"},
]

# Typowe ścieżki RSS
rss_paths = [
    "/rss",
    "/feed",
    "/rss.xml",
    "/feed.xml",
    "/index.xml",
    "/atom.xml",
    "/?feed=rss",
    "/?feed=rss2",
    "/category/dzialdowo/feed/",  # dla Radio 7
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/rss+xml, application/xml, text/xml, */*'
}

print("=" * 70)
print("SZUKANIE RSS FEEDS DLA LOKALNYCH PORTALI DZIAŁDOWO")
print("=" * 70)

working_feeds = []

for portal in portals:
    print(f"\n{portal['name']} ({portal['base']}):")
    print("-" * 70)

    for path in rss_paths:
        url = portal['base'] + path
        try:
            response = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)

            if response.status_code == 200:
                # Sprawdź czy to RSS
                if 'xml' in response.headers.get('content-type', '').lower() or \
                   '<rss' in response.text[:500].lower() or \
                   '<feed' in response.text[:500].lower():

                    # Spróbuj sparsować
                    feed = feedparser.parse(response.text)
                    if feed.entries:
                        print(f"  ✅ {url}")
                        print(f"     Tytuł: {feed.feed.get('title', 'N/A')}")
                        print(f"     Wpisów: {len(feed.entries)}")
                        if feed.entries:
                            print(f"     Pierwszy: {feed.entries[0].get('title', 'N/A')[:60]}...")

                        working_feeds.append({
                            'name': portal['name'],
                            'url': url,
                            'title': feed.feed.get('title', ''),
                            'entries': len(feed.entries)
                        })
                        break  # Znaleziono working feed, przejdź do następnego portalu

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                print(f"  ⚠️  {url} - Cloudflare/403")
        except Exception:
            pass  # Ignoruj inne błędy

print("\n" + "=" * 70)
print("PODSUMOWANIE - DZIAŁAJĄCE RSS FEEDS:")
print("=" * 70)

if working_feeds:
    for feed in working_feeds:
        print(f"\n✅ {feed['name']}")
        print(f"   URL: {feed['url']}")
        print(f"   Tytuł: {feed['title']}")
        print(f"   Wpisów: {feed['entries']}")
else:
    print("\n❌ Nie znaleziono dostępnych RSS feeds")
    print("\nAlternatywy:")
    print("1. Użyć HTML scraperów (jak już mamy)")
    print("2. Użyć cloudscraper do omijania Cloudflare")
    print("3. Użyć API Apify dla Facebook")
