"""Add billing and credit management tables

Revision ID: 20241231_001_billing
Revises: fcb99977d5b6
Create Date: 2024-12-31 18:00:00.000000

This migration adds the core billing infrastructure tables:
- credit_accounts: User credit balances and subscription status
- credit_ledger: Complete transaction history for credits
- credit_purchases: One-time credit purchase tracking
- trial_history: Trial usage tracking
- circuit_breaker_state: Stripe API circuit breaker state
- commitment_history: Yearly commitment tracking
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20241231_001_billing'
down_revision: Union[str, None] = 'fcb99977d5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create billing tables."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    # -------------------------------------------------------------------------
    # 1. credit_accounts - Main credit account table
    # -------------------------------------------------------------------------
    if 'credit_accounts' not in existing_tables:
        op.create_table(
            'credit_accounts',
            # Primary key
            sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
            sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True, comment='User/account ID'),
            
            # Credit balances (stored in dollars)
            sa.Column('balance', sa.DECIMAL(precision=10, scale=2), server_default='0.00', nullable=False, comment='Total balance'),
            sa.Column('expiring_credits', sa.DECIMAL(precision=10, scale=2), server_default='0.00', nullable=False, comment='Monthly subscription credits'),
            sa.Column('non_expiring_credits', sa.DECIMAL(precision=10, scale=2), server_default='0.00', nullable=False, comment='Purchased credits (never expire)'),
            sa.Column('daily_credits_balance', sa.DECIMAL(precision=10, scale=2), server_default='0.00', nullable=False, comment='Daily refresh credits (free tier)'),
            
            # Subscription info
            sa.Column('tier', sa.String(length=50), server_default='none', nullable=False, comment='Subscription tier name'),
            sa.Column('plan_type', sa.String(length=50), nullable=True, comment='monthly, yearly, yearly_commitment'),
            sa.Column('provider', sa.String(length=20), server_default='stripe', nullable=False, comment='Payment provider'),
            
            # Stripe references
            sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True, comment='Stripe subscription ID'),
            sa.Column('stripe_customer_id', sa.String(length=255), nullable=True, comment='Stripe customer ID'),
            
            # Trial info
            sa.Column('trial_status', sa.String(length=20), server_default='none', nullable=False, comment='none, active, expired, converted, cancelled'),
            sa.Column('trial_ends_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='When trial ends'),
            
            # Billing cycle info
            sa.Column('billing_cycle_anchor', sa.TIMESTAMP(timezone=True), nullable=True, comment='Billing cycle start date'),
            sa.Column('next_credit_grant', sa.TIMESTAMP(timezone=True), nullable=True, comment='Next scheduled credit grant'),
            sa.Column('last_grant_date', sa.TIMESTAMP(timezone=True), nullable=True, comment='Last time credits were granted'),
            sa.Column('last_daily_refresh', sa.TIMESTAMP(timezone=True), nullable=True, comment='Last daily credit refresh'),
            
            # Scheduled changes
            sa.Column('scheduled_tier_change', sa.String(length=50), nullable=True, comment='Scheduled tier change'),
            sa.Column('scheduled_change_date', sa.TIMESTAMP(timezone=True), nullable=True, comment='When tier change takes effect'),
            
            # Payment status
            sa.Column('payment_status', sa.String(length=20), server_default='active', nullable=True, comment='active, past_due, cancelled'),
            
            # RevenueCat (mobile) fields
            sa.Column('revenuecat_subscription_id', sa.String(length=255), nullable=True),
            sa.Column('revenuecat_product_id', sa.String(length=255), nullable=True),
            sa.Column('revenuecat_cancelled_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('revenuecat_cancel_at_period_end', sa.TIMESTAMP(timezone=True), nullable=True),
            
            # Commitment tracking (yearly plans)
            sa.Column('commitment_type', sa.String(length=50), nullable=True),
            sa.Column('commitment_start_date', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('commitment_end_date', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('commitment_price_id', sa.String(length=255), nullable=True),
            sa.Column('can_cancel_after', sa.TIMESTAMP(timezone=True), nullable=True),
            
            # Timestamps
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            
            sa.PrimaryKeyConstraint('id'),
        )
        
        # Indexes for credit_accounts
        op.create_index('idx_credit_accounts_account_id', 'credit_accounts', ['account_id'], unique=True)
        op.create_index('idx_credit_accounts_tier', 'credit_accounts', ['tier'])
        op.create_index('idx_credit_accounts_stripe_subscription_id', 'credit_accounts', ['stripe_subscription_id'])
        op.create_index('idx_credit_accounts_stripe_customer_id', 'credit_accounts', ['stripe_customer_id'])
        op.create_index('idx_credit_accounts_trial_status', 'credit_accounts', ['trial_status'])
    
    # -------------------------------------------------------------------------
    # 2. credit_ledger - Transaction history for all credit operations
    # -------------------------------------------------------------------------
    if 'credit_ledger' not in existing_tables:
        op.create_table(
            'credit_ledger',
            sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
            sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False, comment='Reference to credit_accounts'),
            
            # Transaction details
            sa.Column('amount', sa.DECIMAL(precision=10, scale=4), nullable=False, comment='Positive for adds, negative for deductions'),
            sa.Column('balance_after', sa.DECIMAL(precision=10, scale=2), nullable=True, comment='Balance after this transaction'),
            sa.Column('type', sa.String(length=50), nullable=False, comment='usage, purchase, tier_grant, refund, adjustment, daily_refresh'),
            sa.Column('description', sa.Text(), nullable=True, comment='Human-readable description'),
            
            # Credit type
            sa.Column('is_expiring', sa.Boolean(), server_default='true', nullable=False, comment='Whether these credits expire'),
            sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='When these credits expire'),
            sa.Column('credit_id', postgresql.UUID(as_uuid=True), nullable=True, comment='Reference to specific credit batch'),
            
            # External references
            sa.Column('stripe_event_id', sa.String(length=255), nullable=True, comment='Stripe event ID for deduplication'),
            
            # Usage tracking
            sa.Column('thread_id', sa.String(length=64), nullable=True, comment='Thread/conversation ID'),
            sa.Column('message_id', sa.String(length=64), nullable=True, comment='Message ID'),
            sa.Column('model', sa.String(length=100), nullable=True, comment='LLM model used'),
            sa.Column('input_tokens', sa.Integer(), nullable=True, comment='Input tokens consumed'),
            sa.Column('output_tokens', sa.Integer(), nullable=True, comment='Output tokens consumed'),
            
            # Generic metadata
            sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            
            # Timestamps
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            
            sa.PrimaryKeyConstraint('id'),
        )
        
        # Indexes for credit_ledger
        op.create_index('idx_credit_ledger_account_id', 'credit_ledger', ['account_id'])
        op.create_index('idx_credit_ledger_type', 'credit_ledger', ['type'])
        op.create_index('idx_credit_ledger_created_at', 'credit_ledger', ['created_at'])
        op.create_index('idx_credit_ledger_stripe_event_id', 'credit_ledger', ['stripe_event_id'])
        op.create_index('idx_credit_ledger_thread_id', 'credit_ledger', ['thread_id'])
    
    # -------------------------------------------------------------------------
    # 3. credit_purchases - One-time credit purchases
    # -------------------------------------------------------------------------
    if 'credit_purchases' not in existing_tables:
        op.create_table(
            'credit_purchases',
            sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
            sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False, comment='Reference to credit_accounts'),
            
            # Purchase details
            sa.Column('amount_dollars', sa.DECIMAL(precision=10, scale=2), nullable=False, comment='Amount in dollars'),
            sa.Column('status', sa.String(length=20), server_default='pending', nullable=False, comment='pending, completed, failed, refunded'),
            
            # Stripe references
            sa.Column('stripe_payment_intent_id', sa.String(length=255), nullable=True),
            sa.Column('stripe_checkout_session_id', sa.String(length=255), nullable=True),
            
            # Metadata
            sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            
            # Reconciliation
            sa.Column('reconciled_at', sa.TIMESTAMP(timezone=True), nullable=True),
            
            # Timestamps
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
            
            sa.PrimaryKeyConstraint('id'),
        )
        
        # Indexes for credit_purchases
        op.create_index('idx_credit_purchases_account_id', 'credit_purchases', ['account_id'])
        op.create_index('idx_credit_purchases_status', 'credit_purchases', ['status'])
        op.create_index('idx_credit_purchases_stripe_payment_intent_id', 'credit_purchases', ['stripe_payment_intent_id'])
        op.create_index('idx_credit_purchases_created_at', 'credit_purchases', ['created_at'])
    
    # -------------------------------------------------------------------------
    # 4. trial_history - Trial usage tracking
    # -------------------------------------------------------------------------
    if 'trial_history' not in existing_tables:
        op.create_table(
            'trial_history',
            sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
            sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True, comment='One trial per account'),
            
            # Trial lifecycle
            sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('ended_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('converted_to_paid', sa.Boolean(), server_default='false', nullable=False),
            sa.Column('status', sa.String(length=30), server_default='none', nullable=False, 
                      comment='none, checkout_pending, checkout_created, checkout_failed, active, expired, converted, cancelled'),
            
            # Stripe references
            sa.Column('stripe_checkout_session_id', sa.String(length=255), nullable=True),
            sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True),
            
            # Error tracking
            sa.Column('error_message', sa.Text(), nullable=True),
            
            sa.PrimaryKeyConstraint('id'),
        )
        
        # Indexes for trial_history
        op.create_index('idx_trial_history_account_id', 'trial_history', ['account_id'], unique=True)
        op.create_index('idx_trial_history_status', 'trial_history', ['status'])
    
    # -------------------------------------------------------------------------
    # 5. circuit_breaker_state - Stripe API circuit breaker
    # -------------------------------------------------------------------------
    if 'circuit_breaker_state' not in existing_tables:
        op.create_table(
            'circuit_breaker_state',
            sa.Column('circuit_name', sa.String(length=100), nullable=False, comment='Name of the circuit (e.g., stripe_api)'),
            sa.Column('state', sa.String(length=20), server_default='closed', nullable=False, comment='closed, open, half_open'),
            sa.Column('failure_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('success_count', sa.Integer(), server_default='0', nullable=False),
            sa.Column('last_failure_time', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('last_success_time', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('opened_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            
            sa.PrimaryKeyConstraint('circuit_name'),
        )
    
    # -------------------------------------------------------------------------
    # 6. commitment_history - Yearly commitment tracking
    # -------------------------------------------------------------------------
    if 'commitment_history' not in existing_tables:
        op.create_table(
            'commitment_history',
            sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
            sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
            
            # Commitment details
            sa.Column('commitment_type', sa.String(length=50), nullable=False, comment='yearly_commitment'),
            sa.Column('price_id', sa.String(length=255), nullable=True, comment='Stripe price ID'),
            sa.Column('start_date', sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column('end_date', sa.TIMESTAMP(timezone=True), nullable=False),
            
            # Stripe references
            sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True),
            
            # Status
            sa.Column('status', sa.String(length=20), server_default='active', nullable=False, comment='active, completed, cancelled'),
            
            # Timestamps
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            
            sa.PrimaryKeyConstraint('id'),
        )
        
        # Indexes for commitment_history
        op.create_index('idx_commitment_history_account_id', 'commitment_history', ['account_id'])
        op.create_index('idx_commitment_history_stripe_subscription_id', 'commitment_history', ['stripe_subscription_id'])
    
    # -------------------------------------------------------------------------
    # 7. webhook_events - Stripe webhook event tracking (for idempotency)
    # -------------------------------------------------------------------------
    if 'webhook_events' not in existing_tables:
        op.create_table(
            'webhook_events',
            sa.Column('id', sa.String(length=255), nullable=False, comment='Stripe event ID'),
            sa.Column('event_type', sa.String(length=100), nullable=False),
            sa.Column('status', sa.String(length=20), server_default='processing', nullable=False, comment='processing, completed, failed'),
            sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
            
            sa.PrimaryKeyConstraint('id'),
        )
        
        # Indexes for webhook_events
        op.create_index('idx_webhook_events_event_type', 'webhook_events', ['event_type'])
        op.create_index('idx_webhook_events_status', 'webhook_events', ['status'])
        op.create_index('idx_webhook_events_created_at', 'webhook_events', ['created_at'])


def downgrade() -> None:
    """Drop billing tables in reverse order."""
    op.drop_table('webhook_events')
    op.drop_table('commitment_history')
    op.drop_table('circuit_breaker_state')
    op.drop_table('trial_history')
    op.drop_table('credit_purchases')
    op.drop_table('credit_ledger')
    op.drop_table('credit_accounts')
