"""add_agent_mcp_settings

Revision ID: faa10906a0a1
Revises: 809cc3c0ed5a
Create Date: 2025-12-28 15:38:26.573489

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'faa10906a0a1'
down_revision = '809cc3c0ed5a'
branch_labels = None
depends_on = None


def upgrade():
    # Create agent_mcp_settings table
    op.create_table('agent_mcp_settings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键 ID'),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='User who owns this MCP setting'),
        sa.Column('tool_type', sa.String(length=64), nullable=False, comment='MCP tool type (codex, claude_code, or custom)'),
        sa.Column('mcp_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='MCP server configuration JSON'),
        sa.Column('auth_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Authentication credentials JSON'),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Additional metadata (model, reasoning_effort, etc.)'),
        sa.Column('is_active', sa.Boolean(), nullable=False, comment='Whether this MCP setting is active'),
        sa.Column('store_path', sa.String(length=256), nullable=True, comment='Path in sandbox where credentials are written'),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False, comment='创建时间'),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['user_id'], ['sys_user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'tool_type', name='uq_user_tool_type'),
        comment='User MCP tool configurations'
    )
    op.create_index(op.f('ix_agent_mcp_settings_is_active'), 'agent_mcp_settings', ['is_active'], unique=False)
    op.create_index(op.f('ix_agent_mcp_settings_tool_type'), 'agent_mcp_settings', ['tool_type'], unique=False)
    op.create_index(op.f('ix_agent_mcp_settings_user_id'), 'agent_mcp_settings', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_agent_mcp_settings_user_id'), table_name='agent_mcp_settings')
    op.drop_index(op.f('ix_agent_mcp_settings_tool_type'), table_name='agent_mcp_settings')
    op.drop_index(op.f('ix_agent_mcp_settings_is_active'), table_name='agent_mcp_settings')
    op.drop_table('agent_mcp_settings')
