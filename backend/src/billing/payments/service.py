"""
Payment Service

Handles one-time credit purchases via Stripe checkout.
Features:
- Tier-based purchase eligibility
- Credit purchase checkout sessions
- Purchase record tracking
- Idempotent purchase processing

Based on external_billing/payments/service.py.
"""

import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional

from backend.src.billing.external.stripe import StripeAPIWrapper
from backend.src.billing.shared.config import CREDIT_PACKAGES, get_credit_package
from backend.src.billing.shared.exceptions import BillingError, PaymentError
from .interfaces import PaymentProcessorInterface

logger = logging.getLogger(__name__)


class PaymentService(PaymentProcessorInterface):
    """
    Handles credit purchase payments.
    
    Flow:
    1. Validate tier allows purchases
    2. Create credit_purchases record (pending)
    3. Create Stripe checkout session
    4. User completes payment
    5. Webhook grants credits
    
    Usage:
        from backend.src.billing.payments import payment_service
        
        result = await payment_service.create_checkout_session(
            account_id=user_id,
            amount=Decimal('10.00'),
            success_url='/billing/success',
            cancel_url='/billing/cancel'
        )
        # Returns {'checkout_url': 'https://checkout.stripe.com/...'}
    """
    
    async def validate_payment_eligibility(self, account_id: str) -> bool:
        """
        Check if account can purchase credits.
        
        Only paid tiers can purchase additional credits.
        
        Args:
            account_id: User account UUID
            
        Returns:
            True if purchases are allowed
        """
        try:
            from backend.src.billing.subscriptions import get_user_subscription_tier
            tier = await get_user_subscription_tier(account_id)
            return tier.get('can_purchase_credits', False)
        except Exception as e:
            logger.error(f"[PAYMENT] Error checking eligibility: {e}")
            return False
    
    async def create_checkout_session(
        self,
        account_id: str,
        amount: Decimal,
        success_url: str,
        cancel_url: str
    ) -> Dict:
        """
        Create Stripe checkout session for credit purchase.
        
        Args:
            account_id: User account UUID
            amount: Amount in USD to purchase
            success_url: Redirect URL on success
            cancel_url: Redirect URL on cancel
            
        Returns:
            Dict with checkout_url
            
        Raises:
            PaymentError: If payment cannot be created
        """
        return await self.create_credit_purchase_checkout(
            account_id, amount, success_url, cancel_url
        )
    
    async def create_credit_purchase_checkout(
        self,
        account_id: str,
        amount: Decimal,
        success_url: str,
        cancel_url: str
    ) -> Dict:
        """
        Create checkout session for credit purchase.
        
        Steps:
        1. Validate tier allows purchases
        2. Get/validate Stripe customer
        3. Create purchase record
        4. Create Stripe checkout
        5. Update purchase with session info
        """
        # Validate type and normalize
        amount = Decimal(str(amount))
        if amount <= 0:
            raise PaymentError(
                code="INVALID_AMOUNT",
                message="Purchase amount must be positive"
            )
        
        # Check eligibility
        is_eligible = await self.validate_payment_eligibility(account_id)
        if not is_eligible:
            raise PaymentError(
                code="PURCHASE_NOT_ALLOWED",
                message="Credit purchases are not available for your subscription tier. Please upgrade to a paid plan."
            )
        
        logger.info(f"[PAYMENT] Creating checkout for {account_id}, amount=${amount}")
        
        # Get customer ID
        customer_id = await self._get_stripe_customer(account_id)
        if not customer_id:
            raise PaymentError(
                code="NO_CUSTOMER",
                message="No billing customer found. Please set up a subscription first."
            )
        
        # Validate customer exists in Stripe
        is_valid = await self._validate_stripe_customer(customer_id, account_id)
        if not is_valid:
            raise PaymentError(
                code="INVALID_CUSTOMER",
                message="Your billing record is invalid. Please contact support."
            )
        
        # Create purchase record
        purchase_id = await self._create_purchase_record(account_id, amount)
        if not purchase_id:
            raise PaymentError(
                code="RECORD_FAILED",
                message="Failed to initialize payment"
            )
        
        # Generate idempotency key
        idempotency_key = hashlib.sha256(
            f"{account_id}_{purchase_id}_{amount}".encode()
        ).hexdigest()[:40]
        
        try:
            # Create Stripe checkout session
            session = await StripeAPIWrapper.create_checkout_session(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': f'${amount} Credits',
                            'description': 'Platform credits for AI usage'
                        },
                        'unit_amount': int(amount * 100)
                    },
                    'quantity': 1
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
                allow_promotion_codes=True,
                metadata={
                    'type': 'credit_purchase',
                    'account_id': account_id,
                    'credit_amount': str(amount),
                    'purchase_id': str(purchase_id)
                },
                idempotency_key=idempotency_key
            )
            
            # Update purchase record with session info
            payment_intent_id = session.payment_intent if hasattr(session, 'payment_intent') else None
            
            await self._update_purchase_record(
                purchase_id=purchase_id,
                session_id=session.id,
                payment_intent_id=payment_intent_id,
                amount=amount
            )
            
            logger.info(f"[PAYMENT] Created checkout session {session.id} for purchase {purchase_id}")
            
            return {
                'success': True,
                'checkout_url': session.url,
                'session_id': session.id,
                'purchase_id': purchase_id
            }
            
        except Exception as e:
            logger.critical(
                f"[PAYMENT FAILURE] Stripe checkout failed! "
                f"account_id={account_id}, purchase_id={purchase_id}, "
                f"amount=${amount}, error={e}"
            )
            
            # Mark purchase as failed
            await self._mark_purchase_failed(purchase_id, str(e))
            
            raise PaymentError(
                code="CHECKOUT_FAILED",
                message=f"Failed to create payment session: {e}"
            )
    
    async def create_package_checkout(
        self,
        account_id: str,
        package_id: str,
        success_url: str,
        cancel_url: str
    ) -> Dict:
        """
        Create checkout for a predefined credit package.
        
        Args:
            account_id: User account UUID
            package_id: Credit package ID
            success_url: Redirect on success
            cancel_url: Redirect on cancel
            
        Returns:
            Dict with checkout_url
        """
        package = get_credit_package(package_id)
        if not package:
            raise PaymentError(
                code="INVALID_PACKAGE",
                message=f"Credit package '{package_id}' not found"
            )
        
        return await self.create_credit_purchase_checkout(
            account_id=account_id,
            amount=Decimal(str(package.price)),
            success_url=success_url,
            cancel_url=cancel_url
        )
    
    async def get_purchase_status(self, purchase_id: str) -> Dict:
        """
        Get status of a credit purchase.
        
        Returns:
            Dict with purchase status and details
        """
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                result = await session.execute(
                    text("""
                        SELECT 
                            id, account_id, amount_dollars, 
                            status, stripe_payment_intent_id,
                            created_at, completed_at, metadata
                        FROM credit_purchases
                        WHERE id = CAST(:purchase_id AS UUID)
                    """),
                    {"purchase_id": purchase_id}
                )
                row = result.fetchone()
                
                if not row:
                    return {'found': False}
                
                return {
                    'found': True,
                    'id': str(row.id),
                    'account_id': str(row.account_id),
                    'amount': float(row.amount_dollars),
                    'status': row.status,
                    'payment_intent_id': row.stripe_payment_intent_id,
                    'created_at': row.created_at.isoformat() if row.created_at else None,
                    'completed_at': row.completed_at.isoformat() if row.completed_at else None
                }
                
        except Exception as e:
            logger.error(f"[PAYMENT] Error getting purchase status: {e}")
            return {'found': False, 'error': str(e)}
    
    async def list_purchases(
        self,
        account_id: str,
        limit: int = 10,
        status: Optional[str] = None
    ) -> Dict:
        """
        List credit purchases for an account.
        
        Args:
            account_id: User account UUID
            limit: Max results
            status: Filter by status
            
        Returns:
            Dict with purchases list
        """
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                query = """
                    SELECT 
                        id, amount_dollars, status, 
                        created_at, completed_at
                    FROM credit_purchases
                        WHERE account_id = CAST(:account_id AS UUID)
                """
                params = {"account_id": account_id, "limit": limit}
                
                if status:
                    query += " AND status = :status"
                    params["status"] = status
                
                query += " ORDER BY created_at DESC LIMIT :limit"
                
                result = await session.execute(text(query), params)
                rows = result.fetchall()
                
                purchases = []
                for row in rows:
                    purchases.append({
                        'id': str(row.id),
                        'amount': float(row.amount_dollars),
                        'status': row.status,
                        'created_at': row.created_at.isoformat() if row.created_at else None,
                        'completed_at': row.completed_at.isoformat() if row.completed_at else None
                    })
                
                return {
                    'purchases': purchases,
                    'count': len(purchases)
                }
                
        except Exception as e:
            logger.error(f"[PAYMENT] Error listing purchases: {e}")
            return {'purchases': [], 'error': str(e)}
    
    # =========================================================================
    # Internal helpers
    # =========================================================================
    
    async def _get_stripe_customer(self, account_id: str) -> Optional[str]:
        """Get Stripe customer ID for account."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                result = await session.execute(
                    text("""
                        SELECT stripe_customer_id 
                        FROM credit_accounts 
                            WHERE account_id = CAST(:account_id AS UUID)
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                return row.stripe_customer_id if row else None
        except Exception as e:
            logger.error(f"[PAYMENT] Error getting customer: {e}")
            return None
    
    async def _validate_stripe_customer(self, customer_id: str, account_id: str) -> bool:
        """Validate customer exists in Stripe."""
        try:
            await StripeAPIWrapper.retrieve_customer(customer_id)
            logger.debug(f"[PAYMENT] Verified Stripe customer {customer_id}")
            return True
        except Exception as e:
            if 'No such customer' in str(e):
                logger.error(f"[PAYMENT] Customer {customer_id} not found in Stripe")
                return False
            raise
    
    async def _create_purchase_record(
        self,
        account_id: str,
        amount: Decimal
    ) -> Optional[str]:
        """Create initial purchase record."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            import uuid
            
            purchase_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            
            async with async_db_session() as session:
                await session.execute(
                    text("""
                        INSERT INTO credit_purchases (
                            id, account_id, amount_dollars, status, created_at, metadata
                        ) VALUES (
                            CAST(:id AS UUID), CAST(:account_id AS UUID), :amount, 'pending', :now, :metadata
                        )
                    """),
                    {
                        "id": purchase_id,
                        "account_id": account_id,
                        "amount": float(amount),
                        "now": now,
                        "metadata": f'{{"amount": {float(amount)}}}'
                    }
                )
                await session.commit()
            
            logger.info(f"[PAYMENT] Created purchase record {purchase_id}")
            return purchase_id
            
        except Exception as e:
            logger.error(f"[PAYMENT] Failed to create purchase record: {e}")
            return None
    
    async def _update_purchase_record(
        self,
        purchase_id: str,
        session_id: str,
        payment_intent_id: Optional[str],
        amount: Decimal
    ) -> None:
        """Update purchase record with Stripe info."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            import json
            
            async with async_db_session() as session:
                metadata = json.dumps({
                    'session_id': session_id,
                    'amount': float(amount),
                    'purchase_id': purchase_id
                })
                
                await session.execute(
                    text("""
                        UPDATE credit_purchases
                        SET stripe_payment_intent_id = :intent_id,
                            metadata = :metadata::jsonb
                        WHERE id = CAST(:purchase_id AS UUID)
                    """),
                    {
                        "purchase_id": purchase_id,
                        "intent_id": payment_intent_id,
                        "metadata": metadata
                    }
                )
                await session.commit()
                
        except Exception as e:
            logger.warning(f"[PAYMENT] Could not update purchase record: {e}")
    
    async def _mark_purchase_failed(self, purchase_id: str, error: str) -> None:
        """Mark purchase as failed."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            import json
            
            now = datetime.now(timezone.utc)
            
            async with async_db_session() as session:
                metadata = json.dumps({
                    'error': error,
                    'failed_at': now.isoformat()
                })
                
                await session.execute(
                    text("""
                        UPDATE credit_purchases
                        SET status = 'failed', metadata = :metadata::jsonb
                        WHERE id = CAST(:purchase_id AS UUID)
                    """),
                    {"purchase_id": purchase_id, "metadata": metadata}
                )
                await session.commit()
                
        except Exception as e:
            logger.error(f"[PAYMENT] Could not mark purchase failed: {e}")


# Global instance
payment_service = PaymentService()
