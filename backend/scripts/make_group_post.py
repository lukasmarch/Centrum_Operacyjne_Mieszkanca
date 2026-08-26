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
from typing import Optional

import numpy as np
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

# ── wariant fotograficzny (--photo) ──────────────────────────────────────────
#
# Zdjęcie ZOSTAJE ZDJĘCIEM: nie idzie do modelu jako referencja, bo model przerysuje
# je na kreskówkę i zniknie jedyny powód, dla którego tu jest — mieszkaniec ma
# rozpoznać swój dach, nie „jakąś wieś”. Postać dokładamy wycinkiem NA WIERZCHU.
# Gruby biały kontur z BRAND_STYLE robi z niej naklejkę, a nie fotomontaż — płaska
# kreska na fotografii czyta się jako element graficzny i nikt nie bierze jej za realną.
PHOTO_GRADIENT_TOP = int(HEIGHT * 0.45)   # wyżej niż w wariancie rysunkowym: przy 0.30
                                          # gradient zjadał wodę i pola, czyli treść zdjęcia
CUTOUT_WIDTH = 430
CUTOUT_BOTTOM = HEIGHT - 96
CUTOUT_BLEED = 0                          # ile postać wychodzi poza prawą krawędź;
                                          # przy 40 krawędź ucinała zwój mapy w dłoni
PHOTO_CLAIM_SIZES = (86, 76, 68, 60, 54)  # węższa kolumna niż w wariancie pełnym —
PHOTO_MAX_LINES = 4                       # postać zabiera prawą trzecią kadru
CHROMA = (255, 0, 255)

# Osobny styl, bo BRAND_STYLE ma malowane tło wpisane w treść — a do wycinka
# potrzebujemy płaskiej płaszczyzny, którą da się wyciąć bez usługi zewnętrznej.
# Magenta, nie zieleń: Kuba ma miętową koszulkę, więc klucz na zielonym zjadłby mu tors.
CUTOUT_STYLE = (
    "Bold western cartoon sticker illustration (comic/graffiti poster energy, NOT anime, "
    "not photorealistic, not 3D render): thick clean black lineart, flat cel shading with "
    "one crisp highlight, expressive slightly caricatured face, confident hand-drawn feel. "
    "The person is cut out by a THICK WHITE STICKER OUTLINE. "
    "BACKGROUND IS COMPLETELY FLAT SOLID MAGENTA #FF00FF — one single uniform color, "
    "no gradient, no texture, no shadow, no paint strokes, no props, no scenery. "
    "NOTHING in the frame except the single character. Nothing magenta or pink on the "
    "character itself. "
    # Arkusz referencyjny ma DWIE postacie (sylwetka + portret) i na płaskim tle model
    # odtworzył ten układ: dokleił drugą głowę w prawym górnym rogu. Przy malowanym tle
    # z BRAND_STYLE to się nie zdarzało — kompozycja plakatu nie zostawiała na nią miejsca.
    "EXACTLY ONE PERSON, one single head, one body. Do NOT reproduce the layout of the "
    "reference sheet: no second portrait, no extra head, no bust, no duplicate of the "
    "character anywhere in the frame. "
    "Ordinary present-day Polish clothing, plain and unbranded — no brand marks or prints. "
    "Vibrant saturated colors, high contrast. "
    "ABSOLUTELY NO text, letters, numbers, signage, captions, logos or watermarks."
)


def chroma_cutout(raw: bytes, tol: int = 90, feather: int = 150) -> Image.Image:
    """Wytnij postać z płaskiego tła magenta i przytnij kadr do samej sylwetki."""
    img = Image.open(BytesIO(raw)).convert("RGB")
    # int32, nie int16: (255-0)**2 = 65025 nie mieści się w int16, więc suma kwadratów
    # przekręcała się na ujemną, sqrt dawał NaN i alfa wychodziła losowa — tło zostawało.
    arr = np.asarray(img).astype(np.int32)

    dist = np.sqrt(((arr - np.array(CHROMA, dtype=np.int32)) ** 2).sum(axis=2))
    alpha = np.clip((dist - tol) * 255.0 / max(1, feather - tol), 0, 255).astype(np.uint8)

    # Odplamienie krawędzi: piksel na styku białego konturu i tła wychodzi różowy.
    # Warunek wymaga, by NAD zielony wybijały się OBA kanały — skóra (R>G>B) i
    # pomarańczowa koszula tego nie spełniają, więc zostają nietknięte.
    rgb = arr.copy()
    spill = (rgb[:, :, 0] > rgb[:, :, 1] + 25) & (rgb[:, :, 2] > rgb[:, :, 1] + 25)
    for channel in (0, 2):
        rgb[:, :, channel] = np.where(
            spill, np.minimum(rgb[:, :, channel], rgb[:, :, 1] + 25), rgb[:, :, channel]
        )

    out = Image.fromarray(np.dstack([rgb.astype(np.uint8), alpha]))
    bbox = out.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    return out.crop(bbox) if bbox else out


