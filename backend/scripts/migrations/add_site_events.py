"""
Migration: pomiar tego, co dzieje się NA STRONIE (2026-08-30)

Tabela `site_events` + kolumny atrybucji na `users`, `push_subscriptions`
i `newsletter_logs`.

Skąd potrzeba: sierpniowa kampania dowiozła 24 132 zasięgu na Facebooku i 138
unikalnych urządzeń na stronie w tygodniu — przy ZERU nowych kont i ZERU nowych
zgód push. Na pytanie „na czym się odbili" nie ma dziś źródła odpowiedzi:

  * front jest SPA bez react-routera (nawigacja przez `history.pushState`
    w `frontend/App.tsx`), więc log Caddy widzi wyłącznie PIERWSZE wejście —
    ani ścieżki, ani głębokości wizyty, ani zdarzeń produktowych;
  * log Caddy ma `roll_keep_for 168h`, więc cała fala 18–22.08 już nie istnieje;
  * `users` nie ma ANI JEDNEJ kolumny o źródle — cztery sierpniowe konta to
    cztery daty i nic więcej.

Co mierzymy i po co:
  * `event` — zamknięta lista (patrz `ALLOWED_EVENTS` w api/endpoints/analytics.py).
    Endpoint odrzuca resztę: bez tego `POST /api/events` jest otwartym zapisem do bazy;
  * `section` — `AppSection` z `frontend/types.ts`. Ścieżka w SPA to stan aplikacji,
    nie adres, więc bez tego nie wiadomo, gdzie ktoś był;
  * `session_id` — uuid z `sessionStorage`, NIE ciasteczko: ginie z zamknięciem
    karty, nie łączy wizyt między dniami, nie wymaga banera zgody;
  * `utm_*` — jedyny sposób powiązania wizyty z konkretnym postem na Facebooku,
    bo FB nie liczy kliknięć w link z komentarza;
  * `device` — liczony z User-Agenta PO STRONIE SERWERA; samego UA nie zapisujemy,
    tak samo jak nie zapisujemy IP.

RODO: w tabeli nie ma IP ani User-Agenta. `session_id` i `user_id` znikają po
90 dniach, cały wiersz po 180 (`scheduler/retention_job.py`). Liczniki zostają —
do analityki wystarczają nazwa zdarzenia, sekcja i kampania.

Kolumny `users.acq_*` są ŚWIADOMĄ denormalizacją: `site_events` kasuje retencja,
a to, skąd wziął się klient, ma przeżyć dłużej niż log.

`user_id` w `site_events` celowo BEZ klucza obcego — dokładnie jak w
`agent_tool_calls`: log ma przeżyć skasowanie konta (RODO kasuje samo `user_id`),
a klucz obcy blokowałby `scripts/cleanup_test_accounts.py`.

Idempotentna.

Użycie:
    cd backend && python -m scripts.migrations.add_site_events
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import settings


async def migrate():
    print("=" * 60)
    print("Migration: site_events + atrybucja pozyskania")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS site_events (
                id BIGSERIAL PRIMARY KEY,
                occurred_at TIMESTAMP NOT NULL DEFAULT NOW(),
                session_id VARCHAR(36) NULL,
                user_id INTEGER NULL,
                event VARCHAR(40) NOT NULL,
                section VARCHAR(40) NULL,
                path VARCHAR(200) NULL,
                referrer_host VARCHAR(120) NULL,
                utm_source VARCHAR(60) NULL,
                utm_medium VARCHAR(60) NULL,
                utm_campaign VARCHAR(100) NULL,
                utm_content VARCHAR(100) NULL,
                device VARCHAR(10) NULL,
                meta JSONB NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        print("✓ Tabela site_events")

        # Każdy raport pyta „ostatnie N dni" — data jest w KAŻDYM zapytaniu.
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_site_events_occurred
            ON site_events (occurred_at)
        """))
        # Lejek liczy się per zdarzenie w oknie czasu.
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_site_events_event_occurred
            ON site_events (event, occurred_at)
        """))
        # „Ile wejść dowiózł ten post" — grupowanie po kampanii.
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_site_events_campaign
            ON site_events (utm_campaign)
        """))
        # Odtworzenie POJEDYNCZEJ wizyty: co człowiek klikał po kolei.
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_site_events_session
            ON site_events (session_id)
        """))
        print("✓ Indeksy site_events (4)")

        # ── Atrybucja pozyskania na koncie ────────────────────────────────
        for col, ddl in [
            ("acq_session_id", "VARCHAR(36) NULL"),
            ("acq_utm_campaign", "VARCHAR(100) NULL"),
            ("acq_landing", "VARCHAR(200) NULL"),
            ("acq_first_seen", "TIMESTAMP NULL"),
        ]:
            await conn.execute(text(
                f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {ddl}"
            ))
        print("✓ users.acq_* (4 kolumny)")

        # 5 z 9 subskrypcji push nie ma `user_id` (zgody wydane w przeglądarce
        # bez rejestracji) — `session_id` to jedyne, co wiąże je z wizytą.
        await conn.execute(text("""
            ALTER TABLE push_subscriptions
            ADD COLUMN IF NOT EXISTS acq_session_id VARCHAR(36) NULL
        """))
        print("✓ push_subscriptions.acq_session_id")

        # `newsletter_logs.opened_at` i `clicked_at` istnieją od początku i NIC
        # do nich nie pisze (91 wysyłek, 0 otwarć). Webhook Resend potrzebuje
        # identyfikatora wiadomości, żeby trafić we właściwy wiersz.
        await conn.execute(text("""
            ALTER TABLE newsletter_logs
            ADD COLUMN IF NOT EXISTS provider_message_id VARCHAR(80) NULL
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_newsletter_logs_provider_msg
            ON newsletter_logs (provider_message_id)
        """))
        print("✓ newsletter_logs.provider_message_id + indeks")

    await engine.dispose()
    print("\n✅ Migracja zakończona")


if __name__ == "__main__":
    asyncio.run(migrate())
