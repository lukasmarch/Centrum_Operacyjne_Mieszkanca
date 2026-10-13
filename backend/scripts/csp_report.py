"""
Raport naruszeń CSP zebranych w trybie raportowania (audyt 11.10.2026, E8).

Odpowiada na pytanie, które poprzedza włączenie blokowania: CO strona naprawdę ładuje
spoza polityki. Wiersz = (dyrektywa, zablokowane źródło, strona) z licznikiem; tabela
nie niesie IP, User-Agenta ani parametrów adresu.

Jak czytać wynik:
  • źródło, które widzisz często i jest NASZE lub zamierzone (np. kafelki map) → dopuść je w polityce
  • `inline` przy `script-src` → coś wstrzykuje skrypt (rozszerzenie przeglądarki albo nasz kod)
  • raporty z `chrome-extension://…` to rozszerzenia użytkowników — szum, nie błąd strony
  • decyzję o przełączeniu na blokowanie podejmij po ~2 tygodniach, gdy lista przestaje rosnąć

    python -u -m scripts.csp_report [--days 14]
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from src.database.connection import async_session


async def main(days: int) -> None:
    async with async_session() as session:
        total = (await session.execute(text(
            "SELECT count(*), coalesce(sum(hits), 0), min(first_seen), max(last_seen) FROM csp_violations "
            "WHERE last_seen >= now() - make_interval(days => :d)"), {"d": days})).one()
        print(f"Ostatnie {days} dni: {total[0]} różnych naruszeń, {total[1]} zgłoszeń"
              f" (od {total[2]} do {total[3]})\n")
        if not total[0]:
            print("Brak zgłoszeń — polityka nic nie zgłasza albo raporty nie docierają "
                  "(sprawdź nagłówek Content-Security-Policy-Report-Only i /api/csp-report).")
            return
        print(f"{'zgłoszeń':>8}  {'dyrektywa':<16} {'zablokowane źródło':<42} strona")
        rows = (await session.execute(text(
            "SELECT hits, directive, blocked, page FROM csp_violations "
            "WHERE last_seen >= now() - make_interval(days => :d) "
            "ORDER BY hits DESC, last_seen DESC LIMIT 60"), {"d": days})).all()
        for hits, directive, blocked, page in rows:
            print(f"{hits:>8}  {directive:<16} {blocked:<42} {page}")
        print("\nWedług dyrektywy:")
        for directive, n, hits in (await session.execute(text(
                "SELECT directive, count(*), sum(hits) FROM csp_violations "
                "WHERE last_seen >= now() - make_interval(days => :d) GROUP BY 1 ORDER BY 3 DESC"), {"d": days})):
            print(f"  {directive:<18} {n:>4} źródeł, {hits:>6} zgłoszeń")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    asyncio.run(main(parser.parse_args().days))
