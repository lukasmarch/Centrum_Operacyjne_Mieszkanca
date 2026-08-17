"""
Lektor z ElevenLabs — bezpośrednio, bez Magnifica.

Po co osobny skrypt: Magnific był tylko pośrednikiem do ElevenLabs (patrz
DESIGN/brief/KAMPANIA_BRIEF.md), a jego `voiceId 144` to numer wewnętrzny, który
nic nie znaczy poza jego API. Głos „Piotrek Grabowski" jest w bibliotece
ElevenLabs, więc z własnym kluczem seria brzmi dalej tym samym głosem — i kosztuje
kredyty ElevenLabs zamiast kredytów Magnifica.

Kluczowa decyzja: KAŻDA LINIA to osobny plik. Tak samo robił Magnific i tak samo
musi zostać, bo czasy napisów w rolce bierzemy z długości plików lektora
(`ffprobe`), a nie z zegarka. Jeden plik na cały monolog = zgadywanie, w której
sekundzie zmienia się zdanie.

Fonetyka (konwencja serii, PRZEWODNIK_SCENARIUSZ.md §3): `rybnolive.pl` zapisujemy
w tekście jako „rybno lajw kropka pe el", `AI` jako „ej aj". Liczby piszemy słowami
— „4 310 925,00 zł" model czyta cyfra po cyfrze albo po angielsku.

Użycie:
    cd backend && python -u -m scripts.tts_elevenlabs --list Piotrek
    cd backend && python -u -m scripts.tts_elevenlabs --add-shared <public_owner_id> <voice_id>
    cd backend && python -u -m scripts.tts_elevenlabs \\
        --script ../DESIGN/brief/vo_droga.txt --out ../DESIGN/assets/audio/droga_1255n
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

API = "https://api.elevenlabs.io/v1"
MODEL = "eleven_multilingual_v2"          # v3 nie ma jeszcze stabilnego PL w tym endpointcie
OUTPUT_FORMAT = "mp3_44100_128"           # ffmpeg i tak przemiksuje; 128 kbps wystarcza pod obraz
# `stability` to w ElevenLabs suwak „przewidywalność ↔ ekspresja", nie jakość: wysoka
# wartość daje czytanie prognozy pogody z kartki, niska — grę aktorską i ryzyko przekręceń
# w polskich nazwach. 0,40 to lektor informacyjny, który jednak oddycha; `style` trzymamy
# nisko, bo na głosach klonowanych (`professional`) wyżej zaczyna zmieniać barwę.
VOICE_SETTINGS = {
    "stability": 0.40,
    "similarity_boost": 0.80,
    "style": 0.10,
    "use_speaker_boost": True,
}


def _key() -> str:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        sys.exit("brak ELEVENLABS_API_KEY w backend/.env")
    return key


def _headers(key: str) -> dict:
    return {"xi-api-key": key, "Content-Type": "application/json"}


def list_voices(key: str, search: str) -> int:
    """Najpierw głosy z konta, potem biblioteka publiczna — dodać trzeba tylko te drugie."""
    own = requests.get(f"{API}/voices", headers=_headers(key), timeout=30)
    own.raise_for_status()
    matches = [v for v in own.json().get("voices", [])
               if search.lower() in (v.get("name") or "").lower()]
    print(f"— na koncie ({len(matches)} trafień z {len(own.json().get('voices', []))} głosów):")
    for v in matches:
        print(f"    {v['voice_id']}  {v['name']}  [{v.get('category')}]")

    shared = requests.get(f"{API}/shared-voices",
                          headers=_headers(key),
                          params={"search": search, "page_size": 30},
                          timeout=30)
    if shared.status_code != 200:
        print(f"— biblioteka publiczna: HTTP {shared.status_code} {shared.text[:200]}")
        return 0
    voices = shared.json().get("voices", [])
    print(f"— biblioteka publiczna ({len(voices)}):")
    for v in voices:
        langs = ",".join(sorted({(l.get("language") or "?") for l in v.get("verified_languages", [])}))
        print(f"    voice_id={v['voice_id']}  owner={v.get('public_owner_id')}  "
              f"{v.get('name')}  [{v.get('gender')}, {langs or v.get('language')}]")
    return 0


def add_shared(key: str, owner: str, voice_id: str, name: str) -> int:
    r = requests.post(f"{API}/voices/add/{owner}/{voice_id}",
                      headers=_headers(key), json={"new_name": name}, timeout=60)
    print(r.status_code, r.text[:400])
    return 0 if r.ok else 1


def read_script(path: Path) -> list[tuple[str, str]]:
    """
    Plik lektora: linie `ID | tekst`, puste linie i `#` pomijane.

    ID trafia do nazwy pliku, więc kolejność w montażu jest widoczna w katalogu
    (vo-1_wstep.mp3), a nie tylko w tym pliku.
    """
    lines: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        label, _, text = raw.partition("|")
        if not text:
            label, text = f"vo-{len(lines) + 1}", label
        lines.append((re.sub(r"[^\w-]+", "_", label.strip()).strip("_"), text.strip()))
    return lines


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def synth(key: str, voice_id: str, script: Path, outdir: Path,
          settings: Optional[dict] = None) -> int:
    lines = read_script(script)
    if not lines:
        sys.exit(f"pusty skrypt: {script}")
    outdir.mkdir(parents=True, exist_ok=True)

    total_chars = sum(len(t) for _, t in lines)
    print(f"{len(lines)} linii, {total_chars} znaków ≈ {total_chars} kredytów ElevenLabs\n")

    timeline, offset = [], 0.0
    for index, (label, text) in enumerate(lines, start=1):
        target = outdir / f"{index:02d}_{label}.mp3"
        r = requests.post(
            f"{API}/text-to-speech/{voice_id}",
            headers=_headers(key),
            params={"output_format": OUTPUT_FORMAT},
            json={"text": text, "model_id": MODEL, "voice_settings": VOICE_SETTINGS},
            timeout=180,
        )
        if not r.ok:
            print(f"BŁĄD {label}: HTTP {r.status_code} {r.text[:300]}")
            return 1
        target.write_bytes(r.content)
        secs = duration(target)
        timeline.append({"file": target.name, "text": text,
                         "start": round(offset, 2), "duration": round(secs, 2)})
        print(f"  {target.name}  {secs:5.2f} s  start {offset:6.2f} s  „{text[:60]}…")
        offset += secs

    # Kartka czasów obok plików: z niej bierzemy `enable='between(t,a,b)'` dla napisów
    # w ffmpegu, więc napis nie może się rozjechać z lektorem — chyba że ktoś przemontuje
    # dźwięk i zapomni odświeżyć ten plik.
    (outdir / "timeline.json").write_text(
        json.dumps({"voice_id": voice_id, "model": MODEL, "total": round(offset, 2),
                    "lines": timeline}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nrazem {offset:.2f} s  →  {outdir}/timeline.json")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", metavar="SZUKAJ", help="wypisz głosy z konta i biblioteki")
    ap.add_argument("--add-shared", nargs=2, metavar=("OWNER", "VOICE_ID"))
    ap.add_argument("--name", default="Piotrek Grabowski", help="nazwa przy dodawaniu głosu")
    ap.add_argument("--voice", help="voice_id do syntezy")
    ap.add_argument("--script", help="plik z liniami lektora (ID | tekst)")
    ap.add_argument("--out", help="katalog wyjściowy")
    ap.add_argument("--stability", type=float, help="0,0 = ekspresyjnie, 1,0 = monotonnie")
    ap.add_argument("--style", type=float, help="podbicie stylu; na głosach klonowanych ostrożnie")
    args = ap.parse_args()

    key = _key()
    if args.list:
        return list_voices(key, args.list)
    if args.add_shared:
        return add_shared(key, args.add_shared[0], args.add_shared[1], args.name)
    if args.script and args.out and args.voice:
        settings = dict(VOICE_SETTINGS)
        if args.stability is not None:
            settings["stability"] = args.stability
        if args.style is not None:
            settings["style"] = args.style
        return synth(key, args.voice, Path(args.script).expanduser(),
                     Path(args.out).expanduser(), settings)
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
