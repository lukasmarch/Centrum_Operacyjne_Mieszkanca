"""add reports table

Revision ID: f1a2b3c4d5e6
Revises: a7d27cd6a965
Create Date: 2026-02-14 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = '71cfcbfd9588'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), nullable=False),
        # Author
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('author_name', sa.String(100), nullable=True),
        sa.Column('author_email', sa.String(255), nullable=True),
        sa.Column('author_phone', sa.String(50), nullable=True),
        # Content
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('ai_summary', sa.Text(), nullable=True),
        # AI categorization
        sa.Column('category', sa.String(50), nullable=False, server_default='other'),
        sa.Column('ai_detected_objects', JSONB(), nullable=True),
        sa.Column('ai_condition_assessment', sa.String(500), nullable=True),
        sa.Column('ai_severity', sa.String(20), nullable=True),
        # Media
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('generated_image_url', sa.String(500), nullable=True),
        # Geolocation
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('address', sa.String(300), nullable=True),
        sa.Column('location_name', sa.String(100), nullable=True),
        # Status
        sa.Column('status', sa.String(20), nullable=False, server_default='new'),
        sa.Column('is_spam', sa.Boolean(), nullable=False, server_default='false'),
        # Interaction
        sa.Column('upvotes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('views_count', sa.Integer(), nullable=False, server_default='0'),
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_reports_category', 'reports', ['category'])
    op.create_index('idx_reports_status', 'reports', ['status'])
    op.create_index('idx_reports_created_at', 'reports', ['created_at'])
    op.create_index('idx_reports_user_id', 'reports', ['user_id'])


def downgrade() -> None:
    op.drop_index('idx_reports_user_id', table_name='reports')
    op.drop_index('idx_reports_created_at', table_name='reports')
    op.drop_index('idx_reports_status', table_name='reports')
    op.drop_index('idx_reports_category', table_name='reports')
    op.drop_table('reports')
