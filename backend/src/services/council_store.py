"""
Skrót sesji Rady w bazie — zapis, odczyt i strona akceptacji.

Warstwa między pipeline'em (`services/council_transcript` + `ai/council_summary`)
a tym, co widzi człowiek. Trzy rzeczy, których nie ma sensu trzymać ani w jobie,
ani w endpointach, bo używają ich oba:

1. **Transkrypt ↔ JSON.** Segmenty ze znacznikami czasu zostają w bazie na stałe.
   Bez nich cytat przypisany radnemu jest nieweryfikowalny, a przepisanie
   nagrania od nowa kosztuje $0,52.
2. **Skrót → słownik dla API** z gotowym linkiem `?t=` pod każdym punktem.
3. **Strona akceptacji.** Renderowana po stronie backendu, bo skrót ma leżeć
   w bazie i czekać, zanim powstanie strona `/rada` — a czekać musi na
   człowieka, którego nie da się poprosić o czytanie JSON-a w curlu.

**Dlaczego akceptacja idzie tokenem z maila, a nie samym JWT admina.**
Sesja Rady zdarza się raz w miesiącu. Gdyby zatwierdzenie wymagało zalogowania
się do panelu, którego jeszcze nie ma, skrót leżałby tygodniami. Token to ten
sam wzorzec co wypis z newslettera — z tą samą pułapką: **GET nie może niczego
zmieniać**, bo skanery pocztowe odwiedzają linki z wiadomości. Publikacja
następuje dopiero po kliknięciu przycisku (POST).
"""
import html
import json
import secrets
from datetime import datetime
from typing import List, Optional

from dataclasses import asdict

from src.ai.council_summary import CouncilSummaryResult, stamp_to_seconds
from src.database.schema import CouncilSession, CouncilSessionStatus
from src.services.council_transcript import Segment, Transcript
from src.utils.logger import setup_logger

logger = setup_logger("CouncilStore")


# ---------------------------------------------------------------- transkrypt

def transcript_to_json(transcript: Transcript) -> str:
    return json.dumps(
        {
            "source_url": transcript.source_url,
            "duration_s": transcript.duration_s,
            "segments": [asdict(s) for s in transcript.segments],
        },
        ensure_ascii=False,
    )


def transcript_from_json(raw: str) -> Transcript:
    data = json.loads(raw)
    return Transcript(
        segments=[Segment(**s) for s in data.get("segments", [])],
        duration_s=data.get("duration_s", 0.0),
        source_url=data.get("source_url"),
    )


# ---------------------------------------------------------------------- zapis

def apply_result(
    row: CouncilSession,
    transcript: Transcript,
    result: CouncilSummaryResult,
) -> CouncilSession:
    """
    Wynik pipeline'u → wiersz w stanie `pending`. Nie commituje — o transakcji
    decyduje wołający (job robi to raz, po zapisaniu wszystkiego).

    Token akceptacyjny powstaje tutaj, a nie przy tworzeniu wiersza: dopóki nie
    ma czego akceptować, ważny link do akceptacji jest tylko powierzchnią ataku.
    """
    quality = result.quality

    row.duration_s = transcript.duration_s
    row.transcript_chars = len(transcript.text)
    row.transcript_json = transcript_to_json(transcript)
    row.summary_json = result.summary.model_dump_json()

    row.quotes_total = quality.quotes_total
    row.quotes_verified = quality.quotes_verified
    row.quotes_dropped = len(quality.quotes_dropped)
    row.timestamps_fixed = quality.timestamps_fixed
    row.claims_total = quality.claims_total
    row.claims_flagged = len(quality.claims_flagged)
    # Treść oznaczonych zdań wraz z powodem, nie tylko licznik: sam licznik
    # („2 zdania") nauczy admina klikać na ślepo, a zdanie z uzasadnieniem
    # pokazuje, czego szukać w nagraniu i w czym model konfabuluje.
    row.claims_flagged_text = (
        json.dumps(quality.claims_flagged, ensure_ascii=False)
        if quality.claims_flagged else None
    )
    row.quotes_clean = quality.publishable

    row.cost_usd = round(transcript.whisper_cost_usd + result.cost_usd, 4)
    row.status = CouncilSessionStatus.PENDING.value
    row.review_token = row.review_token or secrets.token_urlsafe(32)
    row.last_error = None
    row.processed_at = datetime.utcnow()
    return row


# --------------------------------------------------------------------- odczyt

def watch_url(row: CouncilSession, stamp: Optional[str] = None) -> Optional[str]:
    """Adres nagrania, opcjonalnie z przewinięciem do znacznika."""
    if not row.youtube_id:
        return None
    base = f"https://www.youtube.com/watch?v={row.youtube_id}"
    seconds = stamp_to_seconds(stamp)
    return f"{base}&t={int(seconds)}s" if seconds is not None else base


