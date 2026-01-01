"""
Webhook Endpoints

Stripe webhook endpoint for processing billing events.
"""

import logging
from fastapi import APIRouter, Request

from backend.src.billing.external.stripe import webhook_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["billing-webhooks"])


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Process Stripe webhook events.
    
    Handles:
    - checkout.session.completed
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.paid
    - invoice.payment_failed
    - charge.refunded
    """
    return await webhook_service.process_stripe_webhook(request)
