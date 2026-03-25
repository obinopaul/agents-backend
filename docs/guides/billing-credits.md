# Billing & Credits System

Comprehensive billing system for managing subscriptions, credits, and payments via Stripe integration.

---

## Overview

The billing system provides:

- **Subscription Management** - 4 tiers (free, plus, pro, ultra) via Stripe
- **Credit System** - Priority-based credit deduction (daily → expiring → non-expiring)
- **Usage Tracking** - Token-level cost calculation with full audit trail
- **Daily Refresh** - Automatic daily credit grants for free tier users
- **Trial Management** - 7-day trials with automatic conversion
- **Payment Processing** - Credit package purchases with reconciliation
- **Stripe Integration** - Webhooks, checkout sessions, invoices, refunds

### Credits vs. Billing: What is the difference?

You might notice we often use the terms **"Credits"** and **"Billing"**. While related, they refer to different layers of the system:

*   **Billing (The Interface & Management)**: This is the high-level system that handles subscriptions (Stripe), payments, invoices, and account states. It dictates *how* a user gets credits (e.g., buying a package, subscribing to a tier). The endpoints for this are in `backend/src/billing/endpoints`.
*   **Credits (The Internal Engine)**: This is the low-level logic that handles the *accounting*. It manages the ledger, atomic deductions, balance calculations, and specific resource costs (e.g., tokens). It doesn't care *how* you got the credits (paid vs free), only that you have them and can spend them. The logic for this resides in `backend/src/billing/credits`.

**In short:** You use the **Billing** API to buy/subscribe, and the system uses the **Credits** engine to track your usage.


---

## Architecture

```mermaid
graph TB
    subgraph Application Layer
        API[API Endpoints]
        Agent[Agent Runs]
        LLM[LLM Calls]
    end
    
    subgraph Billing Router
        AS[/account-state]
        SUB[/subscriptions]
        PAY[/payments]
        WH[/webhook]
    end
    
    subgraph Services
        BI[BillingIntegration]
        SS[SubscriptionService]
        PS[PaymentService]
        RS[ReconciliationService]
    end
    
    subgraph Core
        CM[CreditManager]
        CC[CreditCalculator]
        DR[DailyCreditRefresh]
        TC[TierConfig]
    end
    
    subgraph External
        SW[StripeAPIWrapper]
        CB[CircuitBreaker]
        WS[WebhookService]
    end
    
    subgraph Database
        CA[(credit_accounts)]
        CL[(credit_ledger)]
        CP[(credit_purchases)]
        TH[(trial_history)]
    end
    
    API --> AS
    API --> SUB
    API --> PAY
    
    AS --> BI
    SUB --> SS
    PAY --> PS
    WH --> WS
    
    BI --> CM
    BI --> CC
    SS --> SW
    PS --> SW
    
    CM --> CA
    CM --> CL
    PS --> CP
    
    SW --> CB
```

---

## Module Structure

```
backend/src/billing/
├── __init__.py                 # Main exports (200+ symbols)
├── shared/                     # Configuration & utilities
│   ├── config.py              # Tier definitions, credit packages
│   ├── exceptions.py          # Custom exceptions (8 types)
│   └── cache_utils.py         # Redis caching
├── domain/                     # Domain entities
│   ├── credit_account.py      # CreditAccount dataclass
│   └── subscription.py        # Subscription dataclass + enums
├── external/stripe/           # Stripe integration
│   ├── circuit_breaker.py     # API resilience (3-state)
│   ├── client.py              # StripeAPIWrapper (20+ methods)
│   ├── idempotency.py         # Key generation
│   ├── webhook_lock.py        # Distributed locking
│   ├── webhooks.py            # Event dispatcher
│   └── handlers/              # Event handlers
│       ├── checkout.py        # checkout.session.completed
│       ├── subscription.py    # subscription.* events
│       ├── invoice.py         # invoice.* events
│       └── refund.py          # charge.refunded
├── credits/                    # Credit management
│   ├── manager.py             # Atomic operations (~500 lines)
│   ├── calculator.py          # Token cost calculation
│   ├── daily_refresh.py       # Automatic daily grants
│   └── integration.py         # High-level interface
├── subscriptions/             # Subscription management
│   ├── service.py             # SubscriptionService orchestrator
│   ├── free_tier_service.py   # Auto-enrollment
│   ├── trial_service.py       # Trial lifecycle
│   └── handlers/              # Specialized handlers
│       ├── customer.py        # Stripe customer management
│       ├── checkout.py        # Checkout sessions (4 flows)
│       ├── lifecycle.py       # Cancel, reactivate, status
│       ├── tier.py            # Tier lookup, model access
│       └── portal.py          # Customer portal
├── payments/                  # Payment processing
│   ├── service.py             # Credit purchase checkout
│   ├── reconciliation.py      # Balance verification
│   └── interfaces.py          # Protocols
└── endpoints/                 # API routes
    ├── account_state.py       # Unified billing data
    ├── subscriptions.py       # Subscription mutations
    ├── payments.py            # Credit purchases
    ├── webhooks.py            # Stripe webhooks
    └── dependencies.py        # Auth helpers
```

