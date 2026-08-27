"""
Sesja Rady Gminy: nagranie → transkrypt → skrót. Przebieg ręczny.

Narzędzie do oglądania wyniku okiem — ten sam kod, który codziennie o 4:30
uruchamia `scheduler/council_job.py`, tylko natychmiast i z plikami na dysku.
Przydaje się przy nadrabianiu starszych sesji i przy pracy nad promptem.

    # najnowsza sesja z galerii gminy
    cd backend && python -m scripts.run_council_session --latest

    # to samo, ale skrót ląduje w kolejce do akceptacji (mail + strona)
    python -m scripts.run_council_session --latest --save

    # konkretne nagranie
    python -m scripts.run_council_session --url "https://www.youtube.com/watch?v=6h9iKlveTcs"

    # sam skrót na już pobranym transkrypcie — zero kosztów Whispera
    python -m scripts.run_council_session --transcript out/sesja.transcript.json

Transkrypt zapisuje się obok wyników i przy kolejnym uruchomieniu jest czytany
z dysku. To celowe: iterowanie nad promptem skrótu ma kosztować tokeny gpt-4o
(grosze), a nie transkrypcję całego nagrania od nowa ($0,52 za sesję).

Audio (~40 MB) zostaje w katalogu roboczym — kasuj ręcznie, gdy skończysz.
"""
import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlmodel import select

from src.ai.council_summary import stamp_to_seconds, summarize_session
from src.scrapers.council_sessions import CouncilRecording, fetch_recordings
from src.services.council_transcript import (
    Segment,
    Transcript,
    TranscriptionError,
    download_audio,
    not_ready_reason,
    transcribe_audio,
    video_metadata,
)

DEFAULT_WORK_DIR = Path("/tmp/council_sessions")


def save_transcript(transcript: Transcript, path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "source_url": transcript.source_url,
                "duration_s": transcript.duration_s,
                "segments": [asdict(s) for s in transcript.segments],
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )


def load_transcript(path: Path) -> Transcript:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Transcript(
        segments=[Segment(**s) for s in data["segments"]],
        duration_s=data.get("duration_s", 0.0),
        source_url=data.get("source_url"),
    )


async def save_to_queue(
    result,
    transcript: Transcript,
    title: str,
    recording: Optional[CouncilRecording],
) -> Optional[str]:
    """
    Skrót → kolejka akceptacji, tak jakby zrobił go job. Zwraca adres strony
    akceptacji albo None, gdy zapis się nie udał.

    Import bazy siedzi w środku funkcji, bo bez `--save` skrypt ma działać
    na maszynie bez `DATABASE_URL` — pilot nadrabiający starą sesję nie musi
    mieć dostępu do produkcyjnego Postgresa.
    """
    from src.config import settings
    from src.database.connection import async_session
    from src.database.schema import CouncilSession, CouncilSessionStatus
    from src.services.council_store import apply_result

    if recording:
        external_id = recording.page_id
        page_url = recording.page_url
        youtube_id = recording.youtube_id
        session_date = (
            datetime.combine(recording.session_date, datetime.min.time())
            if recording.session_date else None
        )
        number = recording.session_number
    else:
        # Bez galerii nie ma `page_id`; identyfikatorem zostaje nagranie.
        # Prefiks `yt:` odróżnia to od numeru podstrony, żeby późniejszy
        # przebieg joba nie uznał tej samej sesji za nową.
        youtube_id = (transcript.source_url or "").split("v=")[-1][:11] or None
        if not youtube_id:
            print("--save wymaga nagrania z YouTube (--latest albo --url)", file=sys.stderr)
            return None
        external_id, page_url, session_date, number = f"yt:{youtube_id}", "", None, None

    async with async_session() as session:
        row = (await session.execute(
            select(CouncilSession).where(CouncilSession.external_id == external_id)
        )).scalars().first()

        # Ten sam film to ta sama sesja — nawet gdy identyfikatory się nie zgadzają.
        # `--transcript` nie zna `page_id` z galerii, więc identyfikatorem zostaje
        # `yt:<id>`; bez tego dopasowania nadrobienie sesji z gotowego transkryptu
        # zakładało DRUGI wiersz obok tego, który job wpisał z galerii, a job wracał
        # potem po ten pierwszy i przepisywał nagranie po raz kolejny. Ścieżka przez
        # transkrypt jest regułą, dopóki produkcja nie ma dostępu do YouTube
        # (bot-check na IP serwera, 27.08.2026).
        if row is None and youtube_id:
            row = (await session.execute(
                select(CouncilSession).where(CouncilSession.youtube_id == youtube_id)
            )).scalars().first()
            if row:
                print(f"Dopasowano po nagraniu do sesji {row.external_id} ({row.status}).")

        if row is None:
            row = CouncilSession(external_id=external_id, title=title, page_url=page_url)
            row.session_number = number
            row.session_date = session_date
            row.youtube_id = youtube_id
        elif row.status == CouncilSessionStatus.PUBLISHED.value:
            print(f"Sesja {external_id} jest już opublikowana — nie nadpisuję.", file=sys.stderr)
            return None

        apply_result(row, transcript, result)
        session.add(row)
        await session.commit()
        token = row.review_token

    return f"{settings.API_URL}/api/council/review/{token}"


