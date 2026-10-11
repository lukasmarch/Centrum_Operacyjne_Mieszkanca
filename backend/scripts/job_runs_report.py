"""
Raport przebiegów schedulera z `job_runs` (audyt 11.10.2026, F-033).

Co się nie wykonało, co padło, co przerwał restart i co zostało nadrobione.

    cd backend && python -u -m scripts.job_runs_report [--days 7] [--job daily_summary]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from src.database.connection import async_session
from src.services.time_span import to_local


async def main(days: int, job: str | None) -> None:
    since = datetime.utcnow() - timedelta(days=days)
    params = {"since": since, "job": job}
    job_filter = "AND job_id = :job" if job else ""
    async with async_session() as s:
        restarts = (await s.execute(text(
            "SELECT count(*) FROM job_runs WHERE job_id = '__scheduler__' AND started_at >= :since"
        ), params)).scalar()
        summary = (await s.execute(text(f"""
            SELECT job_id,
                   count(*) FILTER (WHERE status = 'ok') AS ok,
                   count(*) FILTER (WHERE status = 'error') AS error,
                   count(*) FILTER (WHERE status = 'missed') AS missed,
                   count(*) FILTER (WHERE status = 'interrupted') AS interrupted,
                   count(*) FILTER (WHERE catch_up) AS catch_up,
                   max(finished_at) FILTER (WHERE status = 'ok') AS last_ok
            FROM job_runs
            WHERE coalesce(scheduled_for, started_at) >= :since AND job_id <> '__scheduler__' {job_filter}
            GROUP BY job_id ORDER BY job_id
        """), params)).all()
        problems = (await s.execute(text(f"""
            SELECT job_id, status, scheduled_for, started_at, error
            FROM job_runs
            WHERE status IN ('error', 'missed', 'interrupted')
              AND coalesce(scheduled_for, started_at) >= :since {job_filter}
            ORDER BY coalesce(scheduled_for, started_at) DESC LIMIT 30
        """), params)).all()

    fmt = lambda d: to_local(d).strftime("%d.%m %H:%M") if d else "—"  # noqa: E731
    print(f"Przebiegi schedulera — ostatnie {days} dni (starty schedulera: {restarts})\n")
    print(f"{'job':34} {'ok':>4} {'błąd':>5} {'pominięty':>9} {'przerwany':>9} {'nadrobiony':>10}  ostatni ok")
    for r in summary:
        print(f"{r.job_id:34} {r.ok:>4} {r.error:>5} {r.missed:>9} {r.interrupted:>9} {r.catch_up:>10}  {fmt(r.last_ok)}")
    if problems:
        print("\nProblemy (najnowsze 30):")
        for p in problems:
            when = fmt(p.scheduled_for or p.started_at)
            print(f"  {when}  {p.status:11} {p.job_id:30} {(p.error or '')[:80]}")
    else:
        print("\nBez błędów, pominięć i przerwanych przebiegów.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--job")
    args = parser.parse_args()
    asyncio.run(main(args.days, args.job))
