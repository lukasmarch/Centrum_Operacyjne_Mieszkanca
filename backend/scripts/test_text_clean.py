"""
Tekst z RSS bez encji HTML i stopki WordPressa (audyt 11.10.2026, F-040).

Bez bazy — w CI. Przypadki wzięte z prawdziwych wpisów Radia 7 (6570, 6571)
i Radia Olsztyn z 10.10.2026.

    cd backend && python -m scripts.test_text_clean
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import feedparser

from src.models.article import ArticleOutput
from src.scrapers.rss_scraper import RSSFeedScraper
from src.utils.text_clean import clean_feed_text

results: list[bool] = []


def check(label: str, ok: bool, detail="") -> None:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + str(detail)) if detail else ''}")
    results.append(bool(ok))


print("\n1️⃣  Czyszczenie")
check("cudzysłowy z encji (6570)", clean_feed_text("&#8222;Duma Zawkrza&#8221; kontynuuje") == "„Duma Zawkrza” kontynuuje")
check("„[…]” WordPressa → wielokropek (6571)", clean_feed_text("Debata w Działdowie [&#8230;]") == "Debata w Działdowie…")
check("stopka Radia Olsztyn znika",
      clean_feed_text("Ruszył remont drogi. The post Ruszył remont appeared first on Radio Olsztyn.") == "Ruszył remont drogi.")
check("podwójnie zakodowana encja", clean_feed_text("A &amp;#8230; B") == "A … B")
check("czysty tekst bez zmian", clean_feed_text("Wyłączenie prądu – Rybno, 9:00") == "Wyłączenie prądu – Rybno, 9:00")
check("puste zostaje puste", clean_feed_text(None) is None and clean_feed_text("") == "")

print("\n2️⃣  Scraper RSS przy pobieraniu")
feed = feedparser.parse("""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>Mławianka &#8211; Elbląg</title><link>https://example.pl/a</link>
<description><![CDATA[<p>&#8222;Duma Zawkrza&#8221; kontynuuje [&#8230;]</p><p>The post Mławianka appeared first on Radio Olsztyn.</p>]]></description>
<pubDate>Sat, 10 Oct 2026 08:00:00 GMT</pubDate></item></channel></rss>""")
parsed = RSSFeedScraper.__new__(RSSFeedScraper)
parsed.logger = __import__("logging").getLogger("test")
item = RSSFeedScraper._parse_entry(parsed, feed.entries[0])
check("tytuł bez encji", item and item["title"] == "Mławianka – Elbląg", item and item["title"])
check("streszczenie bez encji i stopki", item and "&#" not in item["summary"] and "appeared first" not in item["summary"],
      item and item["summary"])

print("\n3️⃣  API — stare wpisy z bazy wydawane czysto")
out = ArticleOutput(id=1, source_id=1, title="Debata &#8211; serce", summary="&#8222;Nafciarzy&#8221; w tabeli",
                    url="https://x.pl", scraped_at=datetime(2026, 10, 10))
check("title i summary w odpowiedzi API", out.title == "Debata – serce" and out.summary == "„Nafciarzy” w tabeli",
      (out.title, out.summary))

passed = sum(results)
print(f"\n{'✅' if passed == len(results) else '❌'} {passed}/{len(results)} sprawdzeń")
sys.exit(0 if passed == len(results) else 1)
