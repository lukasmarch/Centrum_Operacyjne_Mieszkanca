"""
Raport z `site_events` — co ludzie robią na stronie po wejściu.

Uzupełnia `scripts/traffic_report.py`, który czyta log Caddy i z natury widzi
wyłącznie PIERWSZE żądanie HTML (front to SPA bez react-routera). Ten raport
odpowiada na pytanie, którego log nie umie postawić: gdzie człowiek poszedł
dalej i w którym miejscu przestał.

Powód powstania: sierpniowa kampania dowiozła 24 132 zasięgu na Facebooku
i 138 unikalnych urządzeń na stronie w tygodniu — przy ZERU nowych kont i ZERU
nowych zgód push. Bez tego zestawienia „zero rejestracji" nie odróżnia się od
„nikt nie doszedł do formularza".

Użycie:
    cd backend && python -u -m scripts.site_report [--days 7]

Uwaga o oknach: `site_events` żyje 180 dni, log Caddy 7 (`roll_keep_for 168h`).
Przy `--days` większym niż 7 liczby z obu raportów przestają być porównywalne.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import settings


def _bar(n: int, top: int, width: int = 28) -> str:
    if top <= 0:
        return ""
    return "█" * max(1, round(n / top * width)) if n else ""


async def report(days: int) -> None:
    since = datetime.utcnow() - timedelta(days=days)
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.connect() as conn:
        async def rows(sql: str, **kw):
            res = await conn.execute(text(sql), {"since": since, **kw})
            return res.fetchall()

        total = (await rows(
            "SELECT count(*), count(DISTINCT session_id) FROM site_events WHERE occurred_at >= :since"
        ))[0]

        print("=" * 64)
        print(f"  STRONA — CO ROBIĄ LUDZIE · ostatnie {days} dni")
        print("=" * 64)
        if not total[0]:
            print("\n  Brak zdarzeń w tym oknie.")
            print("  Jeśli front jest już wdrożony, sprawdź, czy POST /api/events dochodzi")
            print("  (konsola przeglądarki → zakładka Sieć) i czy CORS przepuszcza origin.")
            await engine.dispose()
            return

        print(f"\n  Zdarzenia:  {total[0]}")
        print(f"  Wizyty:     {total[1]}   (unikalne session_id)")

        # ── Sekcje ────────────────────────────────────────────────────────
        secs = await rows("""
            SELECT coalesce(section, '(brak)') s, count(*) n, count(DISTINCT session_id) v
            FROM site_events WHERE occurred_at >= :since AND event = 'view'
            GROUP BY 1 ORDER BY n DESC LIMIT 15
        """)
        if secs:
            top = secs[0][1]
            print("\n  Odwiedzane sekcje")
            for s, n, v in secs:
                print(f"    {s:<22} {n:>5}  {_bar(n, top)}  ({v} wizyt)")

        # ── Pierwsza sekcja w wizycie ─────────────────────────────────────
        # Tu widać, dokąd faktycznie prowadzą linki z Facebooka.
        firsts = await rows("""
            SELECT coalesce(section, '(brak)') s, count(*) n FROM (
                SELECT DISTINCT ON (session_id) session_id, section
                FROM site_events
                WHERE occurred_at >= :since AND event = 'view' AND session_id IS NOT NULL
                ORDER BY session_id, occurred_at
            ) t GROUP BY 1 ORDER BY n DESC LIMIT 10
        """)
        if firsts:
            top = firsts[0][1]
            print("\n  Pierwsza sekcja wizyty  (dokąd prowadzi link)")
            for s, n in firsts:
                print(f"    {s:<22} {n:>5}  {_bar(n, top)}")

        # ── Głębokość wizyty ──────────────────────────────────────────────
        depth = await rows("""
            SELECT
                count(*) FILTER (WHERE k = 1) jedna,
                count(*) FILTER (WHERE k BETWEEN 2 AND 3) dwie_trzy,
                count(*) FILTER (WHERE k >= 4) cztery_plus,
                round(avg(k), 1) srednio
            FROM (
                SELECT session_id, count(*) k FROM site_events
                WHERE occurred_at >= :since AND event = 'view' AND session_id IS NOT NULL
                GROUP BY session_id
            ) t
        """)
        if depth and depth[0][3] is not None:
            j, dt, cp, sr = depth[0]
            print("\n  Głębokość wizyty  (ile sekcji obejrzano)")
            print(f"    1 sekcja             {j:>5}   ← rzut oka i wyjście")
            print(f"    2–3 sekcje           {dt:>5}")
            print(f"    4 i więcej           {cp:>5}")
            print(f"    średnio              {sr:>5}")

        # ── Kampanie ──────────────────────────────────────────────────────
        camp = await rows("""
            SELECT coalesce(utm_campaign, '(bez znacznika)') c,
                   coalesce(utm_content, '') k,
                   count(DISTINCT session_id) v
            FROM site_events WHERE occurred_at >= :since
            GROUP BY 1, 2 ORDER BY v DESC LIMIT 12
        """)
        if camp:
            top = camp[0][2]
            print("\n  Wizyty wg kampanii")
            for c, k, v in camp:
                label = f"{c} [{k}]" if k else c
                print(f"    {label:<34} {v:>4}  {_bar(v, top, 20)}")

        # ── Lejek ─────────────────────────────────────────────────────────
        funnel = await rows("""
            SELECT event, count(*) n, count(DISTINCT session_id) v
            FROM site_events WHERE occurred_at >= :since AND event <> 'view'
            GROUP BY 1 ORDER BY n DESC
        """)
        counts = {e: (n, v) for e, n, v in funnel}
        visits = total[1] or 1

        def line(label: str, key: str, base: int) -> None:
            n, v = counts.get(key, (0, 0))
            pct = f"{v / base * 100:5.1f}%" if base else "    —"
            flag = "  ← nikt" if not n else ""
            print(f"    {label:<30} {n:>5}   {pct} wizyt{flag}")

        print("\n  Lejek  (odsetek liczony od liczby wizyt)")
        line("otwarcie rejestracji", "register_open", visits)
        line("konto założone", "register_done", visits)
        line("pokazana prośba o push", "push_prompt", visits)
        line("zgoda na push", "push_granted", visits)
        line("odmowa push", "push_denied", visits)
        line("pytanie do asystenta", "assistant_question", visits)
        line("klik w znacznik sesji", "session_stamp_click", visits)
        line("trafienie w płatną funkcję", "paywall_hit", visits)

        # ── Urządzenia ────────────────────────────────────────────────────
        # `device IS NOT NULL` odcina zdarzenia dopisywane po stronie SERWERA
        # (`register_done`) — nie mają nagłówka przeglądarki, więc bez tego
        # filtra tworzyły osobną, fikcyjną pozycję „?".
        dev = await rows("""
            SELECT device d, count(DISTINCT session_id) v
            FROM site_events
            WHERE occurred_at >= :since AND device IS NOT NULL
            GROUP BY 1 ORDER BY v DESC
        """)
        if dev:
            print("\n  Urządzenia")
            for d, v in dev:
                print(f"    {d:<10} {v:>5} wizyt")

        # ── Skąd pozyskane konta ──────────────────────────────────────────
        acq = await rows("""
            SELECT coalesce(acq_utm_campaign, '(nieznane)') c,
                   coalesce(acq_landing, '-') l, count(*) n
            FROM users WHERE created_at >= :since GROUP BY 1, 2 ORDER BY n DESC
        """)
        print("\n  Konta założone w tym oknie")
        if acq:
            for c, l, n in acq:
                print(f"    {c:<26} {l:<24} {n}")
        else:
            print("    brak")

    await engine.dispose()
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description="Co ludzie robią na rybnolive.pl")
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()
    asyncio.run(report(args.days))


if __name__ == "__main__":
    main()
