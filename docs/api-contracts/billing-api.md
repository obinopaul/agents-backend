# Billing API Reference

Complete API documentation for the billing and credits system.

---

## Module Imports

```python
# High-level interface (recommended)
from backend.src.billing import (
    # Billing integration
    check_model_and_billing_access,
    deduct_usage,
    can_afford,
    get_credit_summary,
    
    # Subscription service
    subscription_service,
    create_checkout_session,
    cancel_subscription,
    
    # Payment service
    payment_service,
    reconciliation_service,
    
    # Credit manager
    credit_manager,
    add_credits,
    
    # Configuration
    TIERS, get_tier_by_name, is_model_allowed,
    
    # Exceptions
    InsufficientCreditsError, BillingError, SubscriptionError,
)
```

---

## BillingIntegration API

### check_model_and_billing_access

Pre-flight check before billable operations.

```python
async def check_model_and_billing_access(
    account_id: str,
    model_name: str | None = None,
    estimated_cost: Decimal | None = None
) -> Tuple[bool, str, Dict]
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `account_id` | `str` | User account UUID |
| `model_name` | `str` | LLM model identifier |
| `estimated_cost` | `Decimal` | Optional pre-check amount |

**Returns:** `Tuple[can_run, message, info]`

**Error Types in `info`:**

| error_type | HTTP | Meaning |
|------------|------|---------|
| `model_access_denied` | 403 | Model not in tier |
| `insufficient_credits` | 402 | Balance too low |
| `no_account` | 400 | Account not found |

**Example:**

```python
can_run, message, info = await check_model_and_billing_access(
    account_id=user_id, model_name="gpt-4"
)
if not can_run:
    if info["error_type"] == "model_access_denied":
        raise HTTPException(403, {"allowed_models": info["allowed_models"]})
```

---

### deduct_usage

Deduct credits after an LLM operation.

```python
async def deduct_usage(
    account_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
    thread_id: str | None = None,
    message_id: str | None = None,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0
) -> Dict
```

**Returns:**

```python
{
    "success": True,
    "cost": 0.045,
    "new_balance": 19.95,
    "from_daily": 0.02,
    "from_expiring": 0.025,
    "from_non_expiring": 0.0,
    "transaction_id": "uuid"
}
```

---

### can_afford

Quick affordability check.

```python
async def can_afford(account_id: str, estimated_cost: Decimal) -> bool
```

---

## CreditManager API

### add_credits

Add credits to an account.

```python
async def add_credits(
    account_id: str,
    amount: Decimal,
    is_expiring: bool = True,
    description: str = "Credit added",
    credit_type: str | None = None,
    stripe_event_id: str | None = None,
    metadata: Dict | None = None
) -> Dict
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `is_expiring` | `bool` | `True` for monthly, `False` for purchased |
| `stripe_event_id` | `str` | Idempotency key (prevents duplicates) |

---

### deduct_credits

Low-level credit deduction with priority order.

```python
async def deduct_credits(
    account_id: str,
    amount: Decimal,
    description: str = "Credit deducted",
    deduction_type: str = "usage",
    allow_negative: bool = False
) -> Dict
```

**Priority Order:** daily → expiring → non_expiring

**Raises:** `InsufficientCreditsError` if balance too low

---

### get_balance

Get current credit balance.

```python
async def get_balance(account_id: str, use_cache: bool = True) -> Dict
```

**Returns:**

```python
{
    "total": Decimal("45.50"),
    "daily": Decimal("0.05"),
    "expiring": Decimal("20.45"),
    "non_expiring": Decimal("25.00")
}
```

---

## SubscriptionService API

### create_checkout_session

Create Stripe checkout for subscription.

```python
async def create_checkout_session(
    account_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    commitment_type: str | None = None,
    locale: str | None = None
) -> Dict
```

**Returns:**

```python
{
    "success": True,
    "checkout_url": "https://checkout.stripe.com/...",
    "session_id": "cs_xxx",
    "flow_type": "new"  # or "trial_conversion", "upgrade"
}
```

