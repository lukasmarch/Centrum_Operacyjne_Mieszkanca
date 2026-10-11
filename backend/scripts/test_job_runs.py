"""
Nadrabianie po restarcie i newsletter bez dubli (audyt 11.10.2026, F-033, F-022).

Bez bazy (CI):
  1. `cron_previous_fire` — ostatni termin wyzwalacza, strefa Warszawa
  2. `plan_catch_up` — co nadrobić: okno 2 h, początek pamięci, kolejność terminów,
     joby wysyłkowe po przerwanym starcie, interwałowe
  3. `send_window_start` — briefing: od lokalnej północy, tygodnik: 6 dni
Z bazą (`--db`, LOKALNA baza — nigdy prod):
  4. dziennik: running → ok/error, missed, restart → interrupted, historia
  5. `already_sent` — kto dostał już dziś briefing
  6. pełny przebieg na prawdziwym APSchedulerze z ATRAPAMI jobów: start →
     nadrobienie zaległego → zapis z terminem oryginału; kolejny start nic nie powtarza

    cd backend && python -m scripts.test_job_runs [--db]
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from apscheduler.triggers.cron import CronTrigger

from src.scheduler import job_runs as jr
from src.scheduler.newsletter_job import send_window_start

results: list[bool] = []


def check(label: str, ok: bool, detail="") -> None:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + str(detail)) if detail else ''}")
    results.append(bool(ok))


def cron(**kw):
    return CronTrigger(timezone="Europe/Warsaw", **kw)


def spec(job_id, trigger=None, interval=None):
    if interval is not None:
        return jr.JobSpec(job_id, lambda _n: None, interval=interval)
    return jr.JobSpec(job_id, lambda n, t=trigger: jr.cron_previous_fire(t, n))


# 11.10.2026 (czas letni, UTC+2): lokalna 7:20 = 5:20 UTC
NOW = datetime(2026, 10, 11, 5, 20)
MEMORY = datetime(2026, 10, 1)


def section_previous_fire() -> None:
    print("\n1️⃣  Ostatni termin wyzwalacza")
    check("7:00 lokalnie → 5:00 UTC",
          jr.cron_previous_fire(cron(hour=7, minute=0), NOW) == datetime(2026, 10, 11, 5, 0))
    check("6:00 i 6:15 → 6:15 (najpóźniejszy ≤ teraz)",
          jr.cron_previous_fire(cron(hour=6, minute="0,15"), NOW) == datetime(2026, 10, 11, 4, 15))
    check("termin dopiero przed nami (13:00) → brak w oknie",
          jr.cron_previous_fire(cron(hour=13, minute=0), NOW) is None)


def section_plan() -> None:
    print("\n2️⃣  Co nadrobić")
    specs = [
        spec("article_update", cron(hour=6, minute=0)),
        spec("ai_processing", cron(hour=6, minute=15)),
        spec("daily_summary", cron(hour=7, minute=0)),
        spec("midday", cron(hour=13, minute=0)),
    ]
    history = {
        "article_update": jr.JobHistory(last_ok=datetime(2026, 10, 11, 4, 0), last_started=datetime(2026, 10, 11, 4, 0)),
    }
    plan = jr.plan_catch_up(specs, history, MEMORY, NOW)
    check("restart 6:10–7:15: AI i briefing nadrobione, scraping nie (zrobiony)",
          [j for _f, j in plan] == ["ai_processing", "daily_summary"], plan)
    check("kolejność według terminów (6:15 przed 7:00)", plan == sorted(plan))

    check("pusta pamięć (pierwszy start w historii) → nic", jr.plan_catch_up(specs, {}, None, NOW) == [])
    check("termin sprzed początku pamięci → nic (wdrożenie nie wysyła zaległych maili)",
          jr.plan_catch_up(specs, {}, datetime(2026, 10, 11, 5, 10), NOW) == [])

    late = NOW + timedelta(hours=3)
    check("termin starszy niż 2 h → nie nadrabiamy",
          "article_update" not in [j for _f, j in jr.plan_catch_up(specs, {}, MEMORY, late)])

    failed = {"daily_summary": jr.JobHistory(last_ok=None, last_started=datetime(2026, 10, 11, 5, 0))}
    check("briefing przerwany/błędny → nadrobiony (liczy się udany przebieg)",
          "daily_summary" in [j for _f, j in jr.plan_catch_up(specs, failed, MEMORY, NOW)])

    push = [spec("proactive_alerts", cron(hour=18, minute=0))]
    evening = datetime(2026, 10, 11, 16, 30)  # 18:30 lokalnie
    started = {"proactive_alerts": jr.JobHistory(last_ok=None, last_started=datetime(2026, 10, 11, 16, 0))}
    check("push wieczorny przerwany po starcie → NIE ponawiamy (dubel u części odbiorców)",
          jr.plan_catch_up(push, started, MEMORY, evening) == [])
    check("push wieczorny, który nie wystartował → nadrobiony",
          [j for _f, j in jr.plan_catch_up(push, {}, MEMORY, evening)] == ["proactive_alerts"])

    weather = [spec("weather_update", interval=timedelta(hours=1))]
    fresh = {"weather_update": jr.JobHistory(last_ok=NOW - timedelta(minutes=20))}
    stale = {"weather_update": jr.JobHistory(last_ok=NOW - timedelta(hours=2))}
    check("pogoda sprzed 20 min → czeka na swój termin", jr.plan_catch_up(weather, fresh, MEMORY, NOW) == [])
    check("pogoda sprzed 2 h → od razu (11.10: 2 h bez odświeżenia)",
          jr.plan_catch_up(weather, stale, MEMORY, NOW) == [(NOW, "weather_update")])


def section_window() -> None:
    print("\n3️⃣  Okno „już wysłane”")
    check("briefing: od lokalnej północy (22:00 UTC dnia poprzedniego)",
          send_window_start("daily", NOW) == datetime(2026, 10, 10, 22, 0), send_window_start("daily", NOW))
    check("tygodnik: 6 dni wstecz", send_window_start("weekly", NOW) == NOW - timedelta(days=6))


async def section_db() -> None:
    from sqlalchemy import text
    from src.database.connection import async_session
    from src.scheduler.newsletter_job import already_sent

    print("\n4️⃣  Dziennik na lokalnej bazie")
    job = "test_job_runs_probe"
    fire = datetime(2026, 10, 11, 5, 0)
    async with async_session() as s:
        before_mark = (await s.execute(text("SELECT coalesce(max(id), 0) FROM job_runs"))).scalar()
    try:
        jr.record_started(job, fire)
        jr.record_finished(job, fire)
        jr.record_started(job, fire + timedelta(hours=1))
        jr.record_finished(job, fire + timedelta(hours=1), error="ValueError: test")
        jr.record_missed(job, fire + timedelta(hours=2))
        jr.record_started(job, fire + timedelta(hours=3))
        jr.mark_scheduler_start()
        async with async_session() as s:
            rows = (await s.execute(text(
                "SELECT scheduled_for, status FROM job_runs WHERE job_id = :j ORDER BY scheduled_for"
            ), {"j": job})).all()
        statuses = [r.status for r in rows]
        check("ok → błąd → pominięty → przerwany przez restart",
              statuses == ["ok", "error", "missed", "interrupted"], statuses)
        hist = jr.load_history(fire - timedelta(hours=1))[job]
        check("historia: ostatni udany = 5:00, ostatni rozpoczęty = 8:00",
              hist.last_ok == fire and hist.last_started == fire + timedelta(hours=3), hist)
    finally:
        async with async_session() as s:
            await s.execute(text("DELETE FROM job_runs WHERE job_id = :j"), {"j": job})
            await s.execute(text("DELETE FROM job_runs WHERE job_id = '__scheduler__' AND id > :m"),
                            {"m": before_mark})
            await s.commit()

    print("\n5️⃣  Kto dostał już dziś briefing")
    async with async_session() as s:
        sub_id = (await s.execute(text("SELECT id FROM newsletter_subscribers ORDER BY id LIMIT 1"))).scalar()
        if sub_id is None:
            check("brak subskrybentów w lokalnej bazie — pominięte", True)
            return
        log_id = (await s.execute(text(
            "INSERT INTO newsletter_logs (subscriber_id, newsletter_type, subject, sent_at, status) "
            "VALUES (:s, 'daily', 'test_job_runs', now() AT TIME ZONE 'UTC', 'sent') RETURNING id"
        ), {"s": sub_id})).scalar()
        await s.commit()
        try:
            check("dzisiejsza wysyłka widoczna", sub_id in await already_sent(s, "daily"))
            await s.execute(text("UPDATE newsletter_logs SET sent_at = sent_at - interval '2 days' WHERE id = :i"),
                            {"i": log_id})
            await s.commit()
            check("przedwczorajsza NIE blokuje dzisiejszej", sub_id not in await already_sent(s, "daily"))
            check("wysłany briefing nie blokuje tygodnika (inny rodzaj)",
                  sub_id not in await already_sent(s, "weekly"))
        finally:
            await s.execute(text("DELETE FROM newsletter_logs WHERE id = :i"), {"i": log_id})
            await s.commit()


def section_scheduler() -> None:
    """Atrapy zamiast prawdziwych jobów — nic nie scrapuje, nie woła modelu, nie wysyła."""
    import time
    from apscheduler.schedulers.background import BackgroundScheduler
    from sqlalchemy import create_engine, text
    from src.config import settings
    from src.scheduler import scheduler as sched_mod

    print("\n6️⃣  Pełny przebieg na APSchedulerze (atrapy)")
    calls: list = []
    now = datetime.utcnow()
    local_now = datetime.now()
    # termin 20 min temu (lokalnie), job o tej porze nie ma udanego przebiegu
    fire_local = local_now - timedelta(minutes=20)
    trig = CronTrigger(hour=fire_local.hour, minute=fire_local.minute, timezone="Europe/Warsaw")
    job_id = "test_catchup_probe"
    eng = create_engine(settings.DATABASE_URL.replace("+asyncpg", "+psycopg2"))
    with eng.begin() as c:
        mark = c.execute(text("SELECT coalesce(max(id), 0) FROM job_runs")).scalar()
        # pamięć zaczyna się dzień wcześniej — termin sprzed 20 min jest „po” niej
        c.execute(text("INSERT INTO job_runs (job_id, started_at, status) VALUES ('__scheduler__', :t, 'started')"),
                  {"t": now - timedelta(days=1)})

    original = sched_mod.scheduler
    fake = BackgroundScheduler(timezone="Europe/Warsaw")
    fake.add_job(lambda: calls.append("probe"), trigger=trig, id=job_id)
    sched_mod.scheduler = fake
    try:
        fake.start()
        sched_mod._schedule_catch_up()
        catch = fake.get_job("__catch_up__")
        check("zaległy job zaplanowany do nadrobienia", catch is not None)
        if catch is not None:
            fake.modify_job("__catch_up__", next_run_time=datetime.now(fake.timezone))
            time.sleep(2)
        check("atrapa wykonana raz", calls == ["probe"], calls)
        with eng.begin() as c:
            rows = c.execute(text("SELECT status, catch_up, scheduled_for FROM job_runs WHERE job_id = :j"),
                             {"j": job_id}).all()
        check("zapis: ok, nadrobiony, z terminem oryginału",
              len(rows) == 1 and rows[0].status == "ok" and rows[0].catch_up
              and rows[0].scheduled_for == jr.cron_previous_fire(trig, datetime.utcnow()), rows)

        calls.clear()
        sched_mod._schedule_catch_up()
        check("kolejny restart niczego nie powtarza", fake.get_job("__catch_up__") is None and calls == [])
    finally:
        fake.shutdown(wait=False)
        sched_mod.scheduler = original
        with eng.begin() as c:
            c.execute(text("DELETE FROM job_runs WHERE job_id = :j"), {"j": job_id})
            c.execute(text("DELETE FROM job_runs WHERE job_id = '__scheduler__' AND id > :m"), {"m": mark})
        eng.dispose()


if __name__ == "__main__":
    section_previous_fire()
    section_plan()
    section_window()
    if "--db" in sys.argv:
        asyncio.run(section_db())
        section_scheduler()
    passed = sum(results)
    print(f"\n{'✅' if passed == len(results) else '❌'} {passed}/{len(results)} sprawdzeń")
    sys.exit(0 if passed == len(results) else 1)
