"""
Job sesji Rady Gminy — codziennie 4:30 (2026-08-09)

Sprawdza galerię nagrań gminy, a gdy pojawi się nowa sesja: pobiera audio,
przepisuje je Whisperem, robi skrót i **zostawia go w stanie `pending`**.
Publikacji nie ma — jest wiadomość na Telegramie (zapasowo mail) z linkiem
do strony akceptacji.

**Dlaczego job nie publikuje sam.** Bramka w `ai/council_summary` weryfikuje
cytaty i naprawdę je wycina, gdy ich w nagraniu nie ma. Ale `description`
punktu nie przechodzi żadnej kontroli i na pilotażowej sesji XXIII model dopisał
tam cel zagospodarowania działki, którego nikt nie wypowiedział. Do tego skrót
bywa niestabilny redakcyjnie: dwa przebiegi na tym samym transkrypcie raz
zawierały wątek personalny z imiennym zarzutem wobec wójta, raz pomijały go
w całości. Pięć minut czytania raz w miesiącu kosztuje mniej niż jedno zdanie
przypisane radnemu, którego nie powiedział.

**Rytm i koszt.** Sesja zdarza się ~raz w miesiącu, z przerwą wakacyjną — przez
większość dni job nie znajduje nic nowego i to jest stan normalny, nie awaria.
Jedno nagranie na przebieg (`MAX_SESSIONS_PER_RUN`), bo Whisper kosztuje ~$0,52
za sesję i nadrabianie zaległości nie może wystawić rachunku bez ostrzeżenia.

Przebieg ręczny (ten sam kod, natychmiast):
    cd backend && python -m scripts.run_council_session --latest --save
"""
import asyncio
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from src.ai.council_summary import summarize_session
from src.config import settings
from src.database.schema import CouncilSession, CouncilSessionStatus
from src.scrapers.council_sessions import CouncilRecording, fetch_recordings
from src.services.council_store import apply_result, summary_dict
from src.services.council_transcript import (
    TranscriptionError,
    download_audio,
    not_ready_reason,
    transcribe_audio,
    video_metadata,
)
from src.utils.logger import setup_logger

logger = setup_logger("CouncilJob")

# Ile nagrań przepisujemy w jednym przebiegu. Jeden: transkrypcja to ~$0,52,
# a galeria potrafi wypełnić się kilkoma sesjami naraz po przerwie wakacyjnej.
MAX_SESSIONS_PER_RUN = 1

# Ile razy wracamy do nagrania, które się nie udało. Powyżej tego wiersz zostaje
# w `error` i czeka na człowieka — codzienne dobijanie się do zepsutego pliku
# przez pół roku to same koszty i szum w logach.
MAX_ATTEMPTS = 3

# Sesja Rady trwa do trzech godzin. Dłuższe nagranie w galerii to albo pomyłka
# gminy, albo coś innego niż obrady — a Whisper liczy sobie za minutę, więc
# ograniczenie działa jak bezpiecznik rachunku, nie jak filtr treści.
MAX_SESSION_MINUTES = 240

# Ile nagrań z galerii oglądamy przy każdym przebiegu. Sesje wchodzą po jednej
# w miesiącu, więc sześć to zapas na kilka miesięcy przestoju joba.
GALLERY_LIMIT = 6

# Po ilu dniach sesja przestaje być wiadomością. Galeria trzyma nagrania lata
# wstecz i przy pierwszym uruchomieniu job zobaczył sześć nieznanych sesji —
# bez tego progu ruszyłby sześciodniowe nadrabianie za ~$3,50 i wysłał adminowi
# maila o obradach z grudnia. Starsze nagrania zostają w tabeli w stanie `new`:
# są zapisem tego, co znamy, i punktem wyjścia do ręcznego nadrobienia
# (`run_council_session --url ... --save`), ale job sam po nie nie sięgnie.
MAX_SESSION_AGE_DAYS = 45


