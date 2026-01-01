"""
Payments Module

Handles one-time credit purchases and payment reconciliation.

Components:
- PaymentService: Credit purchase checkout
- ReconciliationService: Balance verification and cleanup

Usage:
    from backend.src.billing.payments import payment_service, reconciliation_service
    
    # Create credit purchase checkout
    result = await payment_service.create_checkout_session(
        account_id, amount, success_url, cancel_url
    )
    
    # Run reconciliation
    results = await reconciliation_service.run_full_reconciliation()
"""

from .service import (
    PaymentService,
    payment_service,
)

from .reconciliation import (
    ReconciliationService,
    reconciliation_service,
)

from .interfaces import (
    PaymentProcessorInterface,
    ReconciliationManagerInterface,
)

__all__ = [
    # Services
    'PaymentService',
    'payment_service',
    'ReconciliationService',
    'reconciliation_service',
    # Interfaces
    'PaymentProcessorInterface',
    'ReconciliationManagerInterface',
]
