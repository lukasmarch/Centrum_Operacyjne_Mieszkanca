"""
Test Gazeta Olsztyńska RSS - diagnoza problemu encoding
"""
import feedparser
import httpx

url = "https://gazetaolsztynska.pl/rss"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/rss+xml, application/xml, text/xml, */*'
}

print("=" * 80)
print("TEST: Gazeta Olsztyńska RSS Feed")
print("=" * 80)

# TEST 1: Bezpośrednio przez feedparser (obecne rozwiązanie)
print("\n1️⃣ TEST: feedparser.parse(url) - OBECNE ROZWIĄZANIE")
print("-" * 80)
try:
    feed1 = feedparser.parse(url, agent=headers['User-Agent'])
    print(f"✓ Feed pobrany")
    print(f"  - Bozo: {feed1.bozo}")
    if feed1.bozo:
        print(f"  - Bozo exception: {feed1.bozo_exception}")
    print(f"  - Feed title: {feed1.feed.get('title', 'N/A')}")
    print(f"  - Entries: {len(feed1.entries)}")
    if feed1.entries:
        print(f"  - Pierwszy wpis: {feed1.entries[0].get('title', 'N/A')[:80]}")
except Exception as e:
    print(f"✗ Błąd: {e}")

# TEST 2: Pobrać jako TEXT, potem feedparser (stare podejście)
print("\n2️⃣ TEST: httpx + response.text + feedparser - STARE PODEJŚCIE")
print("-" * 80)
try:
    response = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
    print(f"✓ Response status: {response.status_code}")
    print(f"  - Content-Type: {response.headers.get('content-type', 'N/A')}")
    print(f"  - Encoding (detected): {response.encoding}")

    feed2 = feedparser.parse(response.text)
    print(f"✓ Feed sparsowany z response.text")
    print(f"  - Bozo: {feed2.bozo}")
    if feed2.bozo:
        print(f"  - Bozo exception: {feed2.bozo_exception}")
    print(f"  - Feed title: {feed2.feed.get('title', 'N/A')}")
    print(f"  - Entries: {len(feed2.entries)}")
    if feed2.entries:
        print(f"  - Pierwszy wpis: {feed2.entries[0].get('title', 'N/A')[:80]}")
except Exception as e:
    print(f"✗ Błąd: {e}")

# TEST 3: Pobrać jako BYTES, potem feedparser (NOWE ROZWIĄZANIE)
print("\n3️⃣ TEST: httpx + response.content (bytes) + feedparser - NOWE ROZWIĄZANIE")
print("-" * 80)
try:
    response = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
    print(f"✓ Response status: {response.status_code}")
    print(f"  - Content-Type: {response.headers.get('content-type', 'N/A')}")

    # Użyj response.content (bytes) zamiast response.text
    feed3 = feedparser.parse(response.content)
    print(f"✓ Feed sparsowany z response.content (bytes)")
    print(f"  - Bozo: {feed3.bozo}")
    if feed3.bozo:
        print(f"  - Bozo exception: {feed3.bozo_exception}")
    print(f"  - Feed title: {feed3.feed.get('title', 'N/A')}")
    print(f"  - Entries: {len(feed3.entries)}")
    if feed3.entries:
        print(f"  - Pierwszy wpis: {feed3.entries[0].get('title', 'N/A')[:80]}")
        print(f"\n  📰 PRZYKŁADOWY ARTYKUŁ:")
        print(f"     Tytuł: {feed3.entries[0].get('title', 'N/A')}")
        print(f"     Link: {feed3.entries[0].get('link', 'N/A')}")
        print(f"     Data: {feed3.entries[0].get('published', 'N/A')}")
        summary = feed3.entries[0].get('summary', '')[:200]
        print(f"     Summary: {summary}...")
except Exception as e:
    print(f"✗ Błąd: {e}")

print("\n" + "=" * 80)
print("PODSUMOWANIE:")
print("=" * 80)
print("Która metoda działa najlepiej?")
print("- Metoda 1 (feedparser bezpośrednio): ???")
print("- Metoda 2 (response.text): ???")
print("- Metoda 3 (response.content bytes): ??? ← OCZEKIWANE ROZWIĄZANIE")