def compose_photo(photo: bytes, cutout: Optional[Image.Image],
                  claim: str, kicker: str) -> bytes:
    """Prawdziwe zdjęcie w tle + postać jako naklejka w prawym dolnym rogu."""
    img = sc._cover(Image.open(BytesIO(photo)).convert("RGB"), WIDTH, HEIGHT).convert("RGBA")

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), sc.BG + (0,))
    odraw = ImageDraw.Draw(overlay)
    for y in range(PHOTO_GRADIENT_TOP, HEIGHT):
        progress = (y - PHOTO_GRADIENT_TOP) / (HEIGHT - PHOTO_GRADIENT_TOP)
        odraw.line((0, y, WIDTH, y), fill=sc.BG + (int(255 * progress**GRADIENT_CURVE),))
    img = Image.alpha_composite(img, overlay)

    # Postać NA gradiencie, nie pod nim — przyciemniona naklejka gubi biały kontur,
    # czyli to jedno, co trzyma ją wizualnie osobno od fotografii.
    text_width = TEXT_WIDTH
    if cutout is not None:
        figure = cutout.resize(
            (CUTOUT_WIDTH, round(cutout.height * CUTOUT_WIDTH / cutout.width)), Image.LANCZOS
        )
        left = WIDTH - CUTOUT_WIDTH + CUTOUT_BLEED
        img.alpha_composite(figure, (left, CUTOUT_BOTTOM - figure.height))
        text_width = left - MARGIN - 28

    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    claim_font, lines, size = sc._fit_headline(
        claim, text_width, PHOTO_CLAIM_SIZES, PHOTO_MAX_LINES
    )

    footer_top = HEIGHT - 210
    block_bottom = footer_top - 52
    line_h = int(size * 1.16)
    y = block_bottom - line_h * len(lines)

    if kicker:
        draw.text((MARGIN, y - 58), kicker.upper(), font=sc._font(34, "Bold"),
                  fill=sc.GLOW, anchor="la")

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
    ap.add_argument("--photo", default="",
                    help="ścieżka do zdjęcia w tle; postać idzie wtedy jako wycinek "
                         "w prawym dolnym rogu, a samo zdjęcie zostaje nietknięte")
    ap.add_argument("--reuse-raw", action="store_true",
                    help="weź zapisaną grafikę <out>_raw.png zamiast wołać model — "
                         "przestrojenie układu ma kosztować zero")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    member_look = CAST[args.cast]["look"]
    # BRAND_STYLE zakazuje znaków firmowych na UBRANIACH — na pierwszej próbie
    # model wyhaftował za to logo producenta na masce samochodu. W gminie, gdzie
    # publikujemy to jako materiał własny, cudzy znak towarowy w kadrze jest
    # ryzykiem prawnym, więc zakaz musi objąć wszystko, co stoi w tle.
    no_marks = (
        "No brand marks anywhere in frame: vehicles have blank grilles with no emblems "
        "or badges, no manufacturer logos, no shop signage, no product packaging."
    )
    style = CUTOUT_STYLE if args.photo else f"{BRAND_STYLE}\n{no_marks}"
    prompt = f"{style}\n\nSCENE: {args.scene}\n\nCHARACTER: {member_look}"

    raw_path = Path(args.out).with_name(Path(args.out).stem + "_raw.png")
    if args.reuse_raw:
        raw = raw_path.read_bytes()
        print(f"[reuse] {raw_path} ({len(raw) // 1024} kB)", flush=True)
    elif args.dry:
        placeholder = Image.new("RGB", (WIDTH, HEIGHT), (28, 34, 48))
        buf = BytesIO()
        placeholder.save(buf, format="PNG")
        raw = buf.getvalue()
    elif args.engine == "openai":
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

    if args.photo:
        # --dry z --photo składa samą kartę ze zdjęciem, bez postaci: kadr i to,
        # czy nagłówek mieści się w węższej kolumnie, sprawdza się wtedy za darmo.
        cutout = None
        if not args.dry:
            # Surowy plik od modelu zostaje na dysku: klucz chromy i skład karty to czysta
            # arytmetyka, więc przestrojenie ma kosztować zero, a nie kolejne $0,12 w kie.ai.
            if not args.reuse_raw:
                raw_path.write_bytes(raw)
                print(f"surowa grafika: {raw_path}", flush=True)
            cutout = chroma_cutout(raw)
        if cutout is not None:
            # Podgląd wycinka leży obok karty. Gdy klucz chromy zawiedzie (model
            # dorzuci cień albo teksturę), widać to tutaj od razu — na karcie
            # objawiłoby się dopiero różową obwódką na ciemnym zdjęciu.
            preview = Path(args.out).with_name(Path(args.out).stem + "_cutout.png")
            cutout.save(preview)
            print(f"wycinek: {preview} ({cutout.width}×{cutout.height})", flush=True)
        card = compose_photo(Path(args.photo).read_bytes(), cutout, args.claim, args.kicker)
    else:
        card = compose(raw, args.claim, args.kicker)

    Path(args.out).write_bytes(card)
    print(f"zapisano: {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
