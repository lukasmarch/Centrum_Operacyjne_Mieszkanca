"""
Migration: role z zakresem, zaproszenia i ogłoszenia sołtysów (2026-09-27)

Sołectwa miały dostać WŁASNE miejsce do publikowania (decyzja Łukasza z 16.09 —
patrz `feed_policy.ANNOUNCEMENT_ONLY_SOURCES`). Do tej pory jedyną drogą do
ogłoszeń sołtysa było scrapowanie jego prywatnego profilu FB.

Trzy tabele:

  * `user_roles` — kto jest kim i W JAKIM ZAKRESIE („sołtys" + „Żabiny").
    Jedna tabela dla wszystkich ról, bo rola jest warstwą NAD kontem, a nie
    rodzajem konta: sołtys jest też mieszkańcem, a koniec kadencji odbiera
    rolę, nie konto. Firmy zostają przy `business_profiles` (działa i jest
    spięte z płatnościami P24); admin przy `users.is_admin`.
  * `role_invitations` — link, który Łukasz wręcza sołtysowi po rozmowie
    telefonicznej. Weryfikacja dzieje się w tej rozmowie, więc przyjęcie
    zaproszenia nadaje rolę od razu.
  * `solectwo_posts` — zdjęcie pisma → odczyt modelem → moderacja → artykuł.
    Zdjęcia NIE leżą w `/app/uploads` (to katalog publiczny: montuje go FastAPI
    i Caddy), tylko w osobnym wolumenie `private_uploads`.

Plus źródło „RybnoLive - Sołectwa", pod którym opublikowane ogłoszenia wchodzą
do `articles` — a więc do feedu, briefingu, newslettera, kalendarza i RAG bez
żadnej osobnej ścieżki.

⚠️ Migracja PRZED kodem (tabele, których stary kod nie zna, nikomu nie szkodzą).

Idempotentna.

Użycie:
    cd backend && python -m scripts.migrations.add_user_roles_and_solectwo_posts
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import settings

SOURCE_NAME = "RybnoLive - Sołectwa"

STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS user_roles (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role VARCHAR(30) NOT NULL,
        scope VARCHAR(100) NOT NULL DEFAULT '',
        status VARCHAR(20) NOT NULL DEFAULT 'verified',
        method VARCHAR(20) NOT NULL DEFAULT 'manual',
        verified_by VARCHAR(255),
        verified_at TIMESTAMP,
        revoked_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles (user_id)",
    # Jedna żywa rola danego rodzaju i zakresu na konto — odwołana nie blokuje
    # ponownego nadania (nowa kadencja, pomyłka admina)
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_user_roles_live
        ON user_roles (user_id, role, scope)
        WHERE status <> 'revoked'
    """,
    """
    CREATE TABLE IF NOT EXISTS role_invitations (
        id SERIAL PRIMARY KEY,
        token VARCHAR(64) NOT NULL UNIQUE,
        role VARCHAR(30) NOT NULL,
        scope VARCHAR(100) NOT NULL DEFAULT '',
        invitee_label VARCHAR(100),
        created_by VARCHAR(255),
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        expires_at TIMESTAMP NOT NULL,
        used_at TIMESTAMP,
        used_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        revoked_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS solectwo_posts (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        role_id INTEGER REFERENCES user_roles(id) ON DELETE SET NULL,
        solectwo VARCHAR(100) NOT NULL,
        signed_as VARCHAR(150) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'processing',
        note TEXT,
        image_files JSONB NOT NULL DEFAULT '[]'::jsonb,
        title VARCHAR(200),
        summary TEXT,
        transcript TEXT,
        doc_type VARCHAR(100),
        event_at TIMESTAMP,
        event_until TIMESTAMP,
        personal_data JSONB,
        illegible JSONB,
        ai_error TEXT,
        article_id INTEGER REFERENCES articles(id) ON DELETE SET NULL,
        moderated_by VARCHAR(255),
        moderated_at TIMESTAMP,
        reject_reason VARCHAR(500),
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        published_at TIMESTAMP,
        images_deleted_at TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_solectwo_posts_status ON solectwo_posts (status)",
    "CREATE INDEX IF NOT EXISTS idx_solectwo_posts_user ON solectwo_posts (user_id)",
]


async def migrate():
    print("=" * 70)
    print("Migration: user_roles + role_invitations + solectwo_posts")
    print("=" * 70)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        for sql in STATEMENTS:
            await conn.execute(text(sql))
        print("✓ tabele i indeksy")

        row = (await conn.execute(
            text("SELECT id FROM sources WHERE name = :name"), {"name": SOURCE_NAME}
        )).fetchone()
        if row:
            print(f"✓ źródło '{SOURCE_NAME}' już jest (id={row.id})")
        else:
            # `disabled`: nic z niego nie scrapujemy — to tylko atrybucja dla
            # ogłoszeń zatwierdzonych w moderacji (jak „Łaciate Mazury MTB")
            await conn.execute(text("""
                INSERT INTO sources (name, type, url, status, created_at)
                VALUES (:name, 'community', :url, 'disabled', NOW())
            """), {"name": SOURCE_NAME, "url": settings.APP_URL})
            print(f"✓ dodane źródło '{SOURCE_NAME}'")

    await engine.dispose()
    print("\n✓ Gotowe.")


if __name__ == "__main__":
    asyncio.run(migrate())
