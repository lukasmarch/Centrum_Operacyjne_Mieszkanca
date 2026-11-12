"""
Dostęp do serwerów gminy: stan, wyłącznik, dziennik żądań (2026-11-12).

Jedyny sposób na sprawdzenie, czy BIP nas wpuszcza, BEZ wysyłania żądania.
⚠️ Nie sprawdzaj dostępu ręcznym `curl` z serwera — takie żądanie nie trafia
do dziennika, a dostawca liczy je jako nasz ruch.

    cd backend
    python -m scripts.bip_access --status                 # stan hostów + ruch 24 h / 7 dni
    python -m scripts.bip_access --log [--days 7]         # dziennik żądań (wyciąg dla dostawcy)
    python -m scripts.bip_access --hold "powód"           # wyłącznik: zero żądań
    python -m scripts.bip_access --release --yes          # zdjęcie wyłącznika (po zgodzie dostawcy!)

Na produkcji: `docker exec -w /app centrum-backend-1 python -m scripts.bip_access --status`.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text  # noqa: E402

from src.scrapers import polite  # noqa: E402

BIP = "bip.gminarybno.pl"


def _rows(sql: str, **params):
    store = polite.get_store()
    with store._conn() as conn:  # noqa: SLF001 — skrypt serwisowy
        return conn.execute(text(sql), params).fetchall()


def status() -> None:
    now = datetime.utcnow()
    print(f"Teraz: {now:%Y-%m-%d %H:%M} UTC\n")
    hosts = _rows("SELECT host FROM polite_hosts UNION SELECT DISTINCT host FROM polite_requests ORDER BY 1")
    for (host,) in hosts:
        st = polite.get_store().state(host)
        reason = polite.closed_reason(host)
        print(f"■ {host}: {'ZAMKNIĘTY — ' + reason if reason else 'otwarty'}")
        print(f"    poziom eskalacji {st.refusal_level}, ostatnia odmowa {st.last_refusal_at or '—'}")
        for label, since in (("1 h", now - timedelta(hours=1)), ("24 h", now - timedelta(days=1)),
                             ("7 dni", now - timedelta(days=7))):
            rows = _rows(
                "SELECT outcome, count(*) FROM polite_requests WHERE host = :h AND at >= :s GROUP BY 1",
                h=host, s=since,
            )
            total = sum(r[1] for r in rows)
            detail = ", ".join(f"{o} {n}" for o, n in rows) or "—"
            print(f"    {label:>6}: {total:>4} żądań ({detail})")
        print(f"    limity: {polite.HOURLY_LIMIT}/h, {polite.DAILY_LIMIT}/dobę, odstęp ≥ {polite.MIN_INTERVAL_S} s\n")


def log(days: int) -> None:
    since = datetime.utcnow() - timedelta(days=days)
    rows = _rows(
        "SELECT at, host, method, path, status, outcome, duration_ms FROM polite_requests "
        "WHERE at >= :s ORDER BY at", s=since,
    )
    print(f"# Żądania do *.gminarybno.pl od {since:%Y-%m-%d %H:%M} UTC ({len(rows)})")
    print("czas_utc;host;metoda;sciezka;kod;wynik;ms")
    for r in rows:
        print(f"{r[0]:%Y-%m-%d %H:%M:%S};{r[1]};{r[2]};{r[3]};{r[4] if r[4] is not None else ''};{r[5]};{r[6]}")
    per_day = _rows(
        "SELECT date(at), host, count(*), min(at), max(at) FROM polite_requests WHERE at >= :s "
        "GROUP BY 1, 2 ORDER BY 1, 2", s=since,
    )
    print("\n# Podsumowanie dzienne (UTC)")
    for d, host, n, first, last in per_day:
        print(f"{d} {host}: {n} żądań, {first:%H:%M}–{last:%H:%M}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Stan dostępu do serwerów gminy")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--log", action="store_true")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--hold", metavar="POWÓD")
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--yes", action="store_true", help="potwierdzenie dla --release")
    ap.add_argument("--host", default=BIP)
    args = ap.parse_args()

    if args.hold:
        polite.hold(args.host, args.hold)
        print(f"Wyłącznik WŁĄCZONY dla {args.host}: {args.hold}")
    elif args.release:
        if not args.yes:
            print("Zdjęcie wyłącznika wznawia ruch do serwera. Tylko po zgodzie dostawcy. Dodaj --yes.")
            return 2
        polite.release(args.host)
        print(f"Wyłącznik ZDJĘTY dla {args.host} (przerwa i poziom eskalacji wyzerowane)")
    elif args.log:
        log(args.days)
        return 0
    status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