---

## Subscription Tiers

| Tier | Price | Monthly Credits | Models | Threads | Concurrent |
|------|-------|-----------------|--------|---------|------------|
| **free** | $0 | $0.05/day | gpt-4o-mini | 5 | 1 |
| **plus** | $20/mo | $20 | gpt-4o, claude-3.5 | 10 | 3 |
| **pro** | $50/mo | $50 | All standard | 25 | 10 |
| **ultra** | $200/mo | $200 | All + priority | ∞ | 25 |

### Daily Credits (Free Tier)

Free tier users receive `$0.05` daily:
- Resets every ~20 hours
- Does not accumulate (max balance = daily amount)
- Consumed first before other credit types

---

## Credit Types & Priority

| Priority | Type | Description | Expiration |
|----------|------|-------------|------------|
| 1 | `daily_credits_balance` | Free tier daily grant | Resets on refresh |
| 2 | `expiring_credits` | Monthly subscription | End of billing cycle |
| 3 | `non_expiring_credits` | Purchased credits | Never |

**Deduction Order**: Credits consumed in priority order (1→2→3), preserving purchased credits as long as possible.

---

## Credit Packages

| Package | Price | Credits | Bonus |
|---------|-------|---------|-------|
| Starter | $10 | $10 | - |
| Basic | $25 | $27.50 | 10% |
| Standard | $50 | $60 | 20% |
| Pro | $100 | $130 | 30% |
| Business | $250 | $350 | 40% |
| Enterprise | $500 | $750 | 50% |

---

## Quick Start

### 1. Pre-Flight Check (Before LLM Call)

```python
from backend.src.billing import check_model_and_billing_access

can_run, message, info = await check_model_and_billing_access(
    account_id=user_id,
    model_name="gpt-4"
)

if not can_run:
    if info.get("error_type") == "model_access_denied":
        raise HTTPException(403, "Upgrade required")
    elif info.get("error_type") == "insufficient_credits":
        raise HTTPException(402, "Add credits")
```

### 2. Deduct Usage (After LLM Call)

```python
from backend.src.billing import deduct_usage

result = await deduct_usage(
    account_id=user_id,
    prompt_tokens=1000,
    completion_tokens=500,
    model="gpt-4",
    thread_id=thread_id
)
# Returns: {"success": True, "cost": 0.045, "new_balance": 19.95}
```

### 3. Subscription Management

```python
from backend.src.billing import subscription_service

# Create checkout for upgrade
result = await subscription_service.create_checkout_session(
    account_id=user_id,
    price_id="price_xxx",
    success_url="/billing/success",
    cancel_url="/billing/cancel"
)

# Cancel subscription (keeps access until period end)
result = await subscription_service.cancel_subscription(user_id)

# Start trial
result = await subscription_service.start_trial(
    user_id, success_url, cancel_url
)
```

### 4. Register API Routes