async def _sync_gallery(session: AsyncSession) -> int:
    """
    Galeria → wiersze w stanie `new`. Nic nie pobiera i nic nie kosztuje;
    zwraca liczbę nagrań, których wcześniej nie widzieliśmy.
    """
    recordings: List[CouncilRecording] = await fetch_recordings(limit=GALLERY_LIMIT)
    known = set(
        (await session.execute(select(CouncilSession.external_id))).scalars().all()
    )

    added = 0
    for recording in recordings:
        if recording.page_id in known or not recording.youtube_id:
            continue
        session.add(CouncilSession(
            external_id=recording.page_id,
            title=recording.title,
            session_number=recording.session_number,
            session_date=(
                datetime.combine(recording.session_date, datetime.min.time())
                if recording.session_date else None
            ),
            page_url=recording.page_url,
            youtube_id=recording.youtube_id,
            status=CouncilSessionStatus.NEW.value,
        ))
        added += 1
        logger.info("Nowa sesja w galerii: %s (%s)", recording.title, recording.page_id)

    if added:
        await session.commit()
    return added


async def _next_to_process(session: AsyncSession) -> List[CouncilSession]:
    """
    Nagrania czekające na transkrypcję — najnowsze najpierw, tylko świeże.

    Sesja bez daty w tytule przechodzi: brak daty zdarza się przy literówce
    w galerii, a odrzucanie obrad z powodu formatu tytułu byłoby gorsze niż
    jeden skrót do przejrzenia za dużo.
    """
    cutoff = datetime.utcnow() - timedelta(days=MAX_SESSION_AGE_DAYS)
    rows = (await session.execute(
        select(CouncilSession)
        .where(CouncilSession.status.in_([
            CouncilSessionStatus.NEW.value,
            CouncilSessionStatus.ERROR.value,
        ]))
        .where(CouncilSession.attempts < MAX_ATTEMPTS)
        .where(
            (CouncilSession.session_date == None)  # noqa: E711
            | (CouncilSession.session_date >= cutoff)
        )
        .order_by(CouncilSession.session_date.desc().nullslast(), CouncilSession.id.desc())
    )).scalars().all()
    return list(rows)[:MAX_SESSIONS_PER_RUN]


async def _process(session: AsyncSession, row: CouncilSession, work_dir: Path) -> bool:
    """
    Jedno nagranie: audio → transkrypt → skrót → `pending`.
    Zwraca True, gdy skrót czeka na akceptację.
    """
    url = f"https://www.youtube.com/watch?v={row.youtube_id}"

    # Metadane PRZED podbiciem próby. Gmina wystawia adres nagrania w galerii
    # z wyprzedzeniem — 26.08.2026 wpis o sesji XXIV prowadził do transmisji
    # zaplanowanej na następny dzień. Zapowiedź nie jest awarią: wiersz zostaje
    # w `new` i job wróci po niego jutro, zamiast wypalić trzy próby na obradach,
    # które się jeszcze nie odbyły.
    try:
        meta = video_metadata(url)
    except Exception as exc:  # noqa: BLE001 — nieczytelne metadane to już awaria
        return await _fail(session, row, exc, counted=True)

    waiting = not_ready_reason(meta)
    if waiting:
        logger.info("Sesja %s czeka: %s", row.external_id, waiting)
        return False

    row.attempts += 1
    row.status = CouncilSessionStatus.PROCESSING.value
    session.add(row)
    await session.commit()

    try:
        minutes = meta["duration_s"] / 60
        if minutes > MAX_SESSION_MINUTES:
            raise TranscriptionError(
                f"Nagranie trwa {minutes:.0f} min (limit {MAX_SESSION_MINUTES}) — "
                f"przepisz ręcznie, jeśli to naprawdę obrady"
            )

        logger.info("Przepisuję: %s (%.0f min)", row.title, minutes)
        audio = download_audio(url, work_dir, name=f"sesja_{row.external_id}")
        transcript = await transcribe_audio(audio, source_url=url)
        if not transcript.segments:
            raise TranscriptionError("Transkrypt pusty — nagranie bez mowy?")

        result = await summarize_session(transcript, session_title=row.title)
        apply_result(row, transcript, result)
        session.add(row)
        await session.commit()

        logger.info(
            "Skrót gotowy do akceptacji: %s | %d punktów | %s | $%.2f",
            row.title, len(result.summary.points), result.quality.describe(), row.cost_usd,
        )
        return True

    except Exception as exc:  # noqa: BLE001 — każdy błąd ma zostawić ślad w wierszu
        return await _fail(session, row, exc)


async def _fail(
    session: AsyncSession,
    row: CouncilSession,
    exc: Exception,
    counted: bool = False,
) -> bool:
    """Wiersz w `error` ze śladem po awarii. `counted` podbija próbę za wołającego."""
    if counted:
        row.attempts += 1
    row.status = CouncilSessionStatus.ERROR.value
    row.last_error = str(exc)[:1000]
    session.add(row)
    await session.commit()
    logger.error(
        "Sesja %s nie przeszła (próba %d/%d): %s",
        row.external_id, row.attempts, MAX_ATTEMPTS, exc,
    )
    return False


