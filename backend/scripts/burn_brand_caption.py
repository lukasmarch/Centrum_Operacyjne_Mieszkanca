"""
Wypal napis marki na własnym materiale wideo + podłóż lektora.

Po co: „Dni Działdowa" (`make_photo_reel.py`) robi rolkę ZE ZDJĘCIA i sam składa
każdą klatkę. Kiedy montaż powstaje w Final Cut, klatek nie składamy — dostajemy
gotowy plik i trzeba na niego nałożyć dokładnie tę samą warstwę marki. Nakładkę
daje `social_card.render_photo_overlay` (ta sama funkcja rysuje post graficzny),
więc napis w rolce jest pikselowo napisem z posta, a nie jego podobizną.

Napis jest NIERUCHOMY przez cały klip — treść niesie lektor. To świadoma decyzja:
napis zmieniający się co ujęcie wymaga, by widz czytał, a rolka informacyjna ma
działać też przy przewijaniu bez dźwięku, z jednym komunikatem na kadrze.

Dźwięk: linie lektora sklejane po kolei z katalogu (`tts_elevenlabs.py` numeruje je
`01_`, `02_`…), opcjonalna muzyka −13 dB pod lektorem, całość wyrównana `loudnorm`
do −14 LUFS — tak jak miks rolek „Sąsiad".

Użycie:
    cd backend && python -u -m scripts.burn_brand_caption \\
        --video ~/Desktop/droga_montaz.mp4 \\
        --claim "NOWY ASFALT TUCZKI–KOSZELEWY" --label "ZAKOŃCZENIE PRAC" \\
        --vo ../DESIGN/assets/audio/droga_1255n \\
        --out ../DESIGN/video/RybnoLive_Droga1255N_9x16.mp4
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional, Tuple

from src.services import social_card as sc

FADE_IN = 0.5
MUSIC_UNDER_DB = -13      # sprawdzone na filmie YT 20 s: wyżej muzyka zjada spółgłoski
TARGET_LUFS = -14


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("\n".join(cmd), flush=True)
        sys.exit(result.stderr[-2000:])
    return result


def probe_duration(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    return float(out.stdout.strip())


def silence(seconds: float, workdir: Path, name: str) -> Path:
    target = workdir / name
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
         "-t", f"{seconds:.3f}", str(target)])
    return target


def collect_vo(vo: Optional[Path], workdir: Path, lead: float, gap: float
               ) -> Tuple[Optional[Path], float]:
    """
    Skleja linie lektora w jedną ścieżkę. Katalog → wszystkie mp3/wav po nazwie.

    `lead` to cisza na starcie: rolka otwiera się obrazem, a nie słowem w pół sekundy —
    widz zdąży zobaczyć, na co patrzy. `gap` to oddech między zdaniami; bez niego cztery
    pliki sklejone stykiem brzmią jak czytanie listy, bo model kończy każdy z nich
    dokładnie na kropce.

    Wszystko idzie przez WAV 48 kHz: `concat` na mieszance mp3 i wav ciszy się wywala,
    a przy samych mp3 sklejka słyszalnie strzela na stykach ramek.
    """
    if not vo:
        return None, 0.0
    files = [vo] if vo.is_file() else sorted(
        p for p in vo.iterdir()
        if p.suffix.lower() in {".mp3", ".wav", ".m4a"} and not p.name.startswith("_"))
    if not files:
        sys.exit(f"brak plików lektora w {vo}")

    parts = []
    if lead > 0.01:
        parts.append(silence(lead, workdir, "lead.wav"))
    for index, source in enumerate(files):
        converted = workdir / f"line{index:02d}.wav"
        run(["ffmpeg", "-y", "-v", "error", "-i", str(source),
             "-ar", "48000", "-ac", "2", str(converted)])
        print(f"  lektor: {source.name}  {probe_duration(source):.2f} s", flush=True)
        parts.append(converted)
        if gap > 0.01 and index < len(files) - 1:
            parts.append(silence(gap, workdir, f"gap{index:02d}.wav"))

    listing = workdir / "vo.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    merged = workdir / "vo.wav"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c", "copy", str(merged)])
    return merged, probe_duration(merged)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="zmontowany materiał (dowolne proporcje)")
    ap.add_argument("--claim", required=True, help="napis na kadrze; wielkość dobiera się sama")
    ap.add_argument("--label", default="", help='pigułka, np. „ZAKOŃCZENIE PRAC” (domyślnie data)')
    ap.add_argument("--day", default="")
    ap.add_argument("--vo", default="", help="plik albo katalog z liniami lektora")
    ap.add_argument("--music", default="")
    ap.add_argument("--lead", type=float, default=0.5, help="cisza przed pierwszym zdaniem")
    ap.add_argument("--gap", type=float, default=0.3, help="oddech między zdaniami lektora")
    ap.add_argument("--stretch", action="store_true",
                    help="zwolnij obraz do długości lektora (zamiast mrozić ostatnią klatkę)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        return print("brak ffmpeg w PATH") or 1

    video = Path(args.video).expanduser()
    if not video.exists():
        sys.exit(f"nie ma pliku: {video}")
    day = date.fromisoformat(args.day) if args.day else date.today()

    workdir = Path(tempfile.mkdtemp(prefix="caption_"))
    try:
        overlay = workdir / "overlay.png"
        overlay.write_bytes(sc.render_photo_overlay(args.claim, day, args.label or None))

        video_len = probe_duration(video)
        vo_path, vo_len = collect_vo(Path(args.vo).expanduser() if args.vo else None,
                                     workdir, args.lead, args.gap)
        print(f"  wideo: {video_len:.2f} s   lektor: {vo_len:.2f} s", flush=True)

        # Lektor dłuższy niż obraz — dwie drogi wyjścia:
        #  --stretch: zwalniamy CAŁE ujęcie do długości lektora. Dobre dla ujęcia z drona,
        #     które zwolnione wygląda lepiej, nie gorzej. `minterpolate` dorabia klatki
        #     pośrednie, bo samo `setpts` przy 25 fps i zwolnieniu 1,8× daje 14 fps i widać
        #     skokowy ruch — to jedyna rzecz, która na dronie wygląda jak plik z internetu.
        #  domyślnie: przytrzymanie ostatniej klatki. Tanie, ale zamrożony kadr na kilka
        #     sekund jest widoczny, więc nadaje się tylko na krótką dopłatę czasu.
        hold = max(0.0, vo_len - video_len)
        vf = ("scale=1080:1920:force_original_aspect_ratio=increase,"
              "crop=1080:1920,setsar=1")

        if args.stretch and vo_len > video_len + 0.05:
            factor = vo_len / video_len
            print(f"  zwalniam obraz {factor:.2f}× ({video_len:.2f} s → {vo_len:.2f} s), "
                  f"z dorabianiem klatek", flush=True)
            vf += (f",setpts={factor:.6f}*PTS,"
                   f"minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:vsbmc=1")
        else:
            vf += ",fps=30"
            if hold > 0.05:
                print(f"  lektor dłuższy o {hold:.2f} s — przytrzymuję ostatnią klatkę", flush=True)
                vf += f",tpad=stop_mode=clone:stop_duration={hold:.3f}"

        cmd = ["ffmpeg", "-y", "-v", "error", "-stats", "-i", str(video), "-i", str(overlay)]
        inputs = 2
        audio_labels = []
        if vo_path:
            cmd += ["-i", str(vo_path)]
            audio_labels.append(f"{inputs}:a")
            inputs += 1
        if args.music:
            cmd += ["-i", str(Path(args.music).expanduser())]
            audio_labels.append(f"{inputs}:a")
            inputs += 1

        filters = [f"[0:v]{vf}[base]",
                   f"[base][1:v]overlay=0:0:format=auto,fade=t=in:st=0:d={FADE_IN},format=yuv420p[v]"]

        if len(audio_labels) == 2:      # lektor + muzyka
            filters.append(f"[{audio_labels[1]}]volume={MUSIC_UNDER_DB}dB,"
                           f"apad,atrim=0:{max(vo_len, video_len):.3f}[bed]")
            filters.append(f"[{audio_labels[0]}][bed]amix=inputs=2:duration=longest:normalize=0,"
                           f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11,aresample=48000[a]")
        elif audio_labels:
            filters.append(f"[{audio_labels[0]}]loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11,aresample=48000[a]")

        cmd += ["-filter_complex", ";".join(filters), "-map", "[v]"]
        if audio_labels:
            cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
        else:
            # Cicha ścieżka: część platform odrzuca upload bez audio
            cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                    "-map", f"{inputs}:a", "-c:a", "aac", "-b:a", "96k", "-shortest"]

        out_path = Path(args.out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "20",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)]
        run(cmd)

        size_mb = out_path.stat().st_size / 1024 / 1024
        print(f"\nzapisano: {out_path}  ({size_mb:.1f} MB, {probe_duration(out_path):.2f} s)",
              flush=True)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