def render_markdown(result, transcript: Transcript, title: str, recording: Optional[CouncilRecording]) -> str:
    """Skrót w postaci, w jakiej trafiłby na stronę — do oceny okiem."""
    summary = result.summary
    lines = [f"# {summary.headline}", "", summary.lead, ""]

    if not summary.is_substantive:
        lines += ["> Sesja formalna — model uznał, że nie ma czego streszczać.", ""]

    lines += ["## Co ustalono", ""]
    for point in summary.points:
        link = recording.watch_url_at(stamp_to_seconds(point.timestamp) or 0) if recording else None
        stamp = f"[{point.timestamp}]({link})" if link else point.timestamp
        lines.append(f"### {point.title}")
        lines.append(f"*{stamp}*" + (f" — **{point.speaker}**" if point.speaker else ""))
        lines.append("")
        lines.append(point.description)
        if point.quote:
            lines.append("")
            lines.append(f"> „{point.quote}”")
        lines.append("")

    if summary.resolutions:
        lines += ["## Uchwały", ""]
        for res in summary.resolutions:
            bits = [res.number, res.subject, res.outcome, res.timestamp]
            lines.append("- " + " — ".join(b for b in bits if b))
        lines.append("")

    lines += [
        "---",
        f"Źródło: [{title}]({transcript.source_url})" if transcript.source_url else f"Źródło: {title}",
        f"Nagranie: {transcript.duration_s / 60:.0f} min · transkrypt {len(transcript.text)} znaków",
        "Skrót wygenerowany automatycznie na podstawie nagrania obrad.",
    ]
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Pilot: skrót sesji Rady Gminy")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="Adres nagrania (YouTube)")
    source.add_argument("--latest", action="store_true", help="Najnowsza sesja z galerii gminy")
    source.add_argument("--transcript", type=Path, help="Gotowy transkrypt JSON (bez kosztu Whispera)")
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR, help="Katalog na audio i wyniki")
    parser.add_argument("--name", default=None, help="Nazwa plików wynikowych")
    parser.add_argument("--save", action="store_true",
                        help="Zapisz skrót do kolejki akceptacji (tabela council_sessions)")
    args = parser.parse_args()

    work_dir: Path = args.work_dir
    work_dir.mkdir(parents=True, exist_ok=True)

    recording: Optional[CouncilRecording] = None
    title = "Sesja Rady Gminy Rybno"

    # --- skąd bierzemy transkrypt -------------------------------------------
    if args.transcript:
        transcript = load_transcript(args.transcript)
        name = args.name or args.transcript.stem.replace(".transcript", "")
        print(f"Transkrypt z pliku: {len(transcript.segments)} segmentów, "
              f"{transcript.duration_s / 60:.0f} min — Whisper pominięty")
    else:
        if args.latest:
            recordings = [r for r in await fetch_recordings(limit=6) if r.youtube_id]
            if not recordings:
                print("Galeria gminy nie ma sesji z dostępnym nagraniem.", file=sys.stderr)
                return 1
            recording = recordings[0]
            url, title = recording.video_url, recording.title
            name = args.name or f"sesja_{recording.page_id}"
        else:
            url = args.url
            name = args.name or "sesja"

        # Bramka transmisji dotyczy OBU ścieżek. Galeria dostaje adres nagrania
        # przed obradami, więc `--latest` w dniu sesji trafia na zapowiedź —
        # bez tego sprawdzenia yt-dlp próbowałby pobrać strumień, którego nie ma.
        meta = video_metadata(url)
        if not args.latest:
            title = meta["title"]
        waiting = not_ready_reason(meta)
        if waiting:
            print(f"Nagranie jeszcze nie do przepisania: {waiting}", file=sys.stderr)
            return 1

        print(f"Nagranie: {title}\n{url}")
        audio = download_audio(url, work_dir, name=name)
        transcript = await transcribe_audio(audio, source_url=url)
        transcript_path = work_dir / f"{name}.transcript.json"
        save_transcript(transcript, transcript_path)
        print(f"Transkrypt zapisany: {transcript_path} (Whisper ~${transcript.whisper_cost_usd:.3f})")

    if not transcript.segments:
        print("Transkrypt pusty — nagranie bez mowy?", file=sys.stderr)
        return 1

    # --- skrót ---------------------------------------------------------------
    result = await summarize_session(transcript, session_title=title)
    quality = result.quality

    text_path = work_dir / f"{name}.transcript.txt"
    text_path.write_text(transcript.stamped_text(), encoding="utf-8")

    markdown = render_markdown(result, transcript, title, recording)
    summary_path = work_dir / f"{name}.skrot.md"
    summary_path.write_text(markdown, encoding="utf-8")

    print("\n" + "=" * 72)
    print(markdown)
    print("=" * 72)
    print(f"\nJAKOŚĆ: {quality.describe()}")
    print(f"Publikowalny bez ręcznej kontroli: {'TAK' if quality.publishable else 'NIE'}")
    if quality.quotes_dropped:
        print("\nCytaty usunięte jako niepotwierdzone w nagraniu:")
        for dropped in quality.quotes_dropped:
            print(f"  - {dropped}")
    print(f"\nKoszt skrótu: ${result.cost_usd:.4f} "
          f"({result.tokens_input} tok. wejścia / {result.tokens_output} wyjścia)")
    print(f"Pliki: {summary_path}\n       {text_path}")

    if args.save:
        review_url = await save_to_queue(result, transcript, title, recording)
        if not review_url:
            return 1
        print(f"\nSkrót czeka na akceptację: {review_url}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except TranscriptionError as exc:
        print(f"BŁĄD: {exc}", file=sys.stderr)
        raise SystemExit(1)
