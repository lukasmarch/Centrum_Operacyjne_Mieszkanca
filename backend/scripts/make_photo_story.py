"""
Karta z WŁASNEGO zdjęcia — story/reels 9:16 albo post do grupy 4:5.

Dlaczego osobny skrypt, a nie flaga w make_group_post: tamten zawsze woła kie.ai
i dobiera postać z obsady. Tutaj kadr jest już zrobiony (dron, telefon), więc cała
robota to wczytać plik i podać go składarce, która i tak istnieje:

    services/social_card.compose_photo_card   → 1080×1920 (story, okładka rolki)
    scripts/make_group_post.compose           → 1080×1350 (post w feedzie grupy)

Typografia, pigułka z datą, gradient i stopka są tam, gdzie były — dzięki temu
zdjęcie z drona czyta się jako ta sama seria co karty generowane. Model nie pisze
ani jednej litery, bo żaden model tu nie startuje.

Użycie:
    cd backend && python -u -m scripts.make_photo_story \\
        --photo ~/Desktop/DJI_0685.jpg \\
        --claim "DNI DZIAŁDOWA ZACZYNAJĄ SIĘ DZIŚ" \\
        --day 2026-08-14 \\
        --out ../DESIGN/stories/story_dni_dzialdowa.jpg

    --format post --kicker "PIĄTEK 14 SIERPNIA"   → wariant 4:5 do grupy
"""
import argparse
from datetime import date
from io import BytesIO
from pathlib import Path

from PIL import Image

from src.services import social_card as sc


def precrop(raw: bytes, aspect: float, focus_x: float, focus_y: float) -> bytes:
    """
    Przytnij do proporcji kadru docelowego wokół WSKAZANEGO punktu, nie środka.

    `social_card._cover` kadruje od środka — dla grafiki z modelu to dobrze, bo model
    komponuje pod środek. Własne zdjęcie tak nie działa: kadr z drona 4:3 przycięty
    na 9:16 od środka wyciął cały lunapark i został z pustym polem. Punkt ostrości
    podajemy ułamkiem szerokości/wysokości oryginału (0 = lewa/góra, 1 = prawa/dół).
    """
    img = Image.open(BytesIO(raw)).convert("RGB")
    width, height = img.size

    if width / height > aspect:          # źródło szersze niż kadr → tniemy boki
        crop_w, crop_h = round(height * aspect), height
    else:                                # źródło wyższe → tniemy górę i dół
        crop_w, crop_h = width, round(width / aspect)

    left = min(max(round(focus_x * width - crop_w / 2), 0), width - crop_w)
    top = min(max(round(focus_y * height - crop_h / 2), 0), height - crop_h)

    out = BytesIO()
    img.crop((left, top, left + crop_w, top + crop_h)).save(out, format="JPEG", quality=95)
    return out.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--photo", required=True, help="ścieżka do własnego zdjęcia")
    ap.add_argument("--claim", required=True)
    ap.add_argument("--kicker", default="", help="tylko dla --format post")
    ap.add_argument("--format", default="story", choices=("story", "post"))
    ap.add_argument("--day", default="", help="RRRR-MM-DD — data w pigułce (domyślnie dziś)")
    ap.add_argument("--focus-x", type=float, default=0.5, help="0 = lewa krawędź, 1 = prawa")
    ap.add_argument("--focus-y", type=float, default=0.5, help="0 = góra, 1 = dół")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    raw = Path(args.photo).expanduser().read_bytes()
    day = date.fromisoformat(args.day) if args.day else date.today()

    aspect = sc.PHOTO_WIDTH / sc.PHOTO_HEIGHT if args.format == "story" else 1080 / 1350
    raw = precrop(raw, aspect, args.focus_x, args.focus_y)

    if args.format == "story":
        out = sc.compose_photo_card(raw, args.claim, day)
    else:
        # Import lokalny: wariant 4:5 rzadko jest potrzebny, a make_group_post
        # ciągnie za sobą klienta kie.ai i całą obsadę.
        from scripts.make_group_post import compose
        out = compose(raw, args.claim, args.kicker)

    path = Path(args.out).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)
    print(f"zapisano: {path}  ({len(out) // 1024} kB, format {args.format})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