```python
from backend.src.billing.endpoints import billing_router

app.include_router(billing_router, prefix="/billing")
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/billing/account-state` | GET | Unified billing data (cached) |
| `/billing/create-checkout-session` | POST | Subscription checkout |
| `/billing/create-portal-session` | POST | Customer portal |
| `/billing/cancel-subscription` | POST | Cancel subscription |
| `/billing/reactivate-subscription` | POST | Reactivate cancelled |
| `/billing/trial/status` | GET | Trial eligibility |
| `/billing/trial/start` | POST | Start trial |
| `/billing/trial/cancel` | POST | Cancel trial |
| `/billing/purchase-credits` | POST | Credit purchase |
| `/billing/transactions` | GET | Transaction history |
| `/billing/transactions/summary` | GET | Usage summary |
| `/billing/credit-usage` | GET | Credit usage records |
| `/billing/webhook` | POST | Stripe webhooks |

---

## Trial System

- **Duration**: 7 days
- **Tier**: Plus-level features ($20/mo equivalent)
- **Credits**: $5.00 trial credits
- **Requirement**: Valid payment method (card setup)
- **Conversion**: Auto-converts to paid at trial end

```python
# Check eligibility
status = await subscription_service.get_trial_status(user_id)
if status.get("can_start_trial"):
    result = await subscription_service.start_trial(
        user_id, success_url, cancel_url
    )
```

---

## Reconciliation

The billing system includes automatic reconciliation:

```python
from backend.src.billing import reconciliation_service

# Run full reconciliation (hourly via cron)
results = await reconciliation_service.run_full_reconciliation()
```

| Task | Description |
|------|-------------|
| `reconcile_failed_payments` | Fix orphaned payments where Stripe succeeded but credits weren't granted |
| `verify_balance_consistency` | Check balance = daily + expiring + non_expiring |
| `detect_double_charges` | Find duplicate ledger entries within 60s |
| `cleanup_expired_credits` | Remove credits past expiry date |

---

## Database Schema

### credit_accounts

| Column | Type | Description |
|--------|------|-------------|
| `account_id` | UUID | User account reference |
| `balance` | DECIMAL | Total available credits |
| `daily_credits_balance` | DECIMAL | Daily refresh credits |
| `expiring_credits` | DECIMAL | Monthly subscription credits |
| `non_expiring_credits` | DECIMAL | Purchased credits |
| `tier` | VARCHAR | Current subscription tier |
| `stripe_customer_id` | VARCHAR | Stripe customer ID |
| `stripe_subscription_id` | VARCHAR | Active subscription ID |
| `trial_status` | VARCHAR | none/active/expired/cancelled |
| `trial_ends_at` | TIMESTAMP | Trial expiration |

### credit_ledger

| Column | Type | Description |
|--------|------|-------------|
| `account_id` | UUID | Account reference |
| `amount` | DECIMAL | Credit change (+/-) |
| `type` | VARCHAR | usage, tier_grant, purchase, refund |
| `model` | VARCHAR | LLM model (for usage) |
| `input_tokens` | INTEGER | Prompt tokens |
| `output_tokens` | INTEGER | Completion tokens |
| `stripe_event_id` | VARCHAR | Idempotency key |

---

## Configuration

### Environment Variables

```bash
# Stripe Keys
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Subscription Price IDs
STRIPE_FREE_TIER_ID=price_xxx
STRIPE_TIER_2_20_ID=price_xxx          # Plus ($20/mo)
STRIPE_TIER_6_50_ID=price_xxx          # Pro ($50/mo)
STRIPE_TIER_25_200_ID=price_xxx        # Ultra ($200/mo)

# Yearly Price IDs (10% discount)
STRIPE_TIER_2_20_YEARLY_ID=price_xxx
STRIPE_TIER_6_50_YEARLY_ID=price_xxx
STRIPE_TIER_25_200_YEARLY_ID=price_xxx

# Feature Flags
BILLING_ENABLED=true
ENV=production  # Set to 'local' to disable billing
```

---

## Related Documentation

- [Billing API Reference](../api-contracts/billing-api.md) - Complete API documentation
- [Environment Variables](./environment-variables.md) - Configuration reference
- [Database Schema](../api-contracts/database.md) - Table definitions