---

### cancel_subscription

Cancel subscription (downgrades to free at period end).

```python
async def cancel_subscription(
    account_id: str,
    feedback: str | None = None
) -> Dict
```

**Returns:**

```python
{
    "success": True,
    "message": "Subscription will be cancelled at period end",
    "effective_date": "2025-01-31T00:00:00Z"
}
```

---

### reactivate_subscription

Undo scheduled cancellation.

```python
async def reactivate_subscription(account_id: str) -> Dict
```

---

### get_user_subscription_tier

Get tier info with caching.

```python
async def get_user_subscription_tier(
    account_id: str,
    skip_cache: bool = False
) -> Dict
```

**Returns:**

```python
{
    "name": "tier_2_20",
    "display_name": "Plus",
    "credits": 20.0,
    "can_purchase_credits": True,
    "models": ["gpt-4o", "claude-3.5-sonnet"],
    "project_limit": 50,
    "thread_limit": 10,
    "concurrent_runs": 3
}
```

---

### Trial Operations

```python
# Check eligibility
status = await subscription_service.get_trial_status(account_id)
# {"can_start_trial": True, "trial_duration_days": 7, "trial_credits": 5.0}

# Start trial
result = await subscription_service.start_trial(
    account_id, success_url, cancel_url
)
# {"checkout_url": "...", "trial_duration_days": 7}

# Cancel trial
result = await subscription_service.cancel_trial(account_id)
```

---

### create_portal_session

Create Stripe Customer Portal session.

```python
async def create_portal_session(
    account_id: str,
    return_url: str
) -> Dict
```

**Returns:** `{"portal_url": "https://billing.stripe.com/..."}`

---

## PaymentService API

### create_checkout_session

Create checkout for credit purchase.

```python
async def create_checkout_session(
    account_id: str,
    amount: Decimal,
    success_url: str,
    cancel_url: str
) -> Dict
```

**Raises:** `PaymentError` if tier doesn't allow purchases

---

### list_purchases

List credit purchase history.

```python
async def list_purchases(
    account_id: str,
    limit: int = 10,
    status: str | None = None
) -> Dict
```

---

## ReconciliationService API

### run_full_reconciliation

Run all reconciliation tasks.

```python
async def run_full_reconciliation() -> Dict
```

**Returns:**

```python
{
    "timestamp": "2025-01-01T00:00:00Z",
    "failed_payments": {"checked": 5, "fixed": 1, "failed": 0},
    "balance_check": {"checked": 100, "fixed": 2, "discrepancies_found": []},
    "duplicate_check": {"total_checked": 500, "duplicates_found": []},
    "expired_cleanup": {"accounts_cleaned": 3, "credits_removed": 15.5}
}
```

### Individual Tasks

```python
# Fix orphaned payments
await reconciliation_service.reconcile_failed_payments(hours=24)

# Verify balances
await reconciliation_service.verify_balance_consistency()

# Detect duplicates
await reconciliation_service.detect_double_charges(days=7)

# Cleanup expired
await reconciliation_service.cleanup_expired_credits()

# Retry specific payment
await reconciliation_service.retry_failed_payment(payment_id)
```

---

## API Endpoints

### Account State

```http
GET /billing/account-state?skip_cache=false
```

**Response:**

```json
{
  "credits": {
    "total": 2000,
    "daily": 5,
    "monthly": 1995,
    "extra": 0,
    "can_run": true,
    "daily_refresh": {
      "enabled": true,
      "next_refresh_at": "2025-01-01T06:00:00Z"
    }
  },
  "subscription": {
    "tier_key": "tier_2_20",
    "tier_display_name": "Plus",
    "status": "active",
    "is_trial": false,
    "can_purchase_credits": true
  },
  "models": [
    {"id": "gpt-4o", "name": "GPT-4o", "allowed": true}
  ],
  "limits": {
    "threads": {"max": 10, "can_create": true},
    "concurrent_runs": {"limit": 3, "can_start": true}
  }
}
```

---

