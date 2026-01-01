"""add_slide_content_table

Revision ID: 4f7492588793
Revises: 20241231_001_billing
Create Date: 2026-01-01 08:57:13.045841

"""
from alembic import op
import sqlalchemy as sa
import backend.common.model
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '4f7492588793'
down_revision = '20241231_001_billing'
branch_labels = None
depends_on = None


def upgrade():
    """Create slide_content table for persistent slide storage."""
    # Create slide_content table
    op.create_table('slide_content',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键 ID'),
        sa.Column('thread_id', sa.String(length=64), nullable=False, comment='Thread/Session ID that owns this slide'),
        sa.Column('presentation_name', sa.String(length=255), nullable=False, comment='Name of the presentation'),
        sa.Column('slide_number', sa.Integer(), nullable=False, comment='Slide number (1-indexed)'),
        sa.Column('slide_title', sa.String(length=500), nullable=True, comment='Title of the slide'),
        sa.Column('slide_content', backend.common.model.UniversalText(), nullable=True, comment='Full HTML content of the slide'),
        sa.Column('slide_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Additional metadata (tool_name, description, etc.)'),
        sa.Column('created_time', backend.common.model.TimeZone(timezone=True), nullable=False, comment='创建时间'),
        sa.Column('updated_time', backend.common.model.TimeZone(timezone=True), nullable=True, comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('thread_id', 'presentation_name', 'slide_number', name='uq_slide_content_location'),
        comment='Persistent storage for slide HTML content'
    )
    op.create_index(op.f('ix_slide_content_id'), 'slide_content', ['id'], unique=True)
    op.create_index(op.f('ix_slide_content_presentation_name'), 'slide_content', ['presentation_name'], unique=False)
    op.create_index(op.f('ix_slide_content_thread_id'), 'slide_content', ['thread_id'], unique=False)


def downgrade():
    """Drop slide_content table."""
    op.drop_index(op.f('ix_slide_content_thread_id'), table_name='slide_content')
    op.drop_index(op.f('ix_slide_content_presentation_name'), table_name='slide_content')
    op.drop_index(op.f('ix_slide_content_id'), table_name='slide_content')
    op.drop_table('slide_content')
