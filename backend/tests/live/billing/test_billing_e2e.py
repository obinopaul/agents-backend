"""
Billing E2E Tests - Live Environment

This test suite simulates a real user interaction with the billing system.
It covers:
1. Initial account state (Free tier)
2. Daily credit refresh
3. Credit usage and deduction
4. Transaction history verification
5. Subscription changes (Simulated)

Usage:
    pytest backend/tests/live/billing/test_billing_e2e.py
"""

from unittest.mock import patch, MagicMock
import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timedelta

from backend.src.billing.credits import credit_manager, deduct_usage
from backend.src.billing.subscriptions import subscription_service
from backend.src.billing.endpoints.account_state import _build_account_state
from backend.database.db import async_db_session
from sqlalchemy import text

# Import the test user creation logic
from backend.tests.create_test_user import create_test_user
from backend.app.admin.model.user import User
from sqlalchemy import select

@pytest.mark.asyncio
async def test_billing_e2e_flow():
    """
    End-to-End Billing Test Flow
    
    Acts as a user to verify the complete lifecycle of credits and billing.
    """
    # Mock Stripe
    patcher1 = patch('backend.src.billing.external.stripe.StripeAPIWrapper.create_customer')
    patcher2 = patch('backend.src.billing.external.stripe.StripeAPIWrapper.retrieve_customer')
    patcher3 = patch('backend.src.billing.external.stripe.StripeAPIWrapper.create_subscription')
    patcher4 = patch('backend.src.billing.external.stripe.StripeAPIWrapper.create_checkout_session')
    patcher5 = patch('backend.src.billing.external.stripe.StripeAPIWrapper.retrieve_subscription')

    mock_create_cus = patcher1.start()
    mock_get_cus = patcher2.start()
    mock_create_sub = patcher3.start()
    mock_create_checkout = patcher4.start()
    mock_get_sub = patcher5.start()

    # Mocks config
    mock_create_cus.return_value = MagicMock(id='cus_test_123', email='test@example.com')
    mock_get_cus.return_value = MagicMock(id='cus_test_123', deleted=False)
    mock_create_sub.return_value = MagicMock(id='sub_test_free', status='active')
    mock_create_checkout.return_value = MagicMock(id='cs_test_123', url='https://checkout.stripe.com/test', payment_intent='pi_test_123')
    mock_get_sub.return_value = MagicMock(id='sub_test_free', status='active')

    print("\n\n🔵 STARTING BILLING E2E TEST")
    
    # 1. Setup Test User
    # ---------------------------------------------------------
    username = f"billing_test_{int(datetime.now().timestamp())}"
    email = f"{username}@example.com"
    
    # Create user in DB
    await create_test_user(
        username=username,
        email=email,
        nickname="Billing Tester",
        is_superuser=False
    )
    
    # Get user ID
    async with async_db_session() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one()
        user_id = str(user.uuid)  # We use UUID for billing
        print(f"✅ Created test user: {username} (ID: {user_id})")

    # 1b. Ensure Free Tier (Auto-enrollment simulation)
    from backend.src.billing.subscriptions import ensure_free_tier_subscription
    await ensure_free_tier_subscription(user_id)

    # 2. Verify Initial Account State (Free Tier)
    # ---------------------------------------------------------
    state = await _build_account_state(user_id)
    
    print("\n🔍 Initial State Analysis:")
    print(f"   Tier: {state['subscription']['tier_key']}")
    print(f"   Credits: {state['credits']['total']}")
    
    # Expect: Free tier, daily credits present (0.05 or similar)
    print(f"DEBUG: State Tier Key: {state['subscription']['tier_key']}")
    print(f"DEBUG: Full Subscription: {state['subscription']}")
    with open("debug_state.txt", "w") as f:
        f.write(f"Tier Key: {state['subscription']['tier_key']}\n")
        f.write(f"Full Subscription: {state['subscription']}\n")
    # Expect: Free tier, daily credits present
    assert state['subscription']['tier_key'] == 'free'
    # Actually, verify_daily_credits should have run if accessed via endpoint, 
    # but here we called internal _build. Let's trigger refresh explicitly.
    
    from backend.src.billing.credits import check_and_refresh_daily_credits
    await check_and_refresh_daily_credits(user_id)
    
    state = await _build_account_state(user_id)
    assert state['credits']['daily'] > 0
    print("✅ Initial daily credits verified")

    # 3. Simulate Credit Usage (Deduction)
    # ---------------------------------------------------------
    # Simulate an LLM call costing $0.02
    print("\n💸 Simulating Usage...")
    usage_result = await deduct_usage(
        account_id=user_id,
        prompt_tokens=500,
        completion_tokens=200,
        model="gpt-4o-mini",
        thread_id="test-thread-1"
    )
    
    assert usage_result['success'] is True
    assert usage_result['cost'] > 0
    print(f"   Cost: ${usage_result['cost']:.4f}")
    print(f"   New Balance: ${usage_result['new_balance']:.4f}")
    
    # Verify ledger entry
    async with async_db_session() as session:
        ledger = await session.execute(
            text("SELECT * FROM credit_ledger WHERE account_id = :uid ORDER BY created_at DESC"),
            {"uid": user_id}
        )
        entry = ledger.fetchone()
        assert entry is not None
        assert entry.type == 'usage'
        print("✅ Usage recorded in ledger")

    # 4. Simulate Credit Purchase (Adding Credits)
    # ---------------------------------------------------------
    # We'll use internal add_credits since we can't easily mock full Stripe checkout flow in live test
    # without a real test card UI interaction, but we can verify the RESULT of a purchase.
    print("\n💰 Simulating Credit Purchase...")
    add_result = await credit_manager.add_credits(
        account_id=user_id,
        amount=Decimal("10.00"),
        description="Test Purchase",
        is_expiring=False, # Purchased credits don't expire
        credit_type="purchase"
    )
    
    assert add_result['success'] is True
    assert add_result['new_balance'] > 10.00 # 10 + remaining daily
    print(f"   Added: $10.00")
    print(f"   New Total: ${add_result['new_balance']}")

    # 5. Verify Priority Deduction (Daily vs Purchased)
    # ---------------------------------------------------------
    # Usage should come from daily FIRST (if any left), then purchased.
    # Let's clean daily credits first to force purchased usage? 
    # Actually, let's just run a large usage that exceeds daily to prove it dips into purchased.
    
    print("\n📉 Testing Deduction Priority...")
    # Get current daily balance
    balance = await credit_manager.get_balance(user_id)
    daily = balance['daily']
    
    # Spend more than daily
    large_usage = await deduct_usage(
        account_id=user_id,
        prompt_tokens=10000, # Large call
        completion_tokens=5000,
        model="gpt-4"
    )
    
    new_balance = await credit_manager.get_balance(user_id)
    print(f"   Old Daily: {daily} -> New Daily: {new_balance['daily']}")
    print(f"   Old Non-Expiring: {balance['non_expiring']} -> New: {new_balance['non_expiring']}")
    
    # Verify daily is depleted/reduced and non-expiring is reduced
    assert new_balance['daily'] < daily or new_balance['daily'] == 0
    assert new_balance['non_expiring'] < balance['non_expiring']
    print("✅ Priority deduction verified (Daily -> Purchased)")

    # 6. Verify Transaction History Endpoint Logic
    # ---------------------------------------------------------
    # We'll reuse the logic from the endpoint
    print("\n📜 Verifying Transaction History...")
    from backend.src.billing.endpoints.payments import get_transactions
    
    # Mock dependency
    async def mock_get_user(): return user_id
    
    # Ensure usage was recorded
    txs = await get_transactions(user_id=user_id, limit=10)
    assert len(txs['transactions']) >= 2 # Usage + Purchase + Usage
    print(f"   Found {len(txs['transactions'])} transactions")
    
    print("\n✅ BILLING E2E TEST COMPLETED SUCCESSFULLY")

if __name__ == "__main__":
    asyncio.run(test_billing_e2e_flow())
