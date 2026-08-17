"""
Rolka 9:16 z JEDNEGO własnego zdjęcia — powolny najazd, napis nieruchomy.

Po co: zdjęcie z drona jest mocnym materiałem, ale nieruchomy kadr jest słabą rolką
— Meta i YouTube traktują statyczny obraz jak gorszy sygnał, a widz przewija.
Najazd robi z tego wideo, nie kosztując ani grosza i nie wymagając modelu.

Jak to jest zrobione i dlaczego akurat tak:
każda klatka to osobne WYCIĘCIE z oryginału (4684×3513 daje ponad dwukrotny zapas
nad 1080×1920), przepuszczone przez `social_card.compose_photo_card`. Dzięki temu
napis, pigułka z datą i stopka są składane od nowa w każdej klatce — czyli stoją
w miejscu i zostają ostre. Gdyby animować gotową kartę, razem ze zdjęciem pełzłby
też adres w stopce, a to widać od razu i wygląda tanio.

Ruch jest celowo minimalny: 5% zbliżenia i 4% zjazdu w dół przez 8 sekund,
wygładzone `smoothstep` (wolny start, wolny koniec). Bez wygładzenia najazd
rusza i staje szarpnięciem — to jedyna rzecz, która na takim ujęciu wygląda jak
efekt z darmowego szablonu.

Użycie:
    cd backend && python -u -m scripts.make_photo_reel \\
        --photo ~/Desktop/DJI_0685.jpg \\
        --claim "DNI DZIAŁDOWA OD 16:00" --day 2026-08-14 \\
        --focus-x 0.36 --out ../DESIGN/video/RybnoLive_DniDzialdowa_9x16.mp4
"""
import argparse
import shutil
import subprocess
import tempfile
from datetime import date
from io import BytesIO
from pathlib import Path

from PIL import Image

from src.services import social_card as sc

FPS = 30
ZOOM_END = 1.05      # 5% — powyżej ~8% widać, że obraz „jedzie", i przestaje być tłem dla tekstu
DRIFT_Y = 0.04       # zjazd w dół, ku lunaparkowi; ułamek wysokości kadru
FADE_IN = 0.5


def smoothstep(t: float) -> float:
    """Wolny start i wolny koniec. Bez tego najazd rusza szarpnięciem."""
    return t * t * (3.0 - 2.0 * t)


def frame_crop(img: Image.Image, progress: float, focus_x: float, focus_y: float) -> bytes:
    aspect = sc.PHOTO_WIDTH / sc.PHOTO_HEIGHT
    width, height = img.size
    eased = smoothstep(progress)

    zoom = 1.0 + (ZOOM_END - 1.0) * eased
    crop_h = min(height, round(height / zoom))
    crop_w = round(crop_h * aspect)
    if crop_w > width:                       # źródło węższe niż kadr — tniemy z wysokości
        crop_w = width
        crop_h = round(crop_w / aspect)

    center_x = focus_x * width
    center_y = (focus_y + DRIFT_Y * eased) * height
    left = min(max(round(center_x - crop_w / 2), 0), width - crop_w)
    top = min(max(round(center_y - crop_h / 2), 0), height - crop_h)

    out = BytesIO()
    img.crop((left, top, left + crop_w, top + crop_h)).save(out, format="JPEG", quality=95)
    return out.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--photo", required=True)
    ap.add_argument("--claim", required=True)
    ap.add_argument("--day", default="")
    ap.add_argument("--focus-x", type=float, default=0.5)
    ap.add_argument("--focus-y", type=float, default=0.5)
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        print("brak ffmpeg w PATH", flush=True)
        return 1

    day = date.fromisoformat(args.day) if args.day else date.today()
    source = Image.open(Path(args.photo).expanduser()).convert("RGB")
    total = int(args.seconds * FPS)

    workdir = Path(tempfile.mkdtemp(prefix="reel_"))
    try:
        for index in range(total):
            progress = index / (total - 1)
            card = sc.compose_photo_card(
                frame_crop(source, progress, args.focus_x, args.focus_y), args.claim, day
            )
            (workdir / f"f{index:04d}.jpg").write_bytes(card)
            if index % 30 == 0:
                print(f"  klatka {index + 1}/{total}", flush=True)

        out_path = Path(args.out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Cicha ścieżka dźwiękowa: część platform odrzuca upload bez audio, a widz
        # i tak ogląda bez dźwięku (napis jest wypalony). Muzykę dokładasz w aplikacji.
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-framerate", str(FPS), "-i", str(workdir / "f%04d.jpg"),
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-vf", f"fade=t=in:st=0:d={FADE_IN},format=yuv420p",
                "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                "-c:a", "aac", "-b:a", "96k", "-shortest",
                "-movflags", "+faststart", str(out_path),
            ],
            check=True, capture_output=True,
        )
        size_mb = out_path.stat().st_size / 1024 / 1024
        print(f"zapisano: {out_path}  ({size_mb:.1f} MB, {args.seconds:g} s, {total} klatek)", flush=True)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
