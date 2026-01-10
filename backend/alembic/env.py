from logging.config import fileConfig
from sqlalchemy import pool, engine_from_config
from alembic import context
from src.database.schema import SQLModel

config = context.config
fileConfig(config.config_file_name)
target_metadata = SQLModel.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    # Convert asyncpg URL to psycopg2 for migrations
    url = config.get_main_option("sqlalchemy.url")
    if url and "postgresql+asyncpg" in url:
        url = url.replace("postgresql+asyncpg", "postgresql")

    config.set_main_option("sqlalchemy.url", url)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema=None,
            include_object=lambda obj, name, type_, reflected, compare_to: (
                # Exclude PostGIS/Tiger tables
                type_ != "table" or not any(
                    name.startswith(prefix) for prefix in [
                        'tiger', 'topology', 'spatial_ref_sys', 'geocode_settings',
                        'loader_', 'pagc_', 'zip_', 'place', 'county', 'state', 'direction',
                        'secondary_unit', 'street_type', 'addr', 'addrfeat', 'bg', 'county_lookup',
                        'countysub', 'cousub', 'edges', 'faces', 'featnames', 'tabblock', 'zcta5'
                    ]
                )
            )
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
