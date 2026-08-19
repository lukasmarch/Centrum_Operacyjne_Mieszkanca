"""
Grafika do posta w grupie lokalnej — format 4:5 (1080×1350), bo post w grupie
wyświetla się w feedzie, nie w Reels; 9:16 zostałby przycięty w podglądzie.

Reużywa stylu marki i obsady z services/social_content (ten sam BRAND_STYLE,
ten sam arkusz referencyjny), więc post w grupie czyta się jako ta sama seria
co W2 na fanpage'u. Tekst nakłada Pillow naszym fontem — model nie pisze
ani jednej litery (patrz komentarz w social_card).

Użycie:
    cd backend && python -u -m scripts.make_group_post \\
        --claim "URZĄD ZAMKNIĘTY W PIĄTEK" --kicker "14 sierpnia" \\
        --cast kuba --scene "..." --out ../DESIGN/posts/grupa_03.png
    --dry  = sam skład karty na szarym tle, bez kosztu kie.ai

Opis postaci i scen: DESIGN/OBSADA.md
"""
import argparse
import asyncio
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from src.services import social_card as sc
from src.services.social_content import BRAND_STYLE, CAST, CAST_ASSET_DIR, generate_image

WIDTH, HEIGHT = 1080, 1350
MARGIN = 78
TEXT_WIDTH = WIDTH - 2 * MARGIN
CLAIM_SIZES = (104, 92, 80, 70, 62)
MAX_LINES = 3
# Gradient startuje wysoko i szybko dochodzi do pełnego krycia: pierwsza wersja
# (0.46, wykładnik 1.35) zostawiła nagłówek na jasnej kurtce postaci — biały tekst
# na lawendowym płaszczu jest nieczytelny w miniaturze feedu, czyli tam, gdzie
# decyduje się, czy ktoś w ogóle zatrzyma kciuk.
GRADIENT_TOP = int(HEIGHT * 0.30)
GRADIENT_CURVE = 0.85

CAST_URL = "https://api.rybnolive.pl/uploads/social/cast/{}.jpg"


def compose(illustration: bytes, claim: str, kicker: str) -> bytes:
    """Kadr + przyciemnienie dołu + nagłówek + stopka marki."""
    img = sc._cover(Image.open(BytesIO(illustration)).convert("RGB"), WIDTH, HEIGHT)

    # Gradient ku dołowi: ilustracja zostaje czytelna u góry, tekst dostaje tło.
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), sc.BG + (0,))
    odraw = ImageDraw.Draw(overlay)
    for y in range(GRADIENT_TOP, HEIGHT):
        progress = (y - GRADIENT_TOP) / (HEIGHT - GRADIENT_TOP)
        odraw.line((0, y, WIDTH, y), fill=sc.BG + (int(255 * progress**GRADIENT_CURVE),))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    claim_font, lines, size = sc._fit_headline(claim, TEXT_WIDTH, CLAIM_SIZES, MAX_LINES)

    footer_top = HEIGHT - 210
    block_bottom = footer_top - 52
    line_h = int(size * 1.16)
    y = block_bottom - line_h * len(lines)

    # Nadkreślenie zamiast plakietki — kicker mówi, czego dotyczy karta.
    if kicker:
        kfont = sc._font(34, "Bold")
        draw.text((MARGIN, y - 58), kicker.upper(), font=kfont, fill=sc.GLOW, anchor="la")

    for line in lines:
        draw.text((MARGIN, y), line, font=claim_font, fill=sc.WHITE, anchor="la")
        y += line_h

    draw.line((MARGIN, footer_top, MARGIN + 72, footer_top), fill=sc.BLUE, width=6)
    draw.text((MARGIN, footer_top + 32), "rybnolive.pl", font=sc._font(50, "Bold"),
              fill=sc.GLOW, anchor="la")
    draw.text((MARGIN, footer_top + 98), "Twoja gmina. Na żywo.", font=sc._font(34),
              fill=sc.GREY, anchor="la")

    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


