"""
Portal Handler

Manages Stripe Customer Portal sessions for self-service billing management.
Features:
- Create portal sessions for subscription management
- Handle payment method updates
- Invoice history access

Based on external_billing/subscriptions/handlers/portal.py.
"""

import logging
from typing import Dict

from backend.src.billing.external.stripe import StripeAPIWrapper
from backend.src.billing.shared.exceptions import BillingError
from .customer import CustomerHandler

logger = logging.getLogger(__name__)


class PortalHandler:
    """
    Handles Stripe Customer Portal operations.
    
    The Customer Portal allows users to:
    - View and update payment methods
    - View invoice history
    - Manage subscription (cancel, upgrade via portal)
    """
    
    @classmethod
    async def create_portal_session(
        cls,
        account_id: str,
        return_url: str
    ) -> Dict:
        """
        Create Stripe Customer Portal session.
        
        Args:
            account_id: User account UUID
            return_url: URL to return to after portal session
            
        Returns:
            Dict with portal_url and session_id
        """
        handler = cls()
        return await handler._create_portal_session(account_id, return_url)
    
    async def _create_portal_session(
        self,
        account_id: str,
        return_url: str
    ) -> Dict:
        """Internal implementation of create_portal_session."""
        # Get Stripe customer ID
        customer_id = await CustomerHandler.get_or_create_stripe_customer(account_id)
        
        logger.info(f"[PORTAL] Creating portal session for {account_id}")
        
        try:
            session = await StripeAPIWrapper.create_billing_portal_session(
                customer_id=customer_id,
                return_url=return_url
            )
            
            logger.info(f"[PORTAL] Created session {session.id} for {account_id}")
            
            return {
                'success': True,
                'portal_url': session.url,
                'session_id': session.id
            }
            
        except Exception as e:
            logger.error(f"[PORTAL] Failed to create portal session: {e}")
            raise BillingError(
                code="PORTAL_SESSION_FAILED",
                message=f"Failed to create billing portal session: {e}",
                details={"account_id": account_id}
            )


# Convenience function
async def create_portal_session(account_id: str, return_url: str) -> Dict:
    """Create Stripe Customer Portal session."""
    return await PortalHandler.create_portal_session(account_id, return_url)
