"""
Arkusze referencyjne obsady postów graficznych (W2).

Trzy powracające postacie — Kuba, Ola, Bartek — mają wyglądać tak samo w każdym
poście. Sam opis w prompcie tego nie utrzyma: model za każdym razem rysuje kogoś
podobnego, ale innego, więc seria się rozjeżdża. Dlatego każda grafika dnia idzie
do kie.ai z arkuszem postaci w `image_input`, a arkusze powstają tutaj — raz.

Arkusz zapisujemy do repo (`backend/assets/social/cast/<id>.png`), bo jest częścią
identyfikacji marki i ma jechać z każdym deployem. Na produkcji endpoint
`/api/social/proposal?kind=photo` kopiuje go do uploads/social/cast/ i to ten adres
dostaje kie.ai.

Skrypt kosztuje kredyty kie.ai (~22 za arkusz), więc domyślnie robi tylko brakujące.

Użycie:
    cd backend && python -m scripts.build_social_cast              # brakujące arkusze
    cd backend && python -m scripts.build_social_cast --only ola   # jedna postać
    cd backend && python -m scripts.build_social_cast --force      # wszystkie od nowa
    cd backend && python -m scripts.build_social_cast --dry-run    # sam prompt, bez kie.ai
"""
import argparse
import asyncio
import sys
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from src.services import social_content

# 3:4 zamiast 9:16 grafik dnia: arkusz ma pokazać postać, nie kadr posta. Model
# czyta z niego wygląd, a proporcje docelowej kompozycji bierze z własnego promptu.
SHEET_ASPECT_RATIO = "3:4"
SHEET_RESOLUTION = "2K"

# Arkusz z kie.ai to PNG ~6 MB. Do repo (i do pobrania przez kie.ai przy każdej
# grafice) idzie wersja lżejsza: przy referencji liczy się rozpoznawalność twarzy
# i ubrania, nie rozdzielczość — trzy arkusze w oryginale to 18 MB w historii gita.
SHEET_MAX_EDGE = 1280
SHEET_QUALITY = 92


async def build_one(cast_id: str, force: bool, dry_run: bool) -> None:
    target = social_content.cast_reference_path(cast_id)
    prompt = social_content.cast_sheet_prompt(cast_id)

    print(f"\n=== {social_content.CAST[cast_id]['name']} ({cast_id}) ===")
    print(f"Prompt:\n{prompt}\n")

    if dry_run:
        return
    if target.exists() and not force:
        print(f"Arkusz już istnieje: {target} — pomijam (--force żeby nadpisać)")
        return

    url = await social_content.generate_image(
        prompt, aspect_ratio=SHEET_ASPECT_RATIO, resolution=SHEET_RESOLUTION
    )
    print(f"kie.ai: {url}")

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

    sheet = Image.open(BytesIO(response.content)).convert("RGB")
    sheet.thumbnail((SHEET_MAX_EDGE, SHEET_MAX_EDGE), Image.LANCZOS)

    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target, format="JPEG", quality=SHEET_QUALITY, optimize=True)
    print(f"Zapisano {target} ({target.stat().st_size // 1024} kB, {sheet.width}×{sheet.height})")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Generuj arkusze referencyjne obsady W2")
    parser.add_argument("--only", choices=sorted(social_content.CAST), help="tylko ta postać")
    parser.add_argument("--force", action="store_true", help="nadpisz istniejące arkusze")
    parser.add_argument("--dry-run", action="store_true", help="pokaż prompty, nic nie generuj")
    args = parser.parse_args()

    ids = [args.only] if args.only else sorted(social_content.CAST)
    for cast_id in ids:
        await build_one(cast_id, force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
