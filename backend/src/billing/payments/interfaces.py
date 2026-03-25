"""
Payment Interfaces

Protocol definitions for payment and reconciliation services.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict


class PaymentProcessorInterface(ABC):
    """Interface for payment processing services."""
    
    @abstractmethod
    async def validate_payment_eligibility(self, account_id: str) -> bool:
        """Check if account can make payments."""
        pass
    
    @abstractmethod
    async def create_checkout_session(
        self,
        account_id: str,
        amount: Decimal,
        success_url: str,
        cancel_url: str
    ) -> Dict:
        """Create checkout session for payment."""
        pass


class ReconciliationManagerInterface(ABC):
    """Interface for payment reconciliation services."""
    
    @abstractmethod
    async def reconcile_failed_payments(self) -> Dict:
        """Reconcile orphaned or failed payments."""
        pass
    
    @abstractmethod
    async def verify_balance_consistency(self) -> Dict:
        """Verify credit balances are consistent."""
        pass
    
    @abstractmethod
    async def detect_double_charges(self) -> Dict:
        """Detect duplicate charges or credits."""
        pass
    
    @abstractmethod
    async def cleanup_expired_credits(self) -> Dict:
        """Remove expired credits."""
        pass
    
    @abstractmethod
    async def retry_failed_payment(self, payment_id: str) -> Dict:
        """Retry a specific failed payment."""
        pass
