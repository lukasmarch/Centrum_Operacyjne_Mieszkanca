"""
Add GUS Database-First tables for monthly data refresh architecture

Creates 3 new tables:
1. gus_data_refresh_log - Tracking odświeżania zmiennych
2. gus_national_averages - Średnie krajowe/wojewódzkie
3. gus_insights - AI-generowane analizy (Business tier)

Run this ONCE after updating schema.py
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.config import settings


async def add_gus_tables():
    """Add GUS database-first tables"""
    print("="*80)
    print("Adding GUS Database-First Tables")
    print("="*80)

    engine = create_async_engine(settings.DATABASE_URL, echo=True)

    async with engine.begin() as conn:
        # ========================================
        # 1. GUSDataRefreshLog
        # ========================================
        print("\n📝 Creating table: gus_data_refresh_log...")

        result = await conn.execute(text("""
            SELECT tablename
            FROM pg_tables
            WHERE tablename = 'gus_data_refresh_log'
        """))
        if result.first():
            print("✓ Table 'gus_data_refresh_log' already exists - skipping")
        else:
            await conn.execute(text("""
                CREATE TABLE gus_data_refresh_log (
                    id SERIAL PRIMARY KEY,
                    var_key VARCHAR(100) NOT NULL UNIQUE,
                    var_id VARCHAR(20) NOT NULL,
                    last_refresh TIMESTAMP NOT NULL DEFAULT NOW(),
                    records_updated INTEGER NOT NULL DEFAULT 0,
                    status VARCHAR(20) NOT NULL DEFAULT 'success',
                    error_message VARCHAR(500),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
            await conn.execute(text("""
                CREATE UNIQUE INDEX idx_gus_refresh_var_key ON gus_data_refresh_log(var_key)
            """))
            print("✅ Table 'gus_data_refresh_log' created!")

        # ========================================
        # 2. GUSNationalAverages
        # ========================================
        print("\n📝 Creating table: gus_national_averages...")

        result = await conn.execute(text("""
            SELECT tablename
            FROM pg_tables
            WHERE tablename = 'gus_national_averages'
        """))
        if result.first():
            print("✓ Table 'gus_national_averages' already exists - skipping")
        else:
            await conn.execute(text("""
                CREATE TABLE gus_national_averages (
                    id SERIAL PRIMARY KEY,
                    var_id VARCHAR(20) NOT NULL,
                    var_key VARCHAR(100) NOT NULL,
                    year INTEGER NOT NULL,
                    level VARCHAR(20) NOT NULL,
                    value FLOAT,
                    fetched_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
            await conn.execute(text("""
                CREATE UNIQUE INDEX idx_gus_avg_var_year_level
                ON gus_national_averages(var_id, year, level)
            """))
            await conn.execute(text("""
                CREATE INDEX idx_gus_avg_var_id ON gus_national_averages(var_id)
            """))
            await conn.execute(text("""
                CREATE INDEX idx_gus_avg_var_key ON gus_national_averages(var_key)
            """))
            await conn.execute(text("""
                CREATE INDEX idx_gus_avg_year ON gus_national_averages(year)
            """))
            await conn.execute(text("""
                CREATE INDEX idx_gus_avg_level ON gus_national_averages(level)
            """))
            print("✅ Table 'gus_national_averages' created!")

        # ========================================
        # 3. GUSInsight (niższy priorytet)
        # ========================================
        print("\n📝 Creating table: gus_insights...")

        result = await conn.execute(text("""
            SELECT tablename
            FROM pg_tables
            WHERE tablename = 'gus_insights'
        """))
        if result.first():
            print("✓ Table 'gus_insights' already exists - skipping")
        else:
            await conn.execute(text("""
                CREATE TABLE gus_insights (
                    id SERIAL PRIMARY KEY,
                    category VARCHAR(50) NOT NULL,
                    insight_type VARCHAR(50) NOT NULL,
                    content VARCHAR(2000) NOT NULL,
                    data_context JSONB NOT NULL DEFAULT '{}'::jsonb,
                    generated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    valid_until TIMESTAMP NOT NULL
                )
            """))
            await conn.execute(text("""
                CREATE INDEX idx_gus_insight_category ON gus_insights(category)
            """))
            print("✅ Table 'gus_insights' created!")

    await engine.dispose()

    print("\n" + "="*80)
    print("✓ Migration completed successfully!")
    print("="*80)
    print("\nCreated tables:")
    print("  1. gus_data_refresh_log - Tracking zmiennych (88 vars)")
    print("  2. gus_national_averages - Średnie krajowe/wojewódzkie")
    print("  3. gus_insights - AI analizy (Business tier)")
    print("\nNext steps:")
    print("  1. Run populate_gus_data.py (jednorazowo)")
    print("  2. Configure scheduler monthly refresh")


if __name__ == "__main__":
    try:
        asyncio.run(add_gus_tables())
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