### Subscription Endpoints

```http
POST /billing/create-checkout-session
Content-Type: application/json

{
  "tier_key": "tier_2_20",
  "success_url": "/billing/success",
  "cancel_url": "/billing/cancel",
  "commitment_type": "monthly"
}
```

```http
POST /billing/cancel-subscription
Content-Type: application/json

{"feedback": "Too expensive"}
```

```http
POST /billing/reactivate-subscription
```

---

### Trial Endpoints

```http
GET /billing/trial/status
```

```http
POST /billing/trial/start
Content-Type: application/json

{
  "success_url": "/trial/success",
  "cancel_url": "/trial/cancel"
}
```

---

### Payment Endpoints

```http
POST /billing/purchase-credits
Content-Type: application/json

{
  "amount": 25.00,
  "success_url": "/purchase/success",
  "cancel_url": "/purchase/cancel"
}
```

```http
GET /billing/transactions?limit=50&offset=0
GET /billing/transactions/summary?days=30
GET /billing/credit-usage?limit=50
```

---

### Webhook Endpoint

```http
POST /billing/webhook
Stripe-Signature: t=1234,v1=abc123...
```

**Handled Events:**

| Event | Handler |
|-------|---------|
| `checkout.session.completed` | CheckoutHandler |
| `customer.subscription.created` | SubscriptionHandler |
| `customer.subscription.updated` | SubscriptionHandler |
| `customer.subscription.deleted` | SubscriptionHandler |
| `invoice.payment_succeeded` | InvoiceHandler |
| `invoice.payment_failed` | InvoiceHandler |
| `charge.refunded` | RefundHandler |

---

## Exceptions

```python
from backend.src.billing import (
    BillingError,           # Base class
    InsufficientCreditsError,
    SubscriptionError,
    PaymentError,
    TierNotFoundError,
    TrialError,
    WebhookError,
    ReconciliationError,
    CircuitBreakerOpenError,
)

try:
    await credit_manager.deduct_credits(account_id, Decimal("100"))
except InsufficientCreditsError as e:
    print(f"Need ${e.required}, have ${e.available}")
except BillingError as e:
    print(f"Error [{e.code}]: {e.message}")
```

---

## Stripe Integration

### StripeAPIWrapper

```python
from backend.src.billing import StripeAPIWrapper

# Create customer
customer = await StripeAPIWrapper.create_customer(
    email="user@example.com",
    metadata={"account_id": str(account_id)}
)

# Create checkout
session = await StripeAPIWrapper.create_checkout_session(
    mode="subscription",
    customer=customer.id,
    line_items=[{"price": "price_xxx", "quantity": 1}],
    success_url="https://app.com/success",
    cancel_url="https://app.com/cancel"
)

# Circuit breaker status
status = await StripeAPIWrapper.get_circuit_status()
# {'state': 'closed', 'failure_count': 0, 'status': '✅ Healthy'}
```

---

## Complete Integration Example

```python
from fastapi import APIRouter, HTTPException, Depends
from backend.src.billing import (
    check_model_and_billing_access,
    deduct_usage,
)

@router.post("/chat")
async def chat(request: ChatRequest, user_id: str = Depends(get_user)):
    # 1. Pre-flight check
    can_run, msg, info = await check_model_and_billing_access(
        account_id=user_id, model_name=request.model
    )
    if not can_run:
        if info["error_type"] == "model_access_denied":
            raise HTTPException(403, detail=msg)
        raise HTTPException(402, detail=msg)
    
    # 2. Run LLM
    response = await llm.chat(request.model, request.messages)
    
    # 3. Deduct credits
    billing = await deduct_usage(
        account_id=user_id,
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        model=request.model,
        thread_id=request.thread_id
    )
    
    return {
        "response": response.content,
        "billing": {"cost": billing["cost"], "balance": billing["new_balance"]}
    }
```

---

## Related Documentation

- [Billing Guide](../guides/billing-credits.md) - Overview and quick start
- [Environment Variables](../guides/environment-variables.md) - Configuration