# ── drugi silnik graficzny ────────────────────────────────────────────────────
# 19.08.2026: kie.ai (`nano-banana-pro`, model Google) odrzuca KAŻDY prompt z Olą —
# „violated Google's Generative AI Prohibited Use policy" — niezależnie od sceny,
# od opisu postaci i od tego, czy idzie arkusz referencyjny. Kontrola rozstrzygnęła:
# ten sam prompt z mężczyzną przechodzi za pierwszym razem, więc to filtr po stronie
# modelu, nie nasz tekst. `gpt-image-2` przez OpenAI przyjmuje ten sam prompt bez oporu.
#
# Arkusz referencyjny idzie tu jako obraz wejściowy do /images/edits — to odpowiednik
# `image_input` w kie.ai i tak samo trzyma twarz w ryzach.
OPENAI_IMAGE_MODEL = "gpt-image-2"


def generate_image_openai(prompt: str, cast_id: str) -> bytes:
    """Ilustracja z OpenAI, z arkuszem postaci jako referencją. Zwraca bajty PNG."""
    import base64

    import httpx

    from src.config import settings

    key = settings.OPENAI_API_KEY
    sheet = CAST_ASSET_DIR / f"{cast_id}.jpg"
    payload = {
        "model": OPENAI_IMAGE_MODEL,
        "prompt": f"{prompt}\n\nThe attached image is the character reference sheet — "
                  "keep the same face, hair and clothing.",
        "size": "1024x1536",   # 2:3; `compose` dokadruje do 1080×1350
        "quality": "high",
    }
    response = httpx.post(
        "https://api.openai.com/v1/images/edits",
        headers={"Authorization": f"Bearer {key}"},
        data=payload,
        files={"image[]": (sheet.name, sheet.read_bytes(), "image/jpeg")},
        timeout=300.0,
    )
    if response.status_code != 200:
        raise RuntimeError(f"OpenAI odrzuciło zadanie: {response.text[:300]}")
    return base64.b64decode(response.json()["data"][0]["b64_json"])


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--claim", required=True)
    ap.add_argument("--kicker", default="")
    ap.add_argument("--cast", default="bartek", choices=list(CAST))
    ap.add_argument("--scene", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--engine", default="kie", choices=("kie", "openai"),
                    help="kie = nano-banana-pro (domyślny); openai = gpt-image-2 "
                         "(jedyna droga dla Oli — patrz DESIGN/OBSADA.md)")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    if args.dry:
        placeholder = Image.new("RGB", (1080, 1350), (28, 34, 48))
        buf = BytesIO()
        placeholder.save(buf, format="PNG")
        raw = buf.getvalue()
    else:
        member_look = CAST[args.cast]["look"]
        # BRAND_STYLE zakazuje znaków firmowych na UBRANIACH — na pierwszej próbie
        # model wyhaftował za to logo producenta na masce samochodu. W gminie, gdzie
        # publikujemy to jako materiał własny, cudzy znak towarowy w kadrze jest
        # ryzykiem prawnym, więc zakaz musi objąć wszystko, co stoi w tle.
        no_marks = (
            "No brand marks anywhere in frame: vehicles have blank grilles with no emblems "
            "or badges, no manufacturer logos, no shop signage, no product packaging."
        )
        prompt = f"{BRAND_STYLE}\n{no_marks}\n\nSCENE: {args.scene}\n\nCHARACTER: {member_look}"
        if args.engine == "openai":
            print(f"[openai] generuję ({args.cast}, {OPENAI_IMAGE_MODEL})…", flush=True)
            raw = generate_image_openai(prompt, args.cast)
            print(f"[openai] odebrano {len(raw) // 1024} kB", flush=True)
        else:
            print(f"[kie.ai] generuję ({args.cast})…", flush=True)
            url = await generate_image(prompt, aspect_ratio="3:4", resolution="2K",
                                       references=[CAST_URL.format(args.cast)])
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                raw = (await client.get(url)).content
            print(f"[kie.ai] pobrano {len(raw) // 1024} kB", flush=True)

    Path(args.out).write_bytes(compose(raw, args.claim, args.kicker))
    print(f"zapisano: {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
