"""
Podgląd posta graficznego W2 bez publikacji.

Przechodzi całą drogę, którą co wtorek o 17:00 robi `/api/social/proposal?kind=photo`:
podsumowanie dnia → claim, wybór postaci i scena (gpt-4o) → grafika w kie.ai z arkuszem
postaci jako referencją → typografia marki (social_card). Efekt ląduje na dysku, więc
zmianę stylu widać PRZED wysłaniem czegokolwiek na Telegram.

Referencja postaci musi być URL-em, po który sięgnie kie.ai. Na produkcji podaje go
`endpoints/social.cast_reference_url` (uploads/social/cast/…), ale localhost jest dla
kie.ai nieosiągalny — stąd `--reference`, gdzie wkleja się dowolny publiczny adres
arkusza (np. świeży link z `build_social_cast.py`). Bez tej flagi test i tak przejdzie,
tylko twarz będzie wyłącznie z opisu.

Użycie:
    cd backend && python -m scripts.test_social_photo --dry-run          # sam prompt, 0 zł
    cd backend && python -m scripts.test_social_photo --db               # materiał z bazy
    cd backend && python -m scripts.test_social_photo --reference https://…/kuba.png
"""
import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

import httpx

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from src.services import social_card, social_content

OUT_DIR = Path("/tmp/social_photo")

# Materiał zastępczy, gdy nie sięgamy do bazy — awaria prądu, bo to najczęstszy
# przypadek W2 i najostrzejszy test tonu (ma być powaga, nie zabawa).
FALLBACK = {
    "date": date.today().isoformat(),
    "headline": "AWARIA: wyłączenie prądu w Rybnie i Truszczynach",
    "content": {
        "date": date.today().isoformat(),
        "headline": "AWARIA: wyłączenie prądu w Rybnie i Truszczynach",
        "highlights": (
            "Energa zapowiada wyłączenie prądu w Rybnie i Truszczynach w środę od 8:00 do 14:00. "
            "Bez zasilania zostaną też dwie ulice w Żabinach. W gminie trwa remont drogi "
            "powiatowej, a w sobotę na boisku w Rybnie odbędzie się festyn rodzinny."
        ),
    },
}


async def load_summary(from_db: bool) -> dict:
    if not from_db:
        return FALLBACK

    from sqlmodel import select

    from src.database import DailySummary
    from src.database.connection import async_session

    async with async_session() as session:
        result = await session.execute(select(DailySummary).order_by(DailySummary.date.desc()).limit(1))
        summary = result.scalar_one_or_none()

    if not summary:
        print("Brak podsumowania w bazie — biorę materiał zastępczy")
        return FALLBACK

    return {
        "date": summary.date.strftime("%Y-%m-%d"),
        "headline": summary.headline,
        "content": summary.content,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Podgląd posta graficznego W2")
    parser.add_argument("--db", action="store_true", help="weź podsumowanie z bazy")
    parser.add_argument("--reference", help="publiczny URL arkusza postaci dla kie.ai")
    parser.add_argument("--dry-run", action="store_true", help="pokaż treść i prompt, nie generuj grafiki")
    args = parser.parse_args()

    summary = await load_summary(args.db)
    proposal = await social_content.build_photo_post(summary)

    print(f"\nNagłówek dnia : {summary['headline']}")
    print(f"Postać        : {social_content.CAST[proposal['cast']]['name']} ({proposal['cast']})")
    print(f"Claim         : {proposal['claim']}")
    print(f"\nPrompt:\n{proposal['prompt']}")
    print(f"\nTreść posta:\n{proposal['message']}")

    if args.dry_run:
        return

    references = [args.reference] if args.reference else None
    if not references:
        print("\n⚠️  Bez --reference: grafika powstanie z samego opisu, twarz może odbiegać od arkusza")

    url = await social_content.generate_image(proposal["prompt"], references=references)
    print(f"\nkie.ai: {url}")

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = OUT_DIR / f"{proposal['cast']}_raw.png"
    raw_path.write_bytes(response.content)

    card = social_card.compose_photo_card(response.content, proposal["claim"])
    card_path = OUT_DIR / f"{proposal['cast']}_post.jpg"
    card_path.write_bytes(card)

    print(f"Ilustracja : {raw_path}")
    print(f"Gotowy post: {card_path}")


if __name__ == "__main__":
    asyncio.run(main())