def summary_dict(row: CouncilSession) -> dict:
    """
    Skrót w postaci, w jakiej wychodzi z API: punkty z gotowym linkiem do minuty
    nagrania. Pusty słownik, gdy skrótu jeszcze nie ma — to normalny stan wiersza
    świeżo wykrytego przez joba, nie błąd.
    """
    if not row.summary_json:
        return {}
    data = json.loads(row.summary_json)
    for point in data.get("points", []):
        point["watch_url"] = watch_url(row, point.get("timestamp"))
    for resolution in data.get("resolutions", []):
        resolution["watch_url"] = watch_url(row, resolution.get("timestamp"))
    return data


def public_payload(row: CouncilSession, with_summary: bool = True) -> dict:
    """Wiersz → odpowiedź publicznego endpointu (bez transkryptu i bez tokenu)."""
    payload = {
        "id": row.id,
        "title": row.title,
        "session_number": row.session_number,
        "session_date": row.session_date.date().isoformat() if row.session_date else None,
        "page_url": row.page_url,
        "video_url": watch_url(row),
        "duration_min": round(row.duration_s / 60) if row.duration_s else None,
        "published_at": row.published_at.isoformat() if row.published_at else None,
    }
    if with_summary:
        payload["summary"] = summary_dict(row)
    return payload


# ------------------------------------------------------- strona akceptacji

_PAGE_CSS = """
  body { margin:0; background:#020617; color:#fafafa;
         font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif; }
  .wrap { max-width:680px; margin:0 auto; padding:48px 20px 72px; }
  .brand { font-size:21px; font-weight:800; letter-spacing:-0.4px; }
  .brand span { color:#91c5ff; }
  .card { margin-top:24px; background:#0d1117; border:1px solid #1f2937;
          border-radius:20px; padding:24px; }
  h1 { margin:0 0 6px; font-size:24px; line-height:31px; letter-spacing:-0.4px; }
  .meta { font-size:13px; color:#6b7280; }
  .lead { margin:14px 0 0; font-size:15px; line-height:24px; color:#d1d5db; }
  .warn { margin-top:18px; padding:14px 16px; border-radius:14px;
          background:#231a05; border:1px solid #78560c; font-size:13.5px;
          line-height:21px; color:#fbe6a2; }
  .stat { display:inline-block; margin:0 16px 0 0; font-size:13px; color:#9ca3af; }
  .stat b { color:#fafafa; font-variant-numeric:tabular-nums; }
  .cut { margin-top:16px; padding:14px 16px; border-radius:14px;
         background:#1e0f10; border:1px solid #7f2b2b; font-size:13.5px;
         line-height:21px; color:#f3c8c8; }
  .cut ul { margin:8px 0 0; padding-left:20px; }
  .cut li { margin:4px 0; }
  .point { padding:18px 0; border-top:1px solid #1f2937; }
  .point h2 { margin:0 0 4px; font-size:16.5px; line-height:23px; }
  .point p { margin:8px 0 0; font-size:14.5px; line-height:23px; color:#c9ced6; }
  .stamp { font-size:12.5px; font-variant-numeric:tabular-nums; }
  .stamp a { color:#91c5ff; text-decoration:none; }
  .speaker { font-size:12.5px; color:#6b7280; }
  blockquote { margin:10px 0 0; padding:10px 14px; border-left:3px solid #3a81f6;
               background:#0b1220; border-radius:0 10px 10px 0;
               font-size:14px; line-height:22px; color:#dbe4f0; }
  .res { font-size:14px; line-height:22px; color:#c9ced6; margin:6px 0; }
  .actions { margin-top:28px; display:flex; gap:12px; flex-wrap:wrap; }
  button { font:inherit; font-size:15px; font-weight:600; border:0; cursor:pointer;
           padding:14px 26px; border-radius:12px; }
  .go { background:#3a81f6; color:#fff; }
  .no { background:transparent; color:#f3a2a2; border:1px solid #7f2b2b; }
  .foot { margin-top:22px; font-size:12.5px; color:#525252; line-height:20px; }
"""


def _page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{_PAGE_CSS}</style></head>
<body><div class="wrap">
  <div class="brand">Rybno<span>Live</span></div>
  {body}
