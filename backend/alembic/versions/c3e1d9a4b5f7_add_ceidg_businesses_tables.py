"""Add CEIDG businesses tables

Revision ID: c3e1d9a4b5f7
Revises: 70f98d07849e
Create Date: 2026-02-05 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c3e1d9a4b5f7'
down_revision = '70f98d07849e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ceidg_businesses table
    op.create_table(
        'ceidg_businesses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ceidg_id', sa.String(length=50), nullable=False),
        sa.Column('nazwa', sa.String(length=500), nullable=False),
        sa.Column('nip', sa.String(length=20), nullable=False),
        sa.Column('regon', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, default='AKTYWNY'),
        sa.Column('data_rozpoczecia', sa.DateTime(), nullable=True),
        sa.Column('wlasciciel_imie', sa.String(length=100), nullable=True),
        sa.Column('wlasciciel_nazwisko', sa.String(length=100), nullable=True),
        sa.Column('ulica', sa.String(length=200), nullable=True),
        sa.Column('budynek', sa.String(length=20), nullable=True),
        sa.Column('lokal', sa.String(length=20), nullable=True),
        sa.Column('miasto', sa.String(length=100), nullable=False),
        sa.Column('kod_pocztowy', sa.String(length=10), nullable=False),
        sa.Column('gmina', sa.String(length=100), nullable=False),
        sa.Column('powiat', sa.String(length=100), nullable=False),
        sa.Column('wojewodztwo', sa.String(length=100), nullable=True),
        sa.Column('raw_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ceidg_link', sa.String(length=500), nullable=True),
        sa.Column('fetched_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ceidg_businesses_ceidg_id', 'ceidg_businesses', ['ceidg_id'], unique=True)
    op.create_index('idx_ceidg_nip', 'ceidg_businesses', ['nip'], unique=False)
    op.create_index('idx_ceidg_miasto', 'ceidg_businesses', ['miasto'], unique=False)
    op.create_index('idx_ceidg_gmina_powiat', 'ceidg_businesses', ['gmina', 'powiat'], unique=False)

    # Create ceidg_sync_stats table
    op.create_table(
        'ceidg_sync_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gmina', sa.String(length=100), nullable=False),
        sa.Column('powiat', sa.String(length=100), nullable=False),
        sa.Column('total_count', sa.Integer(), nullable=False, default=0),
        sa.Column('active_count', sa.Integer(), nullable=False, default=0),
        sa.Column('by_miejscowosc', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('last_sync', sa.DateTime(), nullable=False),
        sa.Column('sync_status', sa.String(length=20), nullable=False, default='success'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ceidg_sync_stats_gmina', 'ceidg_sync_stats', ['gmina'], unique=True)


def downgrade() -> None:
    op.drop_table('ceidg_sync_stats')
    op.drop_table('ceidg_businesses')
