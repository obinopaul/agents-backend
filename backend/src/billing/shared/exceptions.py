"""
Billing Exceptions

Custom exception classes for billing-related errors.
These provide structured error handling across the billing module.
"""


class BillingError(Exception):
    """
    Base exception for all billing-related errors.
    
    All billing exceptions inherit from this class, allowing for
    broad exception handling when needed.
    """
    
    def __init__(self, message: str, code: str = "BILLING_ERROR", details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        """Convert exception to dictionary for API responses."""
        return {
            'error': self.code,
            'message': self.message,
            'details': self.details
        }


class InsufficientCreditsError(BillingError):
    """
    Raised when a user doesn't have enough credits for an operation.
    
    Attributes:
        required: Credits required for the operation
        available: Credits currently available
    """
    
    def __init__(
        self, 
        message: str = "Insufficient credits for this operation",
        required: float = 0,
        available: float = 0
    ):
        super().__init__(
            message=message,
            code="INSUFFICIENT_CREDITS",
            details={
                'required': required,
                'available': available,
                'shortfall': max(0, required - available)
            }
        )
        self.required = required
        self.available = available


class SubscriptionError(BillingError):
    """
    Raised when there's an issue with subscription management.
    
    Examples:
        - Subscription not found
        - Cannot upgrade/downgrade
        - Subscription already cancelled
    """
    
    def __init__(
        self, 
        message: str = "Subscription error",
        code: str = "SUBSCRIPTION_ERROR",
        subscription_id: str = None
    ):
        super().__init__(
            message=message,
            code=code,
            details={'subscription_id': subscription_id} if subscription_id else {}
        )
        self.subscription_id = subscription_id


class PaymentError(BillingError):
    """
    Raised when there's an issue with payment processing.
    
    Examples:
        - Payment failed
        - Invalid payment method
        - Checkout session creation failed
    """
    
    def __init__(
        self, 
        message: str = "Payment processing error",
        code: str = "PAYMENT_ERROR",
        payment_intent_id: str = None,
        stripe_error: str = None
    ):
        details = {}
        if payment_intent_id:
            details['payment_intent_id'] = payment_intent_id
        if stripe_error:
            details['stripe_error'] = stripe_error
            
        super().__init__(
            message=message,
            code=code,
            details=details
        )
        self.payment_intent_id = payment_intent_id
        self.stripe_error = stripe_error


class WebhookError(BillingError):
    """
    Raised when there's an issue processing a webhook.
    
    Examples:
        - Invalid signature
        - Duplicate event
        - Processing failed
    """
    
    def __init__(
        self, 
        message: str = "Webhook processing error",
        code: str = "WEBHOOK_ERROR",
        event_id: str = None,
        event_type: str = None
    ):
        details = {}
        if event_id:
            details['event_id'] = event_id
        if event_type:
            details['event_type'] = event_type
            
        super().__init__(
            message=message,
            code=code,
            details=details
        )
        self.event_id = event_id
        self.event_type = event_type


class TierNotFoundError(BillingError):
    """Raised when a requested tier doesn't exist."""
    
    def __init__(self, tier_name: str):
        super().__init__(
            message=f"Tier '{tier_name}' not found",
            code="TIER_NOT_FOUND",
            details={'tier_name': tier_name}
        )
        self.tier_name = tier_name


class TrialError(BillingError):
    """
    Raised when there's an issue with trial management.
    
    Examples:
        - Trial already used
        - Trial not available
        - Trial conversion failed
    """
    
    def __init__(
        self, 
        message: str = "Trial error",
        code: str = "TRIAL_ERROR",
        account_id: str = None
    ):
        super().__init__(
            message=message,
            code=code,
            details={'account_id': account_id} if account_id else {}
        )
        self.account_id = account_id


class ReconciliationError(BillingError):
    """Raised when payment reconciliation fails."""
    
    def __init__(
        self, 
        message: str = "Reconciliation error",
        purchase_id: str = None
    ):
        super().__init__(
            message=message,
            code="RECONCILIATION_ERROR",
            details={'purchase_id': purchase_id} if purchase_id else {}
        )
        self.purchase_id = purchase_id


class CircuitBreakerOpenError(BillingError):
    """Raised when the circuit breaker is open and preventing calls."""
    
    def __init__(
        self, 
        message: str = "Circuit breaker is open. Service temporarily unavailable.",
        service_name: str = "stripe",
        reset_time: float = None
    ):
        super().__init__(
            message=message,
            code="CIRCUIT_BREAKER_OPEN",
            details={
                'service_name': service_name,
                'reset_time': reset_time
            }
        )
        self.service_name = service_name
        self.reset_time = reset_time
