
import pytest
import time
import json
from httpx import AsyncClient
from unittest.mock import patch, MagicMock
from backend.core.conf import settings
from backend.tests.create_test_user import create_test_user
from backend.database.db import async_db_session
from backend.app.admin.model.user import User
from sqlalchemy import select, text
from datetime import datetime

# API Prefix
BASE_URL = f"{settings.FASTAPI_API_V1_PATH}/billing"

@pytest.fixture
async def authenticated_client(app):
    # Create test user
    username = f"scenario_user_{int(datetime.now().timestamp())}"
    email = f"{username}@example.com"
    await create_test_user(username, email, "Scenario Tester", False)
    
    async with async_db_session() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one()
        user_id = str(user.uuid)
        
    from backend.app.admin.api.v1.auth.utils.current import get_current_user
    async def mock_get_current_user(): return user
    app.dependency_overrides[get_current_user] = mock_get_current_user
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client, user_id
        
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_scenario_free_to_pro_upgrade(authenticated_client):
    """
    Scenario: User Upgrade Flow
    1. User starts on Free Tier
    2. User initiates checkout for Pro Tier (tier_6_50)
    3. Webhook confirms payment
    4. User is now on Pro Tier
    """
    client, user_id = authenticated_client
    
    # 1. Ensure Free Tier
    from backend.src.billing.subscriptions import ensure_free_tier_subscription
    await ensure_free_tier_subscription(user_id)
    
    # Verify initial state
    res = await client.get(f"{BASE_URL}/account-state")
    assert res.json()['data']['subscription']['tier_key'] == 'free'
    
    # 2. Add Stripe Customer ID (needed for webhook matching)
    # We can fake this directly in DB
    stripe_cus_id = f"cus_test_{user_id[:8]}"
    async with async_db_session() as session:
        await session.execute(
            text("UPDATE credit_accounts SET stripe_customer_id = :cus_id WHERE account_id = :uid::uuid"),
            {"cus_id": stripe_cus_id, "uid": user_id}
        )
        await session.commit()

    # 3. Simulate Webhook (checkout.session.completed)
    # This implies the user went to Stripe and paid.
    # We send a webhook event to our endpoint.
    
    # We mock verification because we don't have a specific secret generator here
    with patch('backend.src.billing.external.stripe.webhooks.stripe.Webhook.construct_event') as mock_construct:
        # Construct event payload
        event_payload = {
            "id": f"evt_test_{int(datetime.now().timestamp())}",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_complete",
                    "customer": stripe_cus_id,
                    "mode": "subscription",
                    "subscription": "sub_test_pro_123",
                    "metadata": {
                        "account_id": user_id,
                        "tier": "tier_6_50" # Pro Tier
                    }
                }
            }
        }
        
        # Mock return value to be an object with accessors
        mock_event = MagicMock()
        mock_event.id = event_payload['id']
        mock_event.type = event_payload['type']
        mock_event.data.object = event_payload['data']['object']
        # Also need to allow dict access if code uses it
        mock_event.to_dict.return_value = event_payload
        
        mock_construct.return_value = mock_event
        
        # We also need to mock retrieving the subscription details, 
        # because the handler might call stripe.Subscription.retrieve
        with patch('backend.src.billing.subscriptions.handlers.checkout.StripeAPIWrapper.retrieve_subscription') as mock_retrieve_sub:
            mock_retrieve_sub.return_value = MagicMock(
                id="sub_test_pro_123",
                status="active",
                current_period_end=int(time.time()) + 30*24*3600,
                items=MagicMock(data=[MagicMock(price=MagicMock(id="price_tier_6_50"))])
            )
            
            # Send Webhook
            headers = {"stripe-signature": "t=123,v1=valid_sig"}
            webhook_res = await client.post(f"{BASE_URL}/webhook", json=event_payload, headers=headers)
            
            assert webhook_res.status_code == 200
            assert webhook_res.json()['status'] == 'success'
            
    # 4. Verify Pro Tier
    # Allow small delay for async db commit if any (though here it should be awaited)
    res = await client.get(f"{BASE_URL}/account-state")
    data = res.json()['data']
    
    assert data['subscription']['tier_key'] == 'tier_6_50' # Pro
    assert data['limits']['project_limit'] > 20 # Free is 20
    print("\n✅ Scenario A (Free -> Pro) Passed!")

@pytest.mark.asyncio
async def test_scenario_credit_purchase(authenticated_client):
    """
    Scenario: Credit Purchase
    1. User (Free) buys $10 credits
    2. Webhook confirms payment
    3. Balance increases
    """
    client, user_id = authenticated_client
    from backend.src.billing.subscriptions import ensure_free_tier_subscription
    await ensure_free_tier_subscription(user_id)
    
    # Initial Balance
    res = await client.get(f"{BASE_URL}/account-state")
    initial_balance = float(res.json()['data']['credits']['total'])
    
    # Fake Stripe Customer
    stripe_cus_id = f"cus_test_{user_id[:8]}"
    async with async_db_session() as session:
        await session.execute(
            text("UPDATE credit_accounts SET stripe_customer_id = :cus_id WHERE account_id = :uid::uuid"),
            {"cus_id": stripe_cus_id, "uid": user_id}
        )
        await session.commit()
        
    # Simulate payment_intent.succeeded
    with patch('backend.src.billing.external.stripe.webhooks.stripe.Webhook.construct_event') as mock_construct:
        amount_dollars = 10.00
        event_payload = {
            "id": f"evt_pay_{int(datetime.now().timestamp())}",
            "type": "checkout.session.completed", # Using checkout session for credits too
            "data": {
                "object": {
                    "id": "cs_test_credits",
                    "customer": stripe_cus_id,
                    "mode": "payment", # One-time payment
                    "payment_status": "paid",
                    "amount_total": int(amount_dollars * 100), # in cents
                    "metadata": {
                        "account_id": user_id,
                        "type": "credit_purchase",
                        "credit_amount": str(amount_dollars)
                    }
                }
            }
        }
        
        mock_event = MagicMock()
        mock_event.id = event_payload['id']
        mock_event.type = event_payload['type']
        mock_event.data.object = event_payload['data']['object']
        mock_event.to_dict.return_value = event_payload
        mock_construct.return_value = mock_event
        
        headers = {"stripe-signature": "t=123,v1=valid_sig"}
        webhook_res = await client.post(f"{BASE_URL}/webhook", json=event_payload, headers=headers)
        assert webhook_res.status_code == 200

    # Verify Balance
    res = await client.get(f"{BASE_URL}/account-state")
    new_balance = float(res.json()['data']['credits']['total'])
    
    assert new_balance >= initial_balance + amount_dollars
    print("\n✅ Scenario B (Purchase) Passed!")
