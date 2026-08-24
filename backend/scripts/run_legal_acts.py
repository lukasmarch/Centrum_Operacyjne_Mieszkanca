"""
Ręczne napełnienie rejestru aktów prawnych (etap 4, 2026-08-24).

Pierwsze uruchomienie po migracji `add_legal_acts` — potem robi to
`legal_acts_job` w niedziele o 5:00.

    cd backend
    python -m scripts.run_legal_acts --dry          # co by pobrał, bez kosztów
    python -m scripts.run_legal_acts                # zakres 2024–2026
    python -m scripts.run_legal_acts --since 2026-01-01

⚠️ Pełne napełnienie to ~440 aktów: tyle samo stron szczegółowych i PDF-ów
z małego serwera gminy, około 20 minut z odstępami. Ponowne uruchomienie jest
tanie — akty znane po `bip_id` nie są pobierane ponownie.
"""
import argparse
import asyncio
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.scheduler.legal_acts_job import run_legal_acts_async  # noqa: E402
from src.scrapers.legal_acts import DEFAULT_SINCE  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Napełnia tabelę legal_acts z BIP")
    ap.add_argument("--dry", action="store_true",
                    help="tylko lista aktów — bez PDF-ów, bazy i kosztów")
    ap.add_argument("--since", help="próg daty podjęcia (RRRR-MM-DD), domyślnie 2024-01-01")
    args = ap.parse_args()

    since = DEFAULT_SINCE
    if args.since:
        try:
            since = datetime.strptime(args.since, "%Y-%m-%d").date()
        except ValueError:
            print(f"Zła data: {args.since} (oczekuję RRRR-MM-DD)")
            return 2

    result = asyncio.run(run_legal_acts_async(since=since, dry=args.dry))
    print()
    for key, value in result.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
