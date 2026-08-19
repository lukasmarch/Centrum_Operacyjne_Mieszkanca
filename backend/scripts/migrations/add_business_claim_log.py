"""
Migration: ślad po decyzjach w sprawie przejęcia wizytówki (2026-08-19)

Powód. `moderate_claim` przy odrzuceniu KASUJE wiersz `business_profiles` —
i musi kasować, bo zostawiony wpis „rejected" blokował firmę przed przejęciem
przez prawdziwego właściciela (błąd naprawiony 12.08.2026). Razem z profilem
znikał jednak jedyny ślad, że ktoś w ogóle próbował:

- nie było jak odróżnić pierwszej próby od piątej — admin za każdym razem
  zaczynał ocenę od zera,
- zgłaszający nie dowiadywał się o odmowie: baner „czeka na weryfikację"
  po prostu gasł,
- odrzucony mógł składać wniosek w pętli, bez żadnej karencji.

Tabela trzyma MINIMUM: kto, która firma, jaka decyzja, kiedy. Bez telefonu,
e-maila i uzasadnienia — te znikają razem z profilem i nie mają tu wracać.
Wyjątkiem jest `business_name`: wpis ręczny bywa kasowany razem z odrzuceniem,
więc bez zapisanej nazwy nie da się pokazać człowiekowi, CZEGO dotyczyła odmowa.

Bez kluczy obcych świadomie — firma `source='manual'` i konto użytkownika bywają
usuwane, a log ma je przeżyć (do czasu DSAR, który kasuje go razem z resztą).

Idempotentna.

Użycie:
    cd backend && python -m scripts.migrations.add_business_claim_log
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text

from src.database.connection import async_session  # noqa: E402


DDL = """
CREATE TABLE IF NOT EXISTS business_claim_log (
    id SERIAL PRIMARY KEY,
    business_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    action VARCHAR(20) NOT NULL,
    business_name VARCHAR(300) NOT NULL,
    admin_email VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
)
"""

INDEXES = [
    ("ix_business_claim_log_business_id", "business_claim_log (business_id)"),
    ("ix_business_claim_log_user_id", "business_claim_log (user_id)"),
    ("ix_business_claim_log_action", "business_claim_log (action)"),
    ("ix_business_claim_log_created_at", "business_claim_log (created_at)"),
]


async def migrate() -> None:
    async with async_session() as session:
        existed = (await session.execute(text(
            "SELECT to_regclass('public.business_claim_log')"
        ))).scalar()

        await session.execute(text(DDL))
        print("  = tabela business_claim_log już istniała" if existed
              else "  + utworzono tabelę business_claim_log")

        for name, target in INDEXES:
            await session.execute(text(
                f"CREATE INDEX IF NOT EXISTS {name} ON {target}"
            ))
        print(f"  + indeksy: {len(INDEXES)}")

        # Uzupełnienie historii dla wizytówek, które już są w bazie. Odrzuceń
        # nie odtworzymy (wiersze skasowane), ale zgłoszenia i zatwierdzenia
        # tak — inaczej właściciel wchodzący w nową zakładkę „Moja firma"
        # zobaczyłby wizytówkę bez żadnej historii.
        backfilled = await session.execute(text("""
            INSERT INTO business_claim_log
                (business_id, user_id, action, business_name, admin_email, created_at)
            SELECT p.business_id, p.user_id, 'claimed', b.nazwa, NULL, p.created_at
            FROM business_profiles p
            JOIN ceidg_businesses b ON b.id = p.business_id
            WHERE NOT EXISTS (
                SELECT 1 FROM business_claim_log l
                WHERE l.business_id = p.business_id
                  AND l.user_id = p.user_id
                  AND l.action = 'claimed'
            )
        """))
        print(f"  ~ uzupełniono {backfilled.rowcount} wpisów 'claimed' z istniejących profili")

        backfilled_ok = await session.execute(text("""
            INSERT INTO business_claim_log
                (business_id, user_id, action, business_name, admin_email, created_at)
            SELECT p.business_id, p.user_id, 'approved', b.nazwa, NULL, p.verified_at
            FROM business_profiles p
            JOIN ceidg_businesses b ON b.id = p.business_id
            WHERE p.claim_status = 'verified' AND p.verified_at IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM business_claim_log l
                WHERE l.business_id = p.business_id
                  AND l.user_id = p.user_id
                  AND l.action = 'approved'
            )
        """))
        print(f"  ~ uzupełniono {backfilled_ok.rowcount} wpisów 'approved'")

        await session.commit()
        print("Migracja zakończona.")


if __name__ == "__main__":
    asyncio.run(migrate())