</div></body></html>"""


def render_message(title: str, body: str) -> str:
    """Krótka strona bez skrótu — token zużyty, sesja odrzucona, coś nie gra."""
    return _page(
        title,
        f'<div class="card"><h1>{html.escape(title)}</h1>'
        f'<p class="lead">{html.escape(body)}</p></div>',
    )


def flagged_claims(row: CouncilSession) -> List[str]:
    """Zdania, które bramka wycięła z opisów. Puste, gdy wszystko miało pokrycie."""
    if not row.claims_flagged_text:
        return []
    try:
        return json.loads(row.claims_flagged_text)
    except (ValueError, TypeError):
        return []


def _render_dropped(row: CouncilSession) -> str:
    """
    Co maszyna wycięła — pokazane wprost, nie schowane w liczniku.

    Admin, który widzi „usunięto 2 zdania", nauczy się to klikać na ślepo.
    Admin, który czyta „działka zostanie zagospodarowana na cele rekreacyjne",
    wie, czego szukać w kolejnym skrócie.
    """
    dropped = flagged_claims(row)
    if not dropped and not row.quotes_dropped:
        return ""

    items = "".join(f"<li>{html.escape(s)}</li>" for s in dropped)
    quotes_note = (
        f"<p style='margin:10px 0 0'>Usunięto też <b>{row.quotes_dropped}</b> "
        f"cytat(y), których nie ma w nagraniu.</p>" if row.quotes_dropped else ""
    )
    return (
        '<div class="cut"><b>Do sprawdzenia w nagraniu:</b>'
        f'<ul>{items}</ul>{quotes_note}'
        '<p style="margin:10px 0 0">Te zdania ZOSTAŁY w skrócie — maszyna tylko '
        'je zakreśliła. Posłuchaj i albo popraw ręcznie, albo odrzuć skrót.</p></div>'
    )


def render_review_page(row: CouncilSession, action_url: str) -> str:
    """
    Skrót do przeczytania i dwa przyciski. Znacznik przy każdym punkcie jest
    linkiem do sekundy w nagraniu — to jedyny sposób, żeby sprawdzić opis
    w kilka sekund zamiast oglądać trzy godziny obrad.
    """
    summary = summary_dict(row)
    when = row.session_date.strftime("%d.%m.%Y") if row.session_date else "data nieznana"
    duration = f"{row.duration_s / 60:.0f} min" if row.duration_s else "—"
    # Tytuł z galerii brzmi „XXIII Sesja Rady Gminy Rybno z dnia 24.06.2026 r." —
    # wstawiony obok daty powtarza ją drugi raz. Bierzemy sam numer.
    which = f"Sesja {row.session_number}" if row.session_number else html.escape(row.title)

    parts: List[str] = [
        '<div class="card">',
        f'<h1>{html.escape(summary.get("headline", row.title))}</h1>',
        f'<div class="meta">{which} · {when} · nagranie {duration}</div>',
        f'<p class="lead">{html.escape(summary.get("lead", ""))}</p>',
    ]

    if not summary.get("is_substantive", True):
        parts.append(
            '<div class="warn">Model uznał sesję za czysto formalną — '
            'sprawdź, czy w ogóle jest co publikować.</div>'
        )

    # Sedno bramki: maszyna sprawdziła cytaty i zdania opisów wobec nagrania,
    # ale NIE sprawdziła doboru tematów ani zdań niejednoznacznych.
    parts.append(
        '<div class="warn"><b>Cytaty są sprawdzone twardo</b> — zmyślonego nie ma '
        'w skrócie, bo wyszukiwanie w transkrypcie albo znajduje frazę, albo nie. '
        '<b>Opisy są tylko zakreślone</b>: podejrzane zdania ZOSTAJĄ w treści, '
        'ich lista jest niżej. Nie sprawdzono doboru spraw ani nazw miejscowości '
        '(transkrypcja kaleczy je fonetycznie). Decyzja należy do Ciebie.</div>'
    )

    parts.append(
        '<div style="margin-top:16px">'
        f'<span class="stat">cytaty potwierdzone <b>{row.quotes_verified}/{row.quotes_total}</b></span>'
        f'<span class="stat">zdania z pokryciem '
        f'<b>{row.claims_total - row.claims_flagged}/{row.claims_total}</b></span>'
        f'<span class="stat">znaczniki poprawione <b>{row.timestamps_fixed}</b></span>'
        f'<span class="stat">koszt <b>${row.cost_usd:.2f}</b></span>'
        '</div>'
    )

    parts.append(_render_dropped(row))

    for point in summary.get("points", []):
        link = point.get("watch_url")
        stamp = html.escape(point.get("timestamp") or "")
        stamp_html = f'<a href="{link}" target="_blank" rel="noopener">{stamp}</a>' if link else stamp
        speaker = point.get("speaker")
        parts += [
            '<div class="point">',
            f'<h2>{html.escape(point.get("title", ""))}</h2>',
            f'<div class="stamp">{stamp_html}'
            + (f' <span class="speaker">— {html.escape(speaker)}</span>' if speaker else '')
            + '</div>',
            f'<p>{html.escape(point.get("description", ""))}</p>',
        ]
        if point.get("quote"):
            parts.append(f'<blockquote>„{html.escape(point["quote"])}”</blockquote>')
        parts.append('</div>')

    resolutions = summary.get("resolutions") or []
    if resolutions:
        parts.append('<div class="point"><h2>Uchwały</h2>')
        for res in resolutions:
            bits = [res.get("number"), res.get("subject"), res.get("outcome")]
            parts.append(
                '<div class="res">· ' + html.escape(" — ".join(b for b in bits if b)) + '</div>'
            )
        parts.append('</div>')

    parts += [
        f'<form method="post" action="{html.escape(action_url)}" class="actions">',
        '<button class="go" type="submit" name="action" value="publish">Publikuj skrót</button>',
        '<button class="no" type="submit" name="action" value="reject">Odrzuć</button>',
        '</form>',
        '<div class="foot">Nic się nie dzieje, dopóki nie klikniesz. '
        'Odrzucony skrót nie wraca — nagranie zostaje w bazie, ale nikt go nie zobaczy.</div>',
        '</div>',
    ]
    return _page(f"Skrót do akceptacji — {row.title}", "".join(parts))
