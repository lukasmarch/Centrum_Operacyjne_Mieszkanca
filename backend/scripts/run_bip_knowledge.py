"""
Ręczne uruchomienie joba wiedzy stałej z BIP.

Potrzebne przy pierwszym napełnieniu bazy — scheduler zrobiłby to dopiero
w najbliższą niedzielę o 4:00.

    cd backend && python -m scripts.run_bip_knowledge          # pełny przebieg
    cd backend && python -m scripts.run_bip_knowledge --dry    # bez zapisu i bez kosztów

Tryb --dry pobiera dokumenty i pokazuje, co by weszło do bazy. Warto go użyć
po każdej zmianie `DEFAULT_SECTIONS` — pełny przebieg płaci za embeddingi.
"""
import asyncio
import sys

from src.scheduler.bip_knowledge_job import run_bip_knowledge_job_async
from src.scrapers.bip_knowledge import BipKnowledgeScraper


async def dry_run():
    scraper = BipKnowledgeScraper()
    documents = await scraper.scrape_all()

    print(f"\n{'=' * 78}")
    print(f"DRY RUN — {len(documents)} dokumentów z {len(scraper.sections)} działów (nic nie zapisano)")
    print("=" * 78)

    by_section: dict[str, list[dict]] = {}
    for doc in documents:
        by_section.setdefault(doc["section_name"], []).append(doc)

    total_chars = 0
    for section, docs in by_section.items():
        chars = sum(len(d["content"]) for d in docs)
        pdfs = sum(d["pdf_count"] for d in docs)
        total_chars += chars
        print(f"\n[{section}] — {len(docs)} dok., {chars:,} zn., {pdfs} PDF")
        for doc in docs:
            print(f"    {doc['title'][:58]:<60} {len(doc['content']):>7,} zn  PDF:{doc['pdf_count']}")

    # ~4 znaki na token, 0,02 USD za 1M tokenów (text-embedding-3-small)
    tokens = total_chars / 4
    print(f"\n{'=' * 78}")
    print(f"Razem: {total_chars:,} znaków ≈ {tokens:,.0f} tokenów")
    print(f"Szacowany koszt pełnego osadzenia: ${tokens / 1_000_000 * 0.02:.4f}")

    empty = [s for s, d in by_section.items() if not d]
    missing = [name for _, name in scraper.sections if name not in by_section]
    if missing:
        print(f"\n⚠️  Działy bez dokumentów: {', '.join(missing)}")


if __name__ == "__main__":
    if "--dry" in sys.argv:
        asyncio.run(dry_run())
    else:
        asyncio.run(run_bip_knowledge_job_async())
