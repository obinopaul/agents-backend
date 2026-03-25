# User Management Lifecycle

> Account creation, credits, and API keys.

---

## Overview

User management covers:
- **Account creation** (signup, OAuth)
- **Profile management** (update, password)
- **Credit system** (balance, usage)
- **API keys** (create, revoke)

---

## Account Creation Flow

```mermaid
flowchart TD
    A[New User] --> B{Registration Method}
    
    B -->|Email/Password| C[POST /admin/auth/register]
    B -->|GitHub OAuth| D[GET /oauth2/github/authorize]
    B -->|Google OAuth| E[GET /oauth2/google/authorize]
    
    C --> F[Validate input]
    F --> G[Hash password with Argon2]
    G --> H[Generate UUID]
    H --> I[Insert sys_user]
    
    D --> J[OAuth callback]
    J --> K{User exists?}
    K -->|No| L[Create sys_user]
    K -->|Yes| M[Link sys_user_social]
    L --> M
    
    I --> N[Initialize credits = 0]
    M --> N
    N --> O[Generate JWT]
    O --> P[Return access_token]
```

---

## Credit System

### Credit Types
| Column | Purpose |
|--------|---------|
| `credits` | Primary balance (paid credits) |
| `bonus_credits` | Free/promotional credits |

**Usage order:** Bonus credits consumed first, then regular credits.

### Credit Flow
```mermaid
flowchart TD
    A[User makes API call] --> B[JWT validated]
    B --> C[Get user from DB]
    C --> D{Has credits?}
    
    D -->|Yes| E[Process request]
    E --> F[LLM generates response]
    F --> G[Calculate token cost]
    G --> H[Deduct from credits]
    H --> I[Update session_metrics]
    
    D -->|No| J[Return 402 Payment Required]
```

### Credit Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/agent/credits/balance` | Get current balance |
| GET | `/agent/credits/usage` | Get usage history |
| POST | `/agent/credits/add` | Add credits (admin) |

### Balance Response
```json
{
  "credits": 100.50,
  "bonus_credits": 25.00,
  "total": 125.50
}
```

---

## API Keys

### Purpose
API keys allow tool server authentication without JWT:
- Used by MCP tool server
- Enabled for specific integrations

### Key Format
```
sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```
Prefix `sk_` followed by 32 URL-safe characters.

### API Key Flow
```mermaid
flowchart TD
    A[User] --> B[POST /admin/sys/api-keys]
    B --> C[Generate sk_ key]
    C --> D[Store in agent_api_keys]
    D --> E[Return key to user]
    
    F[Tool Server] --> G[Request with api_key]
    G --> H[Validate against DB]
    H --> I[Update last_used_at]
    I --> J[Process request]
```

### Database Table: `agent_api_keys`
| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGINT | Primary key |
| `user_id` | BIGINT | Owner |
| `api_key` | VARCHAR(256) | The key (hashed in production) |
| `name` | VARCHAR(128) | Label |
| `is_active` | BOOLEAN | Active status |
| `expires_at` | TIMESTAMP | Expiration (null = never) |
| `last_used_at` | TIMESTAMP | Last usage |

---

## Profile Management

### Update Profile
```http
PUT /api/v1/admin/sys/users/{id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "nickname": "New Name",
  "email": "new@example.com",
  "phone": "1234567890",
  "avatar": "https://..."
}
```

### Change Password
```http
PUT /api/v1/admin/sys/users/{id}/password
Authorization: Bearer <token>
Content-Type: application/json

{
  "old_password": "old123",
  "new_password": "new456"
}
```

**Password stored in:** `sys_user_password_history` (prevents reuse)

---

## Session Metrics

Each agent chat session tracks usage:

### `agent_session_metrics`
| Column | Type | Description |
|--------|------|-------------|
| `session_id` | VARCHAR(64) | Chat session ID |
| `user_id` | BIGINT | User |
| `model_name` | VARCHAR(64) | LLM used |
| `credits` | FLOAT | Credits consumed |
| `total_prompt_tokens` | INT | Input tokens |
| `total_completion_tokens` | INT | Output tokens |

---

## Code References

| File | Purpose |
|------|---------|
| [user.py](file:///c:/Users/pault/Documents/3.%20AI%20and%20Machine%20Learning/2.%20Deep%20Learning/1c.%20App/Projects/agents-backend/backend/app/admin/model/user.py) | User model |
| [credits.py](file:///c:/Users/pault/Documents/3.%20AI%20and%20Machine%20Learning/2.%20Deep%20Learning/1c.%20App/Projects/agents-backend/backend/app/agent/api/v1/credits.py) | Credit endpoints |
| [agent_models.py](file:///c:/Users/pault/Documents/3.%20AI%20and%20Machine%20Learning/2.%20Deep%20Learning/1c.%20App/Projects/agents-backend/backend/app/agent/model/agent_models.py) | APIKey, SessionMetrics |
