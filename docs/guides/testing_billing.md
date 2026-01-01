
# Billing System Testing Guide

This guide explains how to run the comprehensive test suite for the billing system.

## Test Suite Overview

The billing tests are located in `backend/tests/live/billing/` and are divided into:

1.  **Integration Tests** (`integration/`)
    - `test_endpoints.py`: Direct API endpoint verification (`/account-state`, `/subscriprions/checkout`).
    - `test_webhooks.py`: Stripe webhook validation (headers, signatures).

2.  **Scenario Tests** (`scenarios/`)
    - `test_user_scenarios.py`: Full user application flows (Free -> Pro upgrade, Credit Purchase).

3.  **End-to-End Test** (`test_billing_e2e.py`)
    - Legacy script that tests the internal service logic.

## Prerequisites

- **Environment Variables**:
    - `STRIPE_SECRET_KEY`: Required for Stripe client (can be a dummy if fully mocked).
    - `STRIPE_WEBHOOK_SECRET`: Required for webhook signature validation tests.
    
- **Database**:
    - Tests run against the configured test database (PostgreSQL).
    - Redis is mocked in the default test configuration.

## Running the Tests

### 1. Run All Billing Tests
```bash
pytest backend/tests/live/billing
```

### 2. Run Specific Components

**API Endpoints:**
```bash
pytest backend/tests/live/billing/integration/test_endpoints.py
```

**Webhooks:**
```bash
pytest backend/tests/live/billing/integration/test_webhooks.py
```

**User Scenarios (Recommended for Validation):**
```bash
pytest backend/tests/live/billing/scenarios/test_user_scenarios.py
```

### 3. Debugging

If tests hang or fail, ensure:
1.  **Docker** is running (if not mocked).
2.  **PostgreSQL** is accessible.
3.  Check `conftest.py` in `backend/tests/live/billing/` for mock configurations.

## Test Coverage

| Component | Test File | Coverage |
|-----------|-----------|----------|
| **Router** | `test_endpoints.py` | API Prefix, Versioning, Mounting |
| **Account State** | `test_endpoints.py` | Structure, Tiers, Credits, Limits |
| **Checkout** | `test_endpoints.py` | Session creation, Parameter validation |
| **Webhooks** | `test_webhooks.py` | Signature validation, Security headers |
| **Upgrade Flow** | `test_user_scenarios.py` | Free -> Pro transition via Webhook |
| **Purchases** | `test_user_scenarios.py` | Credit balance update after payment |

## Mocking Strategy

- **Stripe API**: heavily mocked using `unittest.mock` to prevent real API calls.
- **Redis**: Mocked via `mock_plugin_parsing` fixture to avoid side effects during import.
- **Heavy Services**: `sandbox_service` and `checkpointer_manager` initialization is mocked to speed up tests.
