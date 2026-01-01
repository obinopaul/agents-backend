
import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock
from backend.core.conf import settings
from backend.tests.create_test_user import create_test_user
from backend.database.db import async_db_session
from backend.app.admin.model.user import User
from sqlalchemy import select
from datetime import datetime

# API Prefix
BASE_URL = f"{settings.FASTAPI_API_V1_PATH}/billing"

@pytest.fixture
async def authenticated_client(app):
    # Create test user
    username = f"integ_test_{int(datetime.now().timestamp())}"
    email = f"{username}@example.com"
    await create_test_user(username, email, "Integ Tester", False)
    
    # Get user and generate token (mocking auth if needed or using login)
    # For integration tests, we can use the `create_access_token` util if available,
    # or rely on the fact that `create_test_user` might not log us in.
    # To simplify, we might override the `get_current_user` dependency or similar.
    
    # Actually, let's just get the user ID and mock the dependency
    async with async_db_session() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one()
        user_id = str(user.uuid)
        
    # Mock auth dependency
    # We need to find where `get_current_user` is used.
    # Usually `backend.middleware.jwt_auth_middleware` or `backend.app.utils.jwt`
    
    # For now, let's try to assume we can inject headers if we had a token generator.
    # Alternatively, we can use `app.dependency_overrides`.
    
    from backend.app.admin.api.v1.auth.utils.current import get_current_user
    
    async def mock_get_current_user():
        return user

    app.dependency_overrides[get_current_user] = mock_get_current_user
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client, user_id
        
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_get_account_state(authenticated_client):
    client, user_id = authenticated_client
    
    # Ensure free tier (it should be auto-created by now if hooks are working, or we force it)
    from backend.src.billing.subscriptions import ensure_free_tier_subscription
    await ensure_free_tier_subscription(user_id)
    
    response = await client.get(f"{BASE_URL}/account-state")
    assert response.status_code == 200
    data = response.json()
    
    assert data['code'] == 200
    result = data['data']
    
    # Verify structure
    assert 'credits' in result
    assert 'subscription' in result
    assert 'limits' in result
    
    # Verify content
    assert result['subscription']['tier_key'] == 'free'
    assert result['credits']['daily'] > 0

@pytest.mark.asyncio
async def test_get_transactions(authenticated_client):
    client, user_id = authenticated_client
    
    # Initial state should have no transactions or maybe the daily refresh one
    response = await client.get(f"{BASE_URL}/payments/transactions")
    assert response.status_code == 200
    data = response.json()
    
    assert 'transactions' in data['data']
    assert isinstance(data['data']['transactions'], list)

@pytest.mark.asyncio
async def test_create_checkout_session(authenticated_client):
    client, user_id = authenticated_client
    
    # Mock Stripe
    with patch('backend.src.billing.external.stripe.StripeAPIWrapper.create_checkout_session') as mock_checkout:
        mock_checkout.return_value = MagicMock(id="cs_test_mock", url="https://mock.stripe.com/pay")
        
        payload = {
            "price_id": "price_test_pro",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel"
        }
        
        response = await client.post(f"{BASE_URL}/subscriptions/checkout", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['data']['sessionId'] == "cs_test_mock"
        assert data['data']['url'] == "https://mock.stripe.com/pay"

