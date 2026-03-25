"""Add sandbox_id to session metrics.

Revision ID: 7a8c9d0e1f2b
Revises: faa10906a0a1
Create Date: 2025-12-29 07:03:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a8c9d0e1f2b'
down_revision: Union[str, None] = 'faa10906a0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add sandbox_id column to agent_session_metrics table.
    
    - Each session can be linked to a sandbox
    - When a session requests a sandbox, we first check if one is already linked
    - This avoids creating duplicate sandboxes for the same chat session
    """
    # Add sandbox_id column (nullable, since existing sessions won't have one)
    op.add_column(
        'agent_session_metrics',
        sa.Column(
            'sandbox_id',
            sa.String(64),
            nullable=True,
            comment='Linked sandbox ID for this session'
        )
    )
    
    # Add index for efficient lookups
    op.create_index(
        'ix_agent_session_metrics_sandbox_id',
        'agent_session_metrics',
        ['sandbox_id'],
        unique=False
    )


def downgrade() -> None:
    """Remove sandbox_id column from agent_session_metrics table."""
    # Drop index first
    op.drop_index('ix_agent_session_metrics_sandbox_id', table_name='agent_session_metrics')
    
    # Drop column
    op.drop_column('agent_session_metrics', 'sandbox_id')
