"""add_session_wishlists_table

Revision ID: a1b2c3d4e5f6
Revises: 4f7492588793
Create Date: 2026-01-31 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '4f7492588793'
branch_labels = None
depends_on = None


def upgrade():
    """Create session_wishlists table for user session bookmarks."""
    op.create_table(
        'session_wishlists',
        sa.Column('id', sa.String(36), primary_key=True, comment='Unique wishlist entry ID'),
        sa.Column(
            'user_id',
            sa.BigInteger(),
            sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
            nullable=False,
            comment='User who wishlisted the session'
        ),
        sa.Column(
            'session_id',
            sa.String(64),
            sa.ForeignKey('agent_chat_sessions.uuid', ondelete='CASCADE'),
            nullable=False,
            comment='UUID of the wishlisted session'
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            comment='When the session was added to wishlist'
        ),
        sa.UniqueConstraint('user_id', 'session_id', name='uq_user_session_wishlist'),
        comment='User session wishlist/bookmarks'
    )

    # Create indexes for faster lookups
    op.create_index('idx_wishlist_user_id', 'session_wishlists', ['user_id'])
    op.create_index('idx_wishlist_session_id', 'session_wishlists', ['session_id'])


def downgrade():
    """Drop session_wishlists table."""
    op.drop_index('idx_wishlist_session_id', table_name='session_wishlists')
    op.drop_index('idx_wishlist_user_id', table_name='session_wishlists')
    op.drop_table('session_wishlists')
