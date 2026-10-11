"""
Dziennik przebiegów schedulera i nadrabianie po restarcie (audyt 11.10.2026, F-033).

Scheduler trzyma harmonogram w PAMIĘCI. Każdy restart kontenera (każdy deploy)
gubił joby zaplanowane na czas przerwy, a joby „co godzinę” liczyły się od nowa:
11.10 pięć deployów w ciągu dnia → pogoda nie odświeżyła się ponad 2 h, ruch
z 10:00 przepadł. Gdyby restart wypadł o 6:55, przepadłby briefing i mail Premium.

Dwie role jednej tabeli `job_runs`:
  1. DZIENNIK — listenery APSchedulera zapisują każdy przebieg (running → ok/error,
     missed). Przebiegi, które restart zastał w toku, dostają `interrupted`.
  2. PAMIĘĆ — przy starcie `plan_catch_up` wybiera joby, których termin minął
     w ostatnich `CATCH_UP_GRACE` bez udanego przebiegu, i uruchamia je RAZ,
     PO KOLEI, w kolejności terminów: łańcuch scraping → AI → osadzanie →
     briefing → mail zachowuje porządek.

⚠️ Pierwszy start z pustą tabelą niczego nie nadrabia — wiersz `__scheduler__`
wyznacza początek pamięci. Bez tego wdrożenie tej funkcji wysłałoby zaległe maile.
⚠️ Joby wysyłające push/maile bez własnej ochrony przed dublami (`NO_RETRY_IF_STARTED`)
NIE są nadrabiane, gdy zdążyły wystartować — przerwana wysyłka mogła dojść do części
odbiorców. Newslettery są nadrabiane zawsze: same pomijają, kto już dostał (F-022).

Zapis idzie OSOBNYM synchronicznym połączeniem (psycopg2, jest w obrazie):
listenery działają w wątku APSchedulera, poza pętlą asyncio. Każdy błąd zapisu
jest połykany — dziennik nie może zatrzymać joba.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, Optional

from src.utils.logger import setup_logger

logger = setup_logger("JobRuns")

SCHEDULER_MARK = "__scheduler__"
CATCH_UP_GRACE = timedelta(hours=2)

# Push i maile bez pamięci odbiorców: przerwany przebieg mógł już kogoś
# powiadomić, więc ponowienie = dubel. Nadrabiamy je wyłącznie, gdy NIE wystartowały.
NO_RETRY_IF_STARTED = {"proactive_alerts", "business_weekly_report", "alert_push"}

_engine = None


def _sync_engine():
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine
        from src.config import settings
        url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
        _engine = create_engine(url, pool_size=2, max_overflow=2, pool_pre_ping=True)
    return _engine


def to_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Projekt trzyma naiwny UTC; APScheduler podaje czasy ze strefą Europe/Warsaw."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _execute(sql: str, params: dict, fetch: bool = False):
    from sqlalchemy import text
    try:
        with _sync_engine().begin() as conn:
            result = conn.execute(text(sql), params)
            return result.fetchall() if fetch else None
    except Exception as exc:  # noqa: BLE001 — dziennik nigdy nie zatrzymuje joba
        logger.error(f"job_runs: zapis nieudany ({type(exc).__name__}: {exc})")
        return [] if fetch else None


# --------------------------------------------------------------------------- dziennik

def record_started(job_id: str, scheduled_for: Optional[datetime], catch_up: bool = False) -> None:
    _execute(
        "INSERT INTO job_runs (job_id, scheduled_for, started_at, status, catch_up) "
        "VALUES (:job_id, :scheduled_for, :now, 'running', :catch_up)",
        {"job_id": job_id, "scheduled_for": to_naive_utc(scheduled_for),
         "now": datetime.utcnow(), "catch_up": catch_up},
    )


def record_finished(job_id: str, scheduled_for: Optional[datetime], error: Optional[str] = None) -> None:
    """Zamyka NAJNOWSZY otwarty przebieg tego terminu."""
    _execute(
        "UPDATE job_runs SET finished_at = :now, status = :status, error = :error "
        "WHERE id = (SELECT id FROM job_runs WHERE job_id = :job_id AND status = 'running' "
        "AND scheduled_for IS NOT DISTINCT FROM :scheduled_for ORDER BY id DESC LIMIT 1)",
        {"job_id": job_id, "scheduled_for": to_naive_utc(scheduled_for), "now": datetime.utcnow(),
         "status": "error" if error else "ok", "error": (error or None) and error[:500]},
    )


def record_missed(job_id: str, scheduled_for: Optional[datetime]) -> None:
    _execute(
        "INSERT INTO job_runs (job_id, scheduled_for, status) VALUES (:job_id, :scheduled_for, 'missed')",
        {"job_id": job_id, "scheduled_for": to_naive_utc(scheduled_for)},
    )


def mark_scheduler_start() -> Optional[datetime]:
    """Zamyka przebiegi przerwane restartem, zapisuje start i zwraca POCZĄTEK
    pamięci (pierwszy start w historii) — nic sprzed niego nie jest nadrabiane."""
    now = datetime.utcnow()
    _execute(
        "UPDATE job_runs SET status = 'interrupted', finished_at = :now "
        "WHERE status = 'running' AND job_id <> :mark",
        {"now": now, "mark": SCHEDULER_MARK},
    )
    _execute(
        "INSERT INTO job_runs (job_id, started_at, status) VALUES (:mark, :now, 'started')",
        {"mark": SCHEDULER_MARK, "now": now},
    )
    rows = _execute(
        "SELECT min(started_at) FROM job_runs WHERE job_id = :mark",
        {"mark": SCHEDULER_MARK}, fetch=True,
    )
    return rows[0][0] if rows and rows[0][0] else None


@dataclass
class JobHistory:
    last_ok: Optional[datetime] = None        # najnowszy `scheduled_for` zakończony ok
    last_started: Optional[datetime] = None   # najnowszy `scheduled_for` w ogóle rozpoczęty


def load_history(since: datetime) -> dict:
    rows = _execute(
        "SELECT job_id, "
        "max(scheduled_for) FILTER (WHERE status = 'ok'), "
        "max(scheduled_for) FILTER (WHERE status IN ('ok','error','running','interrupted')) "
        "FROM job_runs WHERE scheduled_for >= :since AND job_id <> :mark GROUP BY job_id",
        {"since": since, "mark": SCHEDULER_MARK}, fetch=True,
    )
    return {r[0]: JobHistory(last_ok=r[1], last_started=r[2]) for r in rows}


# --------------------------------------------------------------------------- nadrabianie

@dataclass
class JobSpec:
    job_id: str
    previous_fire: Callable[[datetime], Optional[datetime]]  # ostatni termin ≤ now (naiwny UTC)
    interval: Optional[timedelta] = None                     # dla jobów „co X”


def plan_catch_up(
    specs: Iterable[JobSpec],
    history: dict,
    memory_start: Optional[datetime],
    now: datetime,
    grace: timedelta = CATCH_UP_GRACE,
) -> list:
    """Które joby nadrobić — lista (termin, job_id) rosnąco po terminie.

    Czysta funkcja: decyzja bez bazy i bez zegara, testowalna w CI.
      - cron: ostatni termin mieści się w oknie `grace` i jest PO początku pamięci,
        a dziennik nie ma dla niego udanego przebiegu;
      - joby z `NO_RETRY_IF_STARTED`: wystarczy, że przebieg wystartował;
      - interwałowe: od ostatniego udanego przebiegu minął interwał (termin = teraz).
    """
    if memory_start is None:
        return []
    plan = []
    for spec in specs:
        h = history.get(spec.job_id, JobHistory())
        if spec.interval is not None:
            if h.last_ok is None or now - h.last_ok >= spec.interval:
                plan.append((now, spec.job_id))
            continue
        fire = spec.previous_fire(now)
        if fire is None or fire <= memory_start or now - fire > grace:
            continue
        done = h.last_started if spec.job_id in NO_RETRY_IF_STARTED else h.last_ok
        if done is not None and done >= fire:
            continue
        plan.append((fire, spec.job_id))
    return sorted(plan)


def cron_previous_fire(trigger, now_utc: datetime, lookback: timedelta = CATCH_UP_GRACE + timedelta(hours=1)) -> Optional[datetime]:
    """Ostatni termin wyzwalacza ≤ now (naiwny UTC). APScheduler 3 nie ma
    `get_previous_fire_time`, więc idziemy od `now - lookback` w przód."""
    tz = trigger.timezone
    now_local = now_utc.replace(tzinfo=timezone.utc).astimezone(tz)
    fire = trigger.get_next_fire_time(None, now_local - lookback)
    last = None
    while fire is not None and fire <= now_local:
        last = fire
        fire = trigger.get_next_fire_time(fire, fire + timedelta(seconds=1))
    return to_naive_utc(last)
