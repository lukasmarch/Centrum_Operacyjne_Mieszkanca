"""
Scraper nowej strony gminarybno.pl (od 22.10.2026) — bez sieci i bazy, idzie do CI.

    cd backend && python -m scripts.test_gmina_portal

Gmina przeniosła portal na nowy system: `aktualnosci.html` i `…,7605.html`
odpowiadają 404, a scheduler przez trzy dni zgłaszał błąd źródła. Test pilnuje:
  1. listy `article.news-card` z datą DD.MM.RRRR i adresem `artykul/…`,
  2. pominięcia kafla z kalendarza gminy (zapowiedź, nie wiadomość),
  3. szczegółów pobieranych TYLKO dla wpisów z okna świeżości (stary scraper
     pobierał stronę każdego wpisu z listy — 13 żądań w ~5 s),
  4. podmiany adresu listy zapisanego w `sources.url` sprzed przebudowy.
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.gmina_rybno import GminaRybnoScraper

results: list[bool] = []


def check(label: str, ok: bool, detail="") -> None:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + str(detail)) if detail else ''}")
    results.append(bool(ok))


def card(href: str, title: str, day: datetime, img: str) -> str:
    return f"""
<div class="col-sm-6 col-lg-3"><article class="news-card h-100">
 <a href="{href}" class="news-image " style="background-image:url('{img}')" aria-label="Czytaj: {title}"></a>
 <div class="news-card-body"><p class="news-meta">{day:%d.%m.%Y}</p>
 <h3><a href="{href}">{title}</a></h3><p>Zajawka.</p>
 <a class="text-link" href="{href}">Czytaj więcej</a></div></article></div>"""


NOW = datetime.utcnow()
LIST_HTML = (
    '<html><head><base href="/"></head><body><main id="main-content"><div class="row">'
    + card("artykul/si-ownia-w-centrum-sportu-b99614", "Siłownia w Centrum Sportu",
           NOW, "uploads/images/a.jpg")
    + """
<div class="col-sm-6 col-lg-3"><article class="news-card h-100">
 <a class="news-card-image" href="kalendarz-wydarzen/xxix-bieg-niepodleglosci"><img src="uploads/images/w.jpg"></a>
 <div class="news-card-body"><p class="eyebrow text-primary">Wydarzenie w kalendarzu</p>
 <h2 class="h5"><a href="kalendarz-wydarzen/xxix-bieg-niepodleglosci">XXIX Bieg Niepodległości</a></h2>
 <p class="small text-muted">11.11.2026 · Stadion</p></div></article></div>"""
    + card("artykul/forum-tarcza-wsch-d-w-praktyce-40", "Forum - Tarcza Wschód w praktyce",
           NOW - timedelta(days=6), "uploads/images/b.jpeg")
    + "</div></main></body></html>"
)

ARTICLE_HTML = """
<main id="main-content"><article class="article-layout article-shell">
<p class="eyebrow text-primary"><a href="aktualnosci">Aktualności</a></p>
<h1>Siłownia w Centrum Sportu z nowym wyposażeniem</h1>
<p class="news-meta">Opublikowano: 23.10.2026</p>
<div class="article-body"><p>Siłownia w Centrum Sportu w Rybnie została doposażona.</p>
<script>bad()</script></div>
<div class="article-photo-grid"><button><img class="img-fluid" src="uploads/images/c.jpg"></button></div>
</article></main>"""


def section_listing() -> None:
    print("\n1️⃣  Lista aktualności")
    items = GminaRybnoScraper(2, {}).parse_listing(LIST_HTML)
    check("dwa wpisy, kafel z kalendarza pominięty", len(items) == 2, [i["title"] for i in items])
    first = items[0]
    check("adres bezwzględny wpisu",
          first["url"] == "https://gminarybno.pl/artykul/si-ownia-w-centrum-sportu-b99614", first["url"])
    check("external_id z prefiksem źródła",
          first["external_id"] == "gminarybno:si-ownia-w-centrum-sportu-b99614", first["external_id"])
    check("data z listy", first["published_at"].date() == NOW.date())
    check("zdjęcie z tła kafla", first["image_url"] == "https://gminarybno.pl/uploads/images/a.jpg",
          first["image_url"])


def section_detail() -> None:
    print("\n2️⃣  Strona wpisu")
    data = GminaRybnoScraper(2, {})._parse_detail(ARTICLE_HTML)
    check("pełny tytuł z h1", data.get("title") == "Siłownia w Centrum Sportu z nowym wyposażeniem")
    check("treść z article-body, bez skryptów",
          "doposażona" in data.get("content", "") and "bad()" not in data.get("content", ""))
    check("zdjęcie wpisu", data.get("image_url") == "https://gminarybno.pl/uploads/images/c.jpg")


async def section_requests() -> None:
    print("\n3️⃣  Żądania: tylko świeże wpisy i stary adres listy")
    scraper = GminaRybnoScraper(2, {})
    fetched: list[str] = []

    async def fake_fetch(url: str) -> str:
        fetched.append(url)
        return ARTICLE_HTML

    scraper.fetch = fake_fetch
    articles = await scraper.parse(LIST_HTML, GminaRybnoScraper.LIST_URL)
    check("szczegóły tylko dla wpisu z okna 2 dni", fetched == [articles[0]["url"]] and len(articles) == 1,
          fetched)
    check("data z listy nie jest nadpisywana", articles[0]["published_at"].date() == NOW.date())

    legacy = GminaRybnoScraper(2, {})
    seen: list[str] = []

    async def fake_base_fetch(self, url):  # noqa: ANN001
        seen.append(url)
        return ""

    from src.scrapers import base
    original = base.BaseScraper.fetch
    base.BaseScraper.fetch = fake_base_fetch
    try:
        await legacy.fetch("https://gminarybno.pl/aktualnosci.html")
    finally:
        base.BaseScraper.fetch = original
    check("adres sprzed przebudowy trafia na nową listę", seen == [GminaRybnoScraper.LIST_URL], seen)


def main() -> None:
    section_listing()
    section_detail()
    asyncio.run(section_requests())
    ok = sum(results)
    print(f"\n{'✅' if ok == len(results) else '❌'} {ok}/{len(results)} sprawdzeń")
    sys.exit(0 if ok == len(results) else 1)


if __name__ == "__main__":
    main()
