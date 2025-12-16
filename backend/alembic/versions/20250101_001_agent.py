"""initial agent tables

Revision ID: 001_agent
Revises: 
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_agent'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. Agent Chat History (Legacy/Manual) ---
    # chat_streams
    op.create_table(
        'chat_streams',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('thread_id', sa.String(length=255), nullable=False),
        sa.Column('messages', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('thread_id')
    )
    op.create_index('idx_chat_streams_thread_id', 'chat_streams', ['thread_id'], unique=False)
    op.create_index('idx_chat_streams_ts', 'chat_streams', ['ts'], unique=False)

    # --- 2. LangGraph Checkpointing Tables (AsyncPostgresSaver) ---
    # checkpoints
    op.create_table(
        'checkpoints',
        sa.Column('thread_id', sa.Text(), nullable=False),
        sa.Column('checkpoint_ns', sa.Text(), server_default='', nullable=False),
        sa.Column('checkpoint_id', sa.Text(), nullable=False),
        sa.Column('parent_checkpoint_id', sa.Text(), nullable=True),
        sa.Column('type', sa.Text(), nullable=True),
        sa.Column('checkpoint', postgresql.BYTEA(), nullable=True),
        sa.Column('metadata', postgresql.BYTEA(), nullable=True),
        sa.PrimaryKeyConstraint('thread_id', 'checkpoint_ns', 'checkpoint_id')
    )

    # checkpoint_blobs
    op.create_table(
        'checkpoint_blobs',
        sa.Column('thread_id', sa.Text(), nullable=False),
        sa.Column('checkpoint_ns', sa.Text(), server_default='', nullable=False),
        sa.Column('channel', sa.Text(), nullable=False),
        sa.Column('version', sa.Text(), nullable=False),
        sa.Column('type', sa.Text(), nullable=True),
        sa.Column('blob', postgresql.BYTEA(), nullable=True),
        sa.PrimaryKeyConstraint('thread_id', 'checkpoint_ns', 'channel', 'version')
    )

    # checkpoint_writes
    op.create_table(
        'checkpoint_writes',
        sa.Column('thread_id', sa.Text(), nullable=False),
        sa.Column('checkpoint_ns', sa.Text(), server_default='', nullable=False),
        sa.Column('checkpoint_id', sa.Text(), nullable=False),
        sa.Column('task_id', sa.Text(), nullable=False),
        sa.Column('idx', sa.Integer(), nullable=False),
        sa.Column('channel', sa.Text(), nullable=False),
        sa.Column('type', sa.Text(), nullable=True),
        sa.Column('blob', postgresql.BYTEA(), nullable=True),
        sa.PrimaryKeyConstraint('thread_id', 'checkpoint_ns', 'checkpoint_id', 'task_id', 'idx')
    )

    # checkpoint_migrations (Internal tracking for LangGraph)
    op.create_table(
        'checkpoint_migrations',
        sa.Column('v', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('v')
    )


def downgrade() -> None:
    op.drop_table('checkpoint_migrations')
    op.drop_table('checkpoint_writes')
    op.drop_table('checkpoint_blobs')
    op.drop_table('checkpoints')
    op.drop_index('idx_chat_streams_ts', table_name='chat_streams')
    op.drop_index('idx_chat_streams_thread_id', table_name='chat_streams')
    op.drop_table('chat_streams')
