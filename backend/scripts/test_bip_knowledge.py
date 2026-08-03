"""
Sprawdza scraper wiedzy stałej z BIP.

    cd backend && python -m scripts.test_bip_knowledge          # parsowanie, bez sieci
    cd backend && python -m scripts.test_bip_knowledge --live   # + realne pobranie 3 działów

Sedno testu to rzeczy, które psuły się po cichu: dział gubiony przez jedno
nieudane żądanie, tytuł „Biuletyn Informacji Publicznej" na każdym dokumencie
i nawigacja SYSTEMDOBIP wchodząca do embeddingu jako treść.
"""
import asyncio
import sys

from src.ai.chunker import chunker
from src.scrapers.bip_knowledge import (
    DEFAULT_SECTIONS,
    MIN_CONTENT_CHARS,
    BipKnowledgeScraper,
)

failures: list[str] = []


def check(condition: bool, label: str, detail: str = "") -> None:
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  FAIL {label}{f' — {detail}' if detail else ''}")
        failures.append(label)


PAGE = """
<html><body>
<h1>Biuletyn Informacji Publicznej</h1>
<div class="information">
  <h2>AZBEST - Informacja</h2>
  <p>Akapit nr 1 - brak tytułu</p>
  <p>Mieszkańcy mogą ubiegać się o dofinansowanie usunięcia wyrobów zawierających
  azbest z dachów budynków mieszkalnych i gospodarczych. Wniosek składa się
  w Urzędzie Gminy Rybno do 31 marca danego roku.</p>
  <a href="/system/pobierz.php?plik=regulamin_azbest.pdf&amp;id=e">Regulamin</a>
  <a href="/system/pobierz.php?plik=wniosek_azbest.pdf&amp;id=f">Wniosek</a>
  <p>Rejestr zmian</p>
  <p>Artykuł był wyświetlony: 1234 raz(y)</p>
  <p>Podmiot udostępniający informację: Urząd Gminy Rybno</p>
</div>
<div class="information-parameters">Informacja ogłoszona dnia 2025-03-14 09:12:00</div>
</body></html>
"""

SECTION_LIST = """
<html><body>
<a href="/74/1/archiwum/Ochrona_srodowiska/">archiwum</a>
<a href="/74/900/AZBEST_-_Informacja/">AZBEST</a>
<a href="/74/900/AZBEST_-_Informacja/rejestr/">rejestr zmian</a>
<a href="https://bip.gminarybno.pl/74/901/Program_Ochrony_Srodowiska/">Program</a>
<a href="/105/1105/Podatek_rolny/">inny dział</a>
<a href="/74/900/AZBEST_-_Informacja/">duplikat</a>
</body></html>
"""

scraper = BipKnowledgeScraper()

print("\n== Parsowanie dokumentu ==")
parsed = scraper._parse_document(PAGE)
check(
    parsed["title"] == "AZBEST - Informacja",
    "tytuł z treści, nie z <h1> serwisu",
    f"dostałem: {parsed['title']!r}",
)
check(len(parsed["pdf_urls"]) == 2, "wykryte OBA załączniki, nie tylko pierwszy")
check(
    all("bip.gminarybno.pl" in u for u in parsed["pdf_urls"]),
    "linki do załączników są bezwzględne",
)
check(parsed["document_date"] is not None, "data dokumentu odczytana")
check("azbest" in parsed["content"].lower(), "treść merytoryczna zachowana")
for noise in ("Rejestr zmian", "Artykuł był wyświetlony", "Podmiot udostępniający", "Akapit nr"):
    check(noise not in parsed["content"], f"nawigacja odsiana: {noise!r}")

print("\n== Linki działu ==")
links = scraper._section_links(SECTION_LIST, "74")
check(len(links) == 2, f"dwa dokumenty działu (dostałem {len(links)})")
check(not any("/archiwum/" in u for u in links), "archiwum pominięte")
check(not any(u.endswith("/rejestr/") for u in links), "rejestr zmian pominięty")
check(not any("/105/" in u for u in links), "obcy dział pominięty")
check(len(links) == len(set(links)), "brak duplikatów")
check(all(u.startswith("https://") for u in links), "wszystkie linki na https")

