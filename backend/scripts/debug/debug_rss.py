"""Debug RSS feed"""
import feedparser
import httpx

url = "https://dzialdowo.naszemiasto.pl/rss/"

print(f"Testing: {url}\n")

# 1. Fetch raw XML
print("=" * 60)
print("1. Fetching raw XML...")
print("=" * 60)
response = httpx.get(url, follow_redirects=True, timeout=30)
print(f"Status: {response.status_code}")
print(f"Content-Type: {response.headers.get('content-type')}")
print(f"Length: {len(response.text)} characters")
print(f"\nFirst 500 chars:")
print(response.text[:500])

# 2. Parse with feedparser
print("\n" + "=" * 60)
print("2. Parsing with feedparser...")
print("=" * 60)
feed = feedparser.parse(url)

print(f"Bozo (errors): {feed.bozo}")
if feed.bozo:
    print(f"Bozo exception: {feed.bozo_exception}")

print(f"Feed title: {feed.feed.get('title', 'N/A')}")
print(f"Feed link: {feed.feed.get('link', 'N/A')}")
print(f"Entries found: {len(feed.entries)}")

if feed.entries:
    print(f"\nFirst entry:")
    entry = feed.entries[0]
    print(f"  Title: {entry.get('title', 'N/A')}")
    print(f"  Link: {entry.get('link', 'N/A')}")
    print(f"  Published: {entry.get('published', 'N/A')}")
else:
    print("\n⚠️  NO ENTRIES - This is the problem!")

# 3. Try parsing from string with sanitization
print("\n" + "=" * 60)
print("3. Trying with HTML entity fixes...")
print("=" * 60)

# Replace common problematic entities
xml_content = response.text
# Feedparser usually handles this, but let's try
import html
xml_sanitized = html.unescape(xml_content)

feed2 = feedparser.parse(xml_sanitized)
print(f"Bozo: {feed2.bozo}")
print(f"Entries: {len(feed2.entries)}")
