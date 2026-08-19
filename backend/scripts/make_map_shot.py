"""
Ujęcie z nieruchomej grafiki: nalot z odjazdem (zoom + przesunięcie) w kadrze pasa.

Po co osobne narzędzie: `make_photo_reel.py` robi rolkę ZE ZDJĘCIA i wypełnia nim
cały kadr 9:16 — dobre dla drona, złe dla mapy, bo pionowy kadr obcina trasę do
jednej trzeciej. Tutaj grafika żyje w POZIOMYM PASIE (domyślnie 1080×1000), a kadr
9:16 dokłada `burn_brand_caption` razem z warstwą marki. Pas zostaje ten sam dla
mapy i dla ujęcia z drona, więc oba montują się bez zmiany kompozycji.

Ruch: kamera zaczyna nisko i blisko, potem WZNOSI SIĘ — zoom maleje, okno wędruje
w bok. Odjazd jest lepszy niż najazd, bo kończy się na kadrze najostrzejszym:
najbardziej powiększona (czyli najbardziej miękka) jest pierwsza sekunda, kiedy
widz jeszcze nic nie czyta, a nie ostatnia, kiedy szuka swojej wsi.

⚠️ Powiększenie ponad ~2,2× robi z podpisów na mapie plamy. `--zoom-start` trzymaj
poniżej 1.35 dla grafiki szerokiej na ~1000 px — inaczej lepiej dać mniej ruchu
niż nieczytelną mapę. AI-upscale grafiki nie jest wyjściem: przy komunikacie
organizatora model przerabia nazwy własne (sprawdzone 19.08 — „RUNDY" → „RUHDY").

Użycie:
    cd backend && python -u -m scripts.make_map_shot \\
        --image ../DESIGN/assets/img/mapa_mtb_1255n.jpg --seconds 18 \\
        --zoom-start 1.30 --zoom-end 1.00 --focus-start 0.18 --focus-end 0.55 \\
        --out /tmp/mapa_shot.mp4
"""
import argparse
import subprocess
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

FPS = 30


def smoothstep(t: float) -> float:
    """Wolny start i wolny koniec. Bez tego ruch rusza i staje szarpnięciem."""
    return t * t * (3.0 - 2.0 * t)


def frame(img: Image.Image, progress: float, args) -> bytes:
    eased = smoothstep(progress)
    zoom = args.zoom_start + (args.zoom_end - args.zoom_start) * eased
    focus = args.focus_start + (args.focus_end - args.focus_start) * eased

    aspect = args.width / args.height
    win_h = min(img.height, img.height / zoom)
    win_w = win_h * aspect
    if win_w > img.width:                     # grafika węższa niż okno — tniemy z wysokości
        win_w = img.width
        win_h = win_w / aspect

    left = (img.width - win_w) * focus
    top = (img.height - win_h) / 2
    crop = img.crop((round(left), round(top), round(left + win_w), round(top + win_h)))
    out = crop.resize((args.width, args.height), Image.LANCZOS)

    buffer = BytesIO()
    out.convert("RGB").save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--seconds", type=float, default=18.0)
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1000)
    ap.add_argument("--zoom-start", type=float, default=1.30)
    ap.add_argument("--zoom-end", type=float, default=1.00)
    ap.add_argument("--focus-start", type=float, default=0.18,
                    help="0 = lewa krawędź grafiki, 1 = prawa")
    ap.add_argument("--focus-end", type=float, default=0.55)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    source = Path(args.image).expanduser()
    if not source.exists():
        sys.exit(f"nie ma pliku: {source}")
    img = Image.open(source).convert("RGB")

    total = max(1, round(args.seconds * FPS))
    magnification = args.height / (img.height / max(args.zoom_start, args.zoom_end))
    print(f"  {img.width}×{img.height} → {args.width}×{args.height}, {total} klatek, "
          f"maks. powiększenie {magnification:.2f}×", flush=True)
    if magnification > 2.2:
        print("  ⚠️ powyżej 2,2× podpisy na grafice zaczynają się rozmywać", flush=True)

    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "image2pipe", "-framerate", str(FPS),
           "-i", "-", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
           "-pix_fmt", "yuv420p", str(Path(args.out).expanduser())]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for index in range(total):
        proc.stdin.write(frame(img, index / (total - 1), args))
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg nie złożył ujęcia")
    print(f"zapisano: {args.out}  ({args.seconds:.1f} s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