print("\n== Nazwa załącznika ==")
check(
    scraper._pdf_label("https://bip.gminarybno.pl/system/pobierz.php?plik=wniosek.pdf&id=e")
    == "wniosek.pdf",
    "nazwa pliku z parametru plik=",
)

print("\n== Konfiguracja ==")
ids = [sid for sid, _ in DEFAULT_SECTIONS]
check(len(ids) == len(set(ids)), "brak zdublowanych działów w DEFAULT_SECTIONS")
check("74" in ids and "105" in ids and "125" in ids, "kluczowe działy na liście")
check(MIN_CONTENT_CHARS >= 100, "próg treści odsiewa puste zajawki")

print("\n== Chunkowanie ==")
chunks = chunker.chunk_bip_static(
    title="AZBEST - Informacja",
    content="Dofinansowanie usunięcia azbestu. " * 200,
    section_name="Ochrona środowiska",
)
check(len(chunks) > 1, "długi dokument dzielony na części")
check(
    all(c["text"].startswith("[BIP › Ochrona środowiska]") for c in chunks),
    "KAŻDY chunk niesie dział i tytuł",
)
check(
    all(c["metadata"]["chunk_type"] == "bip_static" for c in chunks),
    "metadane oznaczają typ bip_static",
)
empty = chunker.chunk_bip_static("Statut", None, "Statut Gminy")
check(len(empty) == 1, "dokument bez treści daje jeden chunk tytułowy")


print("\n== Synonimy w zapytaniu ==")
# Pomiar na produkcji 3.08.2026: „azbest" trafiał w dokument BIP z podobieństwem
# 0,674, „eternit" nie trafiał w niego wcale. Retrieval dzieje się przed modelem,
# więc zapytanie trzeba poprawić w kodzie.
from src.services.search_synonyms import expand_query  # noqa: E402

expanded = expand_query("czy moge dostac dofinansowanie na usuniecie eternitu z dachu")
check("azbest" in expanded, "eternit dociąga termin 'azbest'")
check("eternitu" in expanded, "oryginalne słowo zostaje (pracuje w BM25)")
check("odpady komunalne" in expand_query("kiedy wywoz smieci"), "śmieci → odpady komunalne")
check("wody" in expand_query("czy woda jest brudna"), "kolejność słów nie ma znaczenia")
check(
    expand_query("ile wynosi bezrobocie") == "ile wynosi bezrobocie",
    "zapytanie bez trafienia zostaje nietknięte",
)
check(expand_query("") == "" and expand_query(None) == "", "puste wejście nie wywala")
check(
    expand_query("azbest") == "azbest",
    "termin urzędowy nie dubluje sam siebie",
)


async def live() -> None:
    print("\n== Pobranie na żywo ==")
    live_scraper = BipKnowledgeScraper({
        "sections": [
            {"id": "147", "name": "Jednostki pomocnicze (sołectwa)"},
            {"id": "105", "name": "Podatki i opłaty"},
            {"id": "74", "name": "Ochrona środowiska"},
        ],
        "max_docs_per_section": 3,
    })
    docs = await live_scraper.scrape_all()
    check(len(docs) >= 3, f"pobrano dokumenty ({len(docs)})")

    sections_found = {d["section_name"] for d in docs}
    check(
        "Jednostki pomocnicze (sołectwa)" in sections_found,
        "dział sołectw wrócił z treścią",
        "to on przepadł w przebiegu 3.08.2026",
    )
    solectwa = next(
        (d for d in docs if d["section_name"].startswith("Jednostki pomocnicze")), None
    )
    if solectwa:
        check("Hartowiec" in solectwa["content"], "treść sołectw zawiera nazwy wsi")
    check(
        all(len(d["content"]) >= MIN_CONTENT_CHARS for d in docs),
        "żaden pobrany dokument nie jest pustą zajawką",
    )
    check(
        all(d["content_hash"] for d in docs),
        "każdy dokument ma hash treści",
    )
    check(
        len({d["url"] for d in docs}) == len(docs),
        "brak zdublowanych URL-i",
    )


if "--live" in sys.argv:
    asyncio.run(live())
else:
    print("\n(pominięto test sieciowy — uruchom z --live)")

print(f"\n{'=' * 50}")
if failures:
    print(f"NIEPOWODZENIA ({len(failures)}): " + ", ".join(failures))
    sys.exit(1)
print("Wszystko przeszło.")
