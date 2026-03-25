"""Add connectors table for OAuth integrations

Revision ID: 8b9c0d1e2f3a
Revises: a1b2c3d4e5f6
Create Date: 2026-01-31 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8b9c0d1e2f3a'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create connectors table for external service OAuth integrations."""
    op.create_table(
        'connectors',
        # Primary key
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Primary key ID'),

        # Foreign key to user
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('sys_user.id', ondelete='CASCADE'), nullable=False, comment='User who owns this connector'),

        # Connector type
        sa.Column('connector_type', sa.String(50), nullable=False, comment='Type of connector: google_drive, dropbox, etc.'),

        # OAuth token fields
        sa.Column('access_token', sa.Text(), nullable=True, comment='OAuth access token'),
        sa.Column('refresh_token', sa.Text(), nullable=True, comment='OAuth refresh token for token renewal'),
        sa.Column('token_expiry', sa.DateTime(timezone=True), nullable=True, comment='Access token expiration timestamp'),

        # Metadata (JSONB for PostgreSQL)
        sa.Column('connector_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Service-specific metadata'),

        # Timestamps (from DateTimeMixin)
        sa.Column('created_time', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment='Created timestamp'),
        sa.Column('updated_time', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True, comment='Updated timestamp'),

        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'connector_type', name='uq_user_connector_type'),

        # Comment
        comment='External service connectors for OAuth integrations'
    )

    # Create indexes
    op.create_index('idx_connector_user_id', 'connectors', ['user_id'])
    op.create_index('idx_connector_type', 'connectors', ['connector_type'])
    op.create_index('idx_connector_user_type', 'connectors', ['user_id', 'connector_type'])


def downgrade() -> None:
    """Drop connectors table."""
    op.drop_index('idx_connector_user_type', table_name='connectors')
    op.drop_index('idx_connector_type', table_name='connectors')
    op.drop_index('idx_connector_user_id', table_name='connectors')
    op.drop_table('connectors')