def _scrub_token(text: str) -> str:
    """
    Wycina token bota z tekstu błędu.

    httpx wkleja do treści wyjątku pełny adres żądania, a token siedzi w ścieżce
    (`/bot<TOKEN>/sendMessage`) — bez tego `logger.error(exc)` zapisywał sekret
    do `logs/scheduler.log` przy każdej nieudanej wysyłce. Wyszło przy pierwszym
    teście 9.08.2026.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    return text.replace(token, "***") if token else text


def _is_public_url(url: str) -> bool:
    """
    Czy adres nadaje się na przycisk w Telegramie.

    Telegram odrzuca całą wiadomość (400, „Wrong HTTP URL"), gdy przycisk
    prowadzi na localhost — a to jest domyślny `API_URL` w dewelopmencie.
    Bez tej bramki programista traci powiadomienie w całości zamiast dostać je
    bez przycisku.
    """
    return not any(
        marker in url for marker in ("localhost", "127.0.0.1", "0.0.0.0", "://192.168.")
    )


def _notify_telegram(row: CouncilSession) -> bool:
    """
    Telegram: skrót czeka, oto przycisk. Zwraca True, gdy poszło.

    **Jeden przycisk, nie trzy.** Przycisk inline w Telegramie to zwykły link,
    czyli GET — a GET nie może niczego publikować, bo podglądy linków w Telegramie
    i skanery odwiedzają adresy same z siebie. Przycisk prowadzi więc na stronę
    akceptacji, gdzie decyzja idzie POST-em. Kusi, żeby dać „✅ Publikuj" wprost
    w czacie; to jest dokładnie ta pułapka, o którą rozbił się kiedyś wypis
    z newslettera.
    """
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        return False

    try:
        import httpx

        summary = summary_dict(row)
        review_url = f"{settings.API_URL}/api/council/review/{row.review_token}"
        when = row.session_date.strftime("%d.%m.%Y") if row.session_date else "—"
        points = summary.get("points", [])

        lines = [
            "🏛 Skrót sesji Rady do akceptacji",
            "",
            summary.get("headline", row.title),
            f"{row.session_number or 'Sesja'} · {when} · {row.duration_s / 60:.0f} min nagrania",
            "",
            summary.get("lead", ""),
            "",
        ]
        # Sam nagłówek nie wystarcza do decyzji, a pełne opisy nie zmieszczą się
        # w wiadomości — tytuły punktów mówią, czy skrót w ogóle trafił w temat.
        lines += [f"• {p.get('title', '')}" for p in points[:6]]
        lines += [
            "",
            f"cytaty {row.quotes_verified}/{row.quotes_total} · "
            f"zdania bez zastrzeżeń {row.claims_total - row.claims_flagged}/{row.claims_total} · "
            f"${row.cost_usd:.2f}",
        ]
        if row.quotes_dropped or row.claims_flagged:
            lines.append(
                f"⚠️ {row.quotes_dropped} cytat(ów) usuniętych, {row.claims_flagged} "
                f"zdanie(a) do sprawdzenia — lista na stronie"
            )
        lines += [
            "",
            "Cytaty sprawdzone twardo. Opisy tylko zakreślone — przeczytaj.",
        ]
        payload = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            # Bez parse_mode: treść pochodzi od modelu i potrafi zawierać
            # niedomknięte * albo _, na czym Telegram wywala 400.
            "disable_web_page_preview": True,
        }
        if _is_public_url(review_url):
            payload["reply_markup"] = {"inline_keyboard": [[
                {"text": "📋 Przeczytaj i zdecyduj", "url": review_url}
            ]]}
        else:
            lines += ["", review_url]

        # Limit wiadomości na Telegramie to 4096 znaków; skrót bywa dłuższy.
        payload["text"] = "\n".join(lines)[:3900]

        response = httpx.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=20.0,
        )
        response.raise_for_status()
        logger.info("Skrót podany do akceptacji na Telegramie (czat %s)", settings.TELEGRAM_CHAT_ID)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Telegram nie przyjął powiadomienia o skrócie: %s", _scrub_token(str(exc)))
        return False


def _notify_admin(row: CouncilSession) -> None:
    """
    Skrót czeka — powiadom człowieka. Bez tego cała bramka akceptacji jest
    martwa, bo nikt nie zagląda do bazy z ciekawości.

    Telegram jest kanałem pierwszym (tam admin akceptuje posty na FB, więc tam
    patrzy), mail zapasowym. Oba naraz to ta sama decyzja podana dwa razy —
    dlatego mail idzie tylko wtedy, gdy Telegram nie zadziałał.

    SYNC i połyka wyjątki: niedostarczone powiadomienie nie może cofnąć skrótu.
    """
    if _notify_telegram(row):
        return

    if not settings.ADMIN_ALERT_EMAIL or not settings.RESEND_API_KEY:
        logger.warning(
            "Skrót sesji czeka na akceptację, ale brak ADMIN_ALERT_EMAIL/RESEND_API_KEY "
            "— link: %s/api/council/review/%s", settings.API_URL, row.review_token,
        )
        return

    try:
        import resend as resend_lib

        summary = summary_dict(row)
        review_url = f"{settings.API_URL}/api/council/review/{row.review_token}"
        when = row.session_date.strftime("%d.%m.%Y") if row.session_date else "—"
        points = len(summary.get("points", []))

        resend_lib.api_key = settings.RESEND_API_KEY
        resend_lib.Emails.send({
            "from": f"{settings.NEWSLETTER_FROM_NAME} <{settings.NEWSLETTER_FROM_EMAIL}>",
            "to": [settings.ADMIN_ALERT_EMAIL],
            "subject": f"Skrót sesji Rady do akceptacji — {row.title}",
            "html": f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="margin:0;background:#020617;color:#fafafa;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
  <div style="max-width:520px;margin:0 auto;padding:56px 24px;">
    <div style="font-size:21px;font-weight:800;">Rybno<span style="color:#91c5ff;">Live</span></div>
    <div style="margin-top:28px;background:#0d1117;border:1px solid #1f2937;
                border-radius:20px;padding:26px;">
      <h1 style="margin:0;font-size:21px;line-height:28px;">{summary.get('headline', row.title)}</h1>
      <p style="margin:12px 0 0;font-size:14px;line-height:22px;color:#9ca3af;">
        {row.title} · {when} · {points} punktów ·
        cytaty {row.quotes_verified}/{row.quotes_total} potwierdzone ·
        koszt ${row.cost_usd:.2f}
      </p>
      <p style="margin:18px 0 0;font-size:15px;line-height:23px;color:#d1d5db;">
        {summary.get('lead', '')}
      </p>
      <a href="{review_url}"
         style="display:inline-block;margin-top:22px;background:#3a81f6;color:#fff;
                text-decoration:none;font-weight:600;padding:13px 24px;border-radius:12px;">
        Przeczytaj i zdecyduj
      </a>
      <p style="margin:18px 0 0;font-size:12.5px;line-height:19px;color:#6b7280;">
        Otwarcie linku niczego nie publikuje. Skrót pojawi się w serwisie dopiero
        po kliknięciu przycisku na tej stronie.
      </p>
    </div>
  </div>
</body></html>""",
        })
        logger.info("Powiadomienie o skrócie wysłane → %s", settings.ADMIN_ALERT_EMAIL)
    except Exception as exc:  # noqa: BLE001
        logger.error("Nie udało się powiadomić admina o skrócie sesji: %s", exc)


async def run_council_job_async() -> None:
    """Główny przebieg — wywoływany przez scheduler."""
    logger.info("Start job: sesje Rady Gminy")
    work_dir = Path(tempfile.gettempdir()) / "council_sessions"
    work_dir.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as session:
            added = await _sync_gallery(session)
            pending = await _next_to_process(session)

            if not pending:
                # Sesja raz w miesiącu — brak nowego nagrania to normalny dzień.
                logger.info("Brak nagrań do przepisania (nowych w galerii: %d)", added)
                return

            for row in pending:
                if await _process(session, row, work_dir):
                    _notify_admin(row)
    finally:
        await engine.dispose()
        # Audio to ~30 MB na sesję i nie jest już do niczego potrzebne —
        # transkrypt siedzi w bazie.
        shutil.rmtree(work_dir, ignore_errors=True)

    logger.info("Job zakończony")


def run_council_job() -> None:
    """Synchroniczna otoczka dla APScheduler."""
    asyncio.run(run_council_job_async())
