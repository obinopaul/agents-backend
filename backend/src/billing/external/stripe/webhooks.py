"""
Stripe Webhook Service

Central dispatcher for Stripe webhook events.
Handles signature verification, deduplication, and routing to handlers.

Based on external_billing/external/stripe/webhooks.py.
"""

import logging
from typing import Dict, Any, Optional

from fastapi import Request, HTTPException

from backend.core.conf import settings
from .webhook_lock import WebhookLock

logger = logging.getLogger(__name__)

# Import stripe conditionally
try:
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
except ImportError:
    stripe = None


class WebhookService:
    """
    Central service for processing Stripe webhooks.
    
    Responsibilities:
    - Verify webhook signatures
    - Deduplicate events using distributed locking
    - Route events to appropriate handlers
    - Handle errors and mark event status
    
    Usage:
        webhook_service = WebhookService()
        result = await webhook_service.process_stripe_webhook(request)
    """
    
    def __init__(self):
        if stripe:
            stripe.api_key = settings.STRIPE_SECRET_KEY
    
    async def process_stripe_webhook(self, request: Request) -> Dict[str, Any]:
        """
        Process an incoming Stripe webhook.
        
        Args:
            request: FastAPI Request object
            
        Returns:
            Dict with processing status
            
        Raises:
            HTTPException: If signature invalid or secret not configured
        """
        if not stripe:
            raise HTTPException(status_code=500, detail="Stripe not configured")
        
        event = None
        
        try:
            # Get raw payload and signature
            payload = await request.body()
            sig_header = request.headers.get('stripe-signature')
            
            if not sig_header:
                raise HTTPException(status_code=400, detail="Missing stripe-signature header")
            
            if not settings.STRIPE_WEBHOOK_SECRET:
                logger.error("[WEBHOOK] STRIPE_WEBHOOK_SECRET not configured")
                raise HTTPException(status_code=500, detail="Webhook secret not configured")
            
            # Verify signature and construct event
            try:
                event = stripe.Webhook.construct_event(
                    payload,
                    sig_header,
                    settings.STRIPE_WEBHOOK_SECRET,
                    tolerance=300  # 5 minutes
                )
            except stripe.error.SignatureVerificationError as e:
                logger.warning(f"[WEBHOOK] Invalid signature: {e}")
                raise HTTPException(status_code=400, detail="Invalid webhook signature")
            except ValueError as e:
                logger.warning(f"[WEBHOOK] Invalid payload: {e}")
                raise HTTPException(status_code=400, detail="Invalid payload")
            
            # Check for duplicate/lock event
            can_process, reason = await WebhookLock.check_and_mark_webhook_processing(
                event.id,
                event.type,
                payload=event.to_dict() if hasattr(event, 'to_dict') else None
            )
            
            if not can_process:
                logger.info(f"[WEBHOOK] Skipping event {event.id}: {reason}")
                return {
                    'status': 'success',
                    'message': f'Event already processed or in progress: {reason}'
                }
            
            # Log event processing
            logger.info(f"[WEBHOOK] Processing event type: {event.type} (ID: {event.id})")
            
            # Route to appropriate handler
            await self._route_event(event)
            
            # Mark as completed
            await WebhookLock.mark_webhook_completed(event.id)
            
            return {'status': 'success', 'event_id': event.id}
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[WEBHOOK] Error processing webhook: {e}", exc_info=True)
            
            # Log error details
            error_message = f"{type(e).__name__}: {str(e)[:500]}"
            
            if event and hasattr(event, 'id'):
                await WebhookLock.mark_webhook_failed(event.id, error_message)
            
            # Return success to Stripe (we've logged the error)
            # This prevents Stripe from retrying indefinitely
            return {
                'status': 'success',
                'error': 'processed_with_errors',
                'message': 'Webhook logged as failed internally'
            }
    
    async def _route_event(self, event) -> None:
        """
        Route event to the appropriate handler.
        
        Args:
            event: Stripe event object
        """
        event_type = event.type
        
        # Import handlers here to avoid circular imports
        from .handlers.checkout import CheckoutHandler
        from .handlers.subscription import SubscriptionHandler
        from .handlers.invoice import InvoiceHandler
        from .handlers.refund import RefundHandler
        
        # Checkout events
        if event_type == 'checkout.session.completed':
            logger.info("[WEBHOOK] Handling checkout.session.completed")
            await CheckoutHandler.handle_checkout_completed(event)
        
        elif event_type == 'checkout.session.expired':
            logger.info("[WEBHOOK] Handling checkout.session.expired")
            await CheckoutHandler.handle_checkout_expired(event)
        
        # Subscription events
        elif event_type == 'customer.subscription.created':
            logger.info("[WEBHOOK] Handling customer.subscription.created")
            await SubscriptionHandler.handle_subscription_created(event)
        
        elif event_type == 'customer.subscription.updated':
            logger.info("[WEBHOOK] Handling customer.subscription.updated")
            await SubscriptionHandler.handle_subscription_updated(event)
        
        elif event_type == 'customer.subscription.deleted':
            logger.info("[WEBHOOK] Handling customer.subscription.deleted")
            await SubscriptionHandler.handle_subscription_deleted(event)
        
        elif event_type == 'customer.subscription.trial_will_end':
            logger.info("[WEBHOOK] Handling customer.subscription.trial_will_end")
            await SubscriptionHandler.handle_trial_will_end(event)
        
        # Invoice events
        elif event_type in ['invoice.payment_succeeded', 'invoice.paid']:
            logger.info(f"[WEBHOOK] Handling {event_type}")
            await InvoiceHandler.handle_invoice_paid(event)
        
        elif event_type == 'invoice.payment_failed':
            logger.info("[WEBHOOK] Handling invoice.payment_failed")
            await InvoiceHandler.handle_invoice_failed(event)
        
        elif event_type == 'invoice.upcoming':
            logger.info("[WEBHOOK] Handling invoice.upcoming")
            await InvoiceHandler.handle_invoice_upcoming(event)
        
        # Refund events
        elif event_type in ['charge.refunded', 'payment_intent.refunded']:
            logger.info(f"[WEBHOOK] Handling {event_type}")
            await RefundHandler.handle_refund(event)
        
        # Customer events
        elif event_type == 'customer.created':
            logger.debug(f"[WEBHOOK] customer.created - logged only")
        
        elif event_type == 'customer.updated':
            logger.debug(f"[WEBHOOK] customer.updated - logged only")
        
        # Payment method events
        elif event_type in ['payment_method.attached', 'payment_method.detached']:
            logger.debug(f"[WEBHOOK] {event_type} - logged only")
        
        # Subscription schedule events (for scheduled changes)
        elif event_type in [
            'subscription_schedule.created',
            'subscription_schedule.updated', 
            'subscription_schedule.completed',
            'subscription_schedule.released',
            'subscription_schedule.canceled'
        ]:
            logger.info(f"[WEBHOOK] Handling {event_type}")
            # TODO: Implement ScheduleHandler when needed
            logger.info(f"[WEBHOOK] Schedule event logged: {event_type}")
        
        else:
            logger.info(f"[WEBHOOK] Unhandled event type: {event_type}")
    
    async def verify_signature(self, payload: bytes, sig_header: str) -> bool:
        """
        Verify a webhook signature without processing.
        
        Args:
            payload: Raw request body
            sig_header: Stripe-Signature header value
            
        Returns:
            True if signature is valid
        """
        if not stripe:
            return False
        
        try:
            stripe.Webhook.construct_event(
                payload,
                sig_header,
                settings.STRIPE_WEBHOOK_SECRET,
                tolerance=300
            )
            return True
        except Exception:
            return False


# Global instance
webhook_service = WebhookService()
