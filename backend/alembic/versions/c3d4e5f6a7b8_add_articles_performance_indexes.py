"""Add articles performance indexes

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-01-27 16:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add performance indexes to articles table:
    - ix_articles_published_at: Used in ORDER BY queries
    - ix_articles_processed: Used in WHERE filters
    - ix_articles_category: Used in GROUP BY and filtering
    """
    # Add index on published_at (used for sorting recent articles)
    op.create_index(
        'ix_articles_published_at',
        'articles',
        ['published_at'],
        unique=False
    )

    # Add index on processed (used for filtering unprocessed articles)
    op.create_index(
        'ix_articles_processed',
        'articles',
        ['processed'],
        unique=False
    )

    # Add index on category (used for filtering by category and analytics)
    op.create_index(
        'ix_articles_category',
        'articles',
        ['category'],
        unique=False
    )


def downgrade() -> None:
    """Remove performance indexes"""
    op.drop_index('ix_articles_category', table_name='articles')
    op.drop_index('ix_articles_processed', table_name='articles')
    op.drop_index('ix_articles_published_at', table_name='articles')
