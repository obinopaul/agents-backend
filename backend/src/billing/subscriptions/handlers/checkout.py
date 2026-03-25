"""
Checkout Handler

Manages Stripe checkout session creation for subscriptions.
Features:
- Multiple checkout flows (new, upgrade, trial conversion, free upgrade)
- Adaptive pricing (automatic currency detection)
- Idempotency key generation
- Metadata management for webhook processing

Based on external_billing/subscriptions/handlers/checkout.py.
"""

import logging
import hashlib
from datetime import datetime, timezone
from typing import Dict, Optional

from backend.core.conf import settings
from backend.src.billing.external.stripe import (
    StripeAPIWrapper,
    generate_checkout_idempotency_key,
)
from backend.src.billing.shared.config import get_tier_by_price_id, TIERS
from backend.src.billing.shared.exceptions import BillingError, SubscriptionError
from backend.src.billing.shared.cache_utils import invalidate_account_state_cache
from .customer import CustomerHandler

logger = logging.getLogger(__name__)


class CheckoutHandler:
    """
    Handles Stripe checkout session creation for subscriptions.
    
    Supports multiple checkout flows:
    - new_subscription: First-time subscriber
    - trial_conversion: Trial user upgrading to paid
    - free_upgrade: Free tier user upgrading to paid
    - paid_upgrade: Paid user upgrading to higher tier
    
    All checkout sessions include:
    - Adaptive pricing (Stripe auto-detects currency)
    - Idempotency keys (prevent duplicate sessions)
    - Rich metadata for webhook processing
    """
    
    @classmethod
    async def create_checkout_session(
        cls,
        account_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        commitment_type: Optional[str] = None,
        locale: Optional[str] = None
    ) -> Dict:
        """
        Create Stripe checkout session for subscription.
        
        Args:
            account_id: User account UUID
            price_id: Stripe price ID for subscription
            success_url: URL to redirect after success
            cancel_url: URL to redirect if cancelled
            commitment_type: 'monthly' or 'yearly'
            locale: User's locale for checkout page
            
        Returns:
            Dict with checkout_url, session_id, and flow details
        """
        handler = cls()
        return await handler._create_checkout_session(
            account_id, price_id, success_url, cancel_url, commitment_type, locale
        )
    
    async def _create_checkout_session(
        self,
        account_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        commitment_type: Optional[str] = None,
        locale: Optional[str] = None
    ) -> Dict:
        """Internal implementation of checkout session creation."""
        # Get or create Stripe customer
        customer_id = await CustomerHandler.get_or_create_stripe_customer(account_id)
        customer_email = await CustomerHandler.get_customer_email(account_id)
        
        # Get current subscription status
        subscription_status = await self._get_current_subscription_status(account_id)
        
        logger.debug(f"[CHECKOUT] account_id={account_id}, status={subscription_status}")
        
        # Generate idempotency key
        idempotency_key = generate_checkout_idempotency_key(
            account_id=account_id,
            price_id=price_id,
            commitment_type=commitment_type or 'monthly'
        )
        
        # Determine checkout flow
        flow_type = self._determine_checkout_flow(subscription_status)
        
        logger.info(f"[CHECKOUT] Flow: {flow_type} for {account_id}")
        
        # Route to appropriate handler
        if flow_type == 'trial_conversion':
            return await self._handle_trial_conversion(
                customer_id, customer_email, account_id, price_id, success_url, cancel_url,
                subscription_status, commitment_type, idempotency_key, locale
            )
        elif flow_type == 'free_upgrade':
            return await self._handle_free_upgrade(
                customer_id, customer_email, account_id, price_id, success_url, cancel_url,
                subscription_status, commitment_type, idempotency_key, locale
            )
        elif flow_type == 'paid_upgrade':
            return await self._handle_paid_upgrade(
                customer_id, customer_email, account_id, price_id, success_url, cancel_url,
                subscription_status, commitment_type, idempotency_key, locale
            )
        else:
            return await self._handle_new_subscription(
                customer_id, customer_email, account_id, price_id, success_url, cancel_url,
                commitment_type, idempotency_key, locale
            )
    
    async def _get_current_subscription_status(self, account_id: str) -> Dict:
        """Get current subscription status for account."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                result = await session.execute(
                    text("""
                        SELECT tier, stripe_subscription_id, trial_status
                        FROM credit_accounts
                        WHERE account_id = :account_id::uuid
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                
                if row:
                    return {
                        'has_subscription': row.stripe_subscription_id is not None,
                        'subscription_id': row.stripe_subscription_id,
                        'current_tier': row.tier or 'none',
                        'is_trial': row.trial_status == 'active',
                        'trial_status': row.trial_status
                    }
                
                return {
                    'has_subscription': False,
                    'subscription_id': None,
                    'current_tier': 'none',
                    'is_trial': False,
                    'trial_status': None
                }
                
        except Exception as e:
            logger.error(f"[CHECKOUT] Error getting subscription status: {e}")
            return {
                'has_subscription': False,
                'subscription_id': None,
                'current_tier': 'none',
                'is_trial': False
            }
    
    def _determine_checkout_flow(self, subscription_status: Dict) -> str:
        """Determine which checkout flow to use."""
        if subscription_status.get('is_trial'):
            return 'trial_conversion'
        
        if not subscription_status.get('has_subscription'):
            return 'new_subscription'
        
        current_tier = subscription_status.get('current_tier', 'none')
        if current_tier in ('none', 'free'):
            return 'free_upgrade'
        
        return 'paid_upgrade'
    
    async def _handle_trial_conversion(
        self,
        customer_id: str,
        customer_email: Optional[str],
        account_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        subscription_status: Dict,
        commitment_type: Optional[str],
        idempotency_key: str,
        locale: Optional[str]
    ) -> Dict:
        """Handle trial user converting to paid subscription."""
        new_tier_info = get_tier_by_price_id(price_id)
        tier_display_name = new_tier_info.display_name if new_tier_info else 'paid plan'
        
        existing_subscription_id = subscription_status.get('subscription_id')
        
        # Build metadata with info for webhook to cancel trial
        metadata = self._build_subscription_metadata(
            account_id=account_id,
            commitment_type=commitment_type,
            checkout_type='trial_conversion',
            previous_tier=subscription_status.get('current_tier'),
            cancel_after_checkout=existing_subscription_id
        )
        
        session = await self._create_stripe_checkout_session(
            customer_id, customer_email, price_id, success_url, cancel_url,
            metadata, idempotency_key, locale
        )
        
        return self._build_checkout_response(
            session, 'trial_conversion', new_tier_info, tier_display_name
        )
    
    async def _handle_free_upgrade(
        self,
        customer_id: str,
        customer_email: Optional[str],
        account_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        subscription_status: Dict,
        commitment_type: Optional[str],
        idempotency_key: str,
        locale: Optional[str]
    ) -> Dict:
        """Handle free tier user upgrading to paid subscription."""
        new_tier_info = get_tier_by_price_id(price_id)
        tier_display_name = new_tier_info.display_name if new_tier_info else 'paid plan'
        
        existing_subscription_id = subscription_status.get('subscription_id')
        
        # Build metadata - webhook will cancel free tier subscription after checkout
        metadata = self._build_subscription_metadata(
            account_id=account_id,
            commitment_type=commitment_type,
            checkout_type='free_upgrade',
            previous_tier='free',
            cancel_after_checkout=existing_subscription_id
        )
        
        session = await self._create_stripe_checkout_session(
            customer_id, customer_email, price_id, success_url, cancel_url,
            metadata, idempotency_key, locale
        )
        
        return self._build_checkout_response(
            session, 'free_upgrade', new_tier_info, tier_display_name
        )
    
    async def _handle_paid_upgrade(
        self,
        customer_id: str,
        customer_email: Optional[str],
        account_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        subscription_status: Dict,
        commitment_type: Optional[str],
        idempotency_key: str,
        locale: Optional[str]
    ) -> Dict:
        """Handle paid user upgrading/changing subscription."""
        existing_subscription_id = subscription_status.get('subscription_id')
        
        # For paid upgrades, we typically modify in-place rather than creating new checkout
        # But we create checkout if user doesn't have payment method or for tier changes
        
        new_tier_info = get_tier_by_price_id(price_id)
        tier_display_name = new_tier_info.display_name if new_tier_info else 'new plan'
        
        metadata = self._build_subscription_metadata(
            account_id=account_id,
            commitment_type=commitment_type,
            checkout_type='paid_upgrade',
            previous_tier=subscription_status.get('current_tier'),
            cancel_after_checkout=existing_subscription_id
        )
        
        session = await self._create_stripe_checkout_session(
            customer_id, customer_email, price_id, success_url, cancel_url,
            metadata, idempotency_key, locale
        )
        
        return self._build_checkout_response(
            session, 'paid_upgrade', new_tier_info, tier_display_name
        )
    
    async def _handle_new_subscription(
        self,
        customer_id: str,
        customer_email: Optional[str],
        account_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        commitment_type: Optional[str],
        idempotency_key: str,
        locale: Optional[str]
    ) -> Dict:
        """Handle first-time subscription."""
        new_tier_info = get_tier_by_price_id(price_id)
        tier_display_name = new_tier_info.display_name if new_tier_info else 'subscription'
        
        metadata = self._build_subscription_metadata(
            account_id=account_id,
            commitment_type=commitment_type,
            checkout_type='new_subscription'
        )
        
        session = await self._create_stripe_checkout_session(
            customer_id, customer_email, price_id, success_url, cancel_url,
            metadata, idempotency_key, locale
        )
        
        return self._build_checkout_response(
            session, 'new_subscription', new_tier_info, tier_display_name
        )
    
    async def _create_stripe_checkout_session(
        self,
        customer_id: str,
        customer_email: Optional[str],
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Dict,
        idempotency_key: str,
        locale: Optional[str]
    ):
        """Create Stripe checkout session with adaptive pricing."""
        session_params = {
            'customer': customer_id,
            'payment_method_types': ['card'],
            'line_items': [{'price': price_id, 'quantity': 1}],
            'mode': 'subscription',
            'success_url': success_url,
            'cancel_url': cancel_url,
            'allow_promotion_codes': True,
            'subscription_data': {'metadata': metadata},
            'idempotency_key': idempotency_key,
            # Enable adaptive pricing - Stripe auto-converts to customer's currency
            'adaptive_pricing': {'enabled': True}
        }
        
        # Set locale for checkout page
        session_params['locale'] = locale or 'auto'
        
        logger.debug(f"[CHECKOUT] Creating session with adaptive pricing")
        
        try:
            return await StripeAPIWrapper.create_checkout_session(**session_params)
        except Exception as e:
            logger.error(f"[CHECKOUT] Failed to create session: {e}")
            raise BillingError(
                code="CHECKOUT_SESSION_FAILED",
                message=f"Failed to create checkout session: {e}"
            )
    
    def _build_subscription_metadata(
        self,
        account_id: str,
        commitment_type: Optional[str] = None,
        checkout_type: str = 'new_subscription',
        previous_tier: Optional[str] = None,
        cancel_after_checkout: Optional[str] = None
    ) -> Dict:
        """Build metadata for subscription."""
        metadata = {
            'account_id': account_id,
            'checkout_type': checkout_type,
            'commitment_type': commitment_type or 'monthly',
            'checkout_timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        if previous_tier:
            metadata['previous_tier'] = previous_tier
        
        if cancel_after_checkout:
            metadata['cancel_after_checkout'] = cancel_after_checkout
        
        return metadata
    
    def _build_checkout_response(
        self,
        session,
        flow_type: str,
        tier_info = None,
        tier_display_name: str = None
    ) -> Dict:
        """Build response for checkout session."""
        response = {
            'success': True,
            'checkout_url': session.url,
            'session_id': session.id,
            'flow_type': flow_type
        }
        
        if tier_display_name:
            response['tier_name'] = tier_display_name
        
        if tier_info:
            response['new_tier'] = {
                'name': tier_info.name,
                'display_name': tier_info.display_name,
                'monthly_credits': float(tier_info.monthly_credits)
            }
        
        return response


# Convenience function
async def create_checkout_session(
    account_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    **kwargs
) -> Dict:
    """Create checkout session for subscription."""
    return await CheckoutHandler.create_checkout_session(
        account_id, price_id, success_url, cancel_url, **kwargs
    )
