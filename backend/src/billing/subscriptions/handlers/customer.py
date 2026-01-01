"""
Customer Handler

Manages Stripe customer creation and retrieval.
Features:
- Get or create Stripe customer for an account
- Validate existing customers in Stripe
- Handle stale customer cleanup
- Email lookup for customer creation

Based on external_billing/subscriptions/handlers/customer.py.
"""

import logging
from typing import Optional, Dict

from backend.core.conf import settings
from backend.src.billing.external.stripe import StripeAPIWrapper
from backend.src.billing.shared.exceptions import BillingError

logger = logging.getLogger(__name__)


class CustomerHandler:
    """
    Handles Stripe customer management.
    
    Each user account maps to one Stripe customer.
    Customer IDs are stored in billing_customers table.
    """
    
    @classmethod
    async def get_or_create_stripe_customer(cls, account_id: str) -> str:
        """
        Get existing Stripe customer or create new one.
        
        Args:
            account_id: User account UUID
            
        Returns:
            Stripe customer ID (cus_xxx)
            
        Raises:
            BillingError: If customer creation fails
        """
        handler = cls()
        return await handler._get_or_create_stripe_customer(account_id)
    
    async def _get_or_create_stripe_customer(self, account_id: str) -> str:
        """Internal implementation of get_or_create."""
        # Try to get existing customer
        existing_customer = await self._try_get_existing_customer(account_id)
        if existing_customer:
            return existing_customer
        
        # Create new customer
        return await self._create_new_customer(account_id)
    
    async def _try_get_existing_customer(self, account_id: str) -> Optional[str]:
        """Check for existing valid Stripe customer."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                # Check billing_customers table
                result = await session.execute(
                    text("""
                        SELECT id, email FROM billing_customers
                            WHERE account_id = CAST(:account_id AS UUID)
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                
                if not row:
                    return None
                
                customer_id = row.id
                
                # Validate customer exists in Stripe
                if await self._validate_stripe_customer(customer_id):
                    logger.debug(f"[CUSTOMER] Found existing customer {customer_id} for {account_id}")
                    return customer_id
                
                # Customer doesn't exist in Stripe - clean up stale record
                await self._cleanup_stale_customer_record(session, account_id)
                await session.commit()
                return None
                
        except Exception as e:
            logger.warning(f"[CUSTOMER] Error checking existing customer: {e}")
            return None
    
    async def _validate_stripe_customer(self, customer_id: str) -> bool:
        """Verify customer exists in Stripe."""
        try:
            customer = await StripeAPIWrapper.retrieve_customer(customer_id)
            return customer is not None and not customer.get('deleted', False)
        except Exception:
            return False
    
    async def _cleanup_stale_customer_record(self, session, account_id: str) -> None:
        """Remove stale customer record from database."""
        from sqlalchemy import text
        
        await session.execute(
            text("DELETE FROM billing_customers WHERE account_id = CAST(:account_id AS UUID)"),
            {"account_id": account_id}
        )
        logger.info(f"[CUSTOMER] Cleaned up stale customer record for {account_id}")
    
    async def _create_new_customer(self, account_id: str) -> str:
        """Create new Stripe customer and store in database."""
        # Get user email
        email = await self._get_user_email(account_id)
        
        if not email:
            raise BillingError(
                code="EMAIL_NOT_FOUND",
                message=f"Could not find email for account {account_id}",
                details={"account_id": account_id}
            )
        
        # Create Stripe customer
        try:
            customer = await StripeAPIWrapper.create_customer(
                email=email,
                metadata={"account_id": account_id}
            )
            customer_id = customer.id
            
            logger.info(f"[CUSTOMER] Created Stripe customer {customer_id} for {account_id}")
            
        except Exception as e:
            logger.error(f"[CUSTOMER] Failed to create Stripe customer: {e}")
            raise BillingError(
                code="STRIPE_CUSTOMER_CREATE_FAILED",
                message=f"Failed to create Stripe customer: {e}",
                details={"account_id": account_id}
            )
        
        # Store in database
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                await session.execute(
                    text("""
                        INSERT INTO billing_customers (id, account_id, email, created_at)
                        VALUES (:id, CAST(:account_id AS UUID), :email, NOW())
                        ON CONFLICT (account_id) DO UPDATE 
                        SET id = :id, email = :email
                    """),
                    {
                        "id": customer_id,
                        "account_id": account_id,
                        "email": email
                    }
                )
                await session.commit()
                
        except Exception as e:
            logger.error(f"[CUSTOMER] Failed to store customer record: {e}")
            # Customer was created in Stripe, so return it anyway
        
        return customer_id
    
    async def _get_user_email(self, account_id: str) -> Optional[str]:
        """Get user email for account."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                # Try to get from billing_customers first
                result = await session.execute(
                    text("""
                        SELECT email FROM billing_customers
                            WHERE account_id = CAST(:account_id AS UUID)
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                if row and row.email:
                    return row.email
                
                # Try users table
                result = await session.execute(
                    text("""
                        SELECT email FROM users
                        WHERE id = CAST(:account_id AS UUID)
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                if row and row.email:
                    return row.email
                
                return None
                
        except Exception as e:
            logger.warning(f"[CUSTOMER] Error getting email for {account_id}: {e}")
            return None
    
    @classmethod
    async def get_customer_email(cls, account_id: str) -> Optional[str]:
        """Get email for a customer account."""
        handler = cls()
        return await handler._get_user_email(account_id)
    
    @classmethod
    async def update_customer_email(cls, account_id: str, email: str) -> bool:
        """Update customer email in Stripe and database."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                result = await session.execute(
                    text("SELECT id FROM billing_customers WHERE account_id = CAST(:account_id AS UUID)"),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                
                if row:
                    customer_id = row.id
                    
                    # Update in Stripe
                    await StripeAPIWrapper.update_customer(customer_id, email=email)
                    
                    # Update in database
                    await session.execute(
                        text("""
                            UPDATE billing_customers 
                            SET email = :email 
                                WHERE account_id = CAST(:account_id AS UUID)
                        """),
                        {"email": email, "account_id": account_id}
                    )
                    await session.commit()
                    
                    logger.info(f"[CUSTOMER] Updated email for {account_id}")
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"[CUSTOMER] Failed to update email: {e}")
            return False


# Convenience function
async def get_or_create_stripe_customer(account_id: str) -> str:
    """Get or create Stripe customer for account."""
    return await CustomerHandler.get_or_create_stripe_customer(account_id)
