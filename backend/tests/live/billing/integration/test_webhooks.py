
import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock
from backend.core.conf import settings
from datetime import datetime


WEBHOOK_URL = f"{settings.FASTAPI_API_V1_PATH}/billing/webhook"

@pytest.mark.asyncio
async def test_webhook_missing_signature(app):
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(WEBHOOK_URL, json={"id": "evt_test"})
        assert response.status_code == 400
        assert "Missing stripe-signature header" in response.json()['detail']

@pytest.mark.asyncio
async def test_webhook_invalid_signature(app):
    async with AsyncClient(app=app, base_url="http://test") as client:
        # We need to ensure stripe is "configured" in the service, or mock it
        # backend.src.billing.external.stripe.webhooks.stripe is imported conditionally
        # If settings.STRIPE_SECRET_KEY is set, it might expect real validation.
        
        # We force settings to have a secret
        settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
        
        headers = {"stripe-signature": "t=123,v1=invalid_sig"}
        response = await client.post(WEBHOOK_URL, json={"id": "evt_test"}, headers=headers)
        
        # Depending on if we reach stripe or if stripe lib is installed, 
        # it might return 400 (Invalid signature) or 500.
        # But we expect 400 from our logic.
        assert response.status_code == 400
        assert "Invalid webhook signature" in response.json()['detail'] or "Invalid payload" in response.json()['detail']

@pytest.mark.asyncio
async def test_webhook_valid_signature_mocked(app):
    async with AsyncClient(app=app, base_url="http://test") as client:
        with patch('backend.src.billing.external.stripe.webhooks.stripe.Webhook.construct_event') as mock_construct:
            event_payload = {
                "id": f"evt_test_valid_{int(datetime.now().timestamp())}",
                "type": "invoice.paid",
                "data": {"object": {"id": "in_test", "customer": "cus_test"}}
            }
            
            mock_event = MagicMock()
            mock_event.id = event_payload['id']
            mock_event.type = event_payload['type']
            mock_event.to_dict.return_value = event_payload
            
            mock_construct.return_value = mock_event
            
            headers = {"stripe-signature": "t=123,v1=valid_sig"}
            response = await client.post(WEBHOOK_URL, json=event_payload, headers=headers)
            
            assert response.status_code == 200
            assert response.json()['status'] == 'success'

