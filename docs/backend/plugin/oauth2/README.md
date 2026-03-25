# OAuth2 Plugin

The `oauth2/` plugin provides third-party OAuth2 authentication for GitHub, Google, and Linux-DO.

---

## Directory Structure

```
oauth2/
├── plugin.toml              # Plugin metadata
├── requirements.txt         # httpx dependency
├── README.md                # Plugin documentation
├── enums.py                 # OAuth provider enums
│
├── api/                     # REST endpoints
│   └── v1/
│       ├── github.py        # GitHub OAuth endpoints
│       ├── google.py        # Google OAuth endpoints
│       └── linux_do.py      # Linux-DO OAuth endpoints
│
├── schema/                  # Pydantic schemas
│   └── oauth.py             # OAuth DTOs
│
├── service/                 # Business logic
│   ├── github.py            # GitHub OAuth service
│   ├── google.py            # Google OAuth service
│   └── linux_do.py          # Linux-DO OAuth service
│
├── crud/                    # Database operations
│   └── oauth.py             # OAuth user binding CRUD
│
└── model/                   # SQLAlchemy models
    └── oauth.py             # OAuth user binding model
```

---

## Supported Providers

| Provider | Authorization URL | Token URL |
|----------|-------------------|-----------|
| GitHub | `github.com/login/oauth/authorize` | `github.com/login/oauth/access_token` |
| Google | `accounts.google.com/o/oauth2/v2/auth` | `oauth2.googleapis.com/token` |
| Linux-DO | `connect.linux.do/oauth2/authorize` | `connect.linux.do/oauth2/token` |

---

## OAuth Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        OAUTH2 FLOW                                   │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────┐
│ 1. Start Authorization│
│ GET /oauth2/{provider}│
│     /authorize        │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ 2. Generate State     │
│ Store in Redis        │
│ (3 min TTL)           │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ 3. Redirect to        │
│ Provider Login Page   │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ 4. User Authorizes    │
│ (on provider site)    │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ 5. Callback           │
│ GET /oauth2/{provider}│
│     /callback         │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ 6. Validate State     │
│ Exchange code → token │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ 7. Get User Info      │
│ from Provider API     │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ 8. Create/Bind User   │
│ Return JWT token      │
└───────────────────────┘
```

---

## API Endpoints

### GitHub

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/oauth2/github/authorize` | GET | Start GitHub OAuth |
| `/api/v1/oauth2/github/callback` | GET | GitHub callback |

### Google

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/oauth2/google/authorize` | GET | Start Google OAuth |
| `/api/v1/oauth2/google/callback` | GET | Google callback |

### Linux-DO

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/oauth2/linux-do/authorize` | GET | Start Linux-DO OAuth |
| `/api/v1/oauth2/linux-do/callback` | GET | Linux-DO callback |

---

## Configuration

| Setting | Description |
|---------|-------------|
| `OAUTH2_GITHUB_CLIENT_ID` | GitHub OAuth app client ID |
| `OAUTH2_GITHUB_CLIENT_SECRET` | GitHub OAuth app secret |
| `OAUTH2_GITHUB_REDIRECT_URI` | GitHub callback URL |
| `OAUTH2_GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `OAUTH2_GOOGLE_CLIENT_SECRET` | Google OAuth secret |
| `OAUTH2_GOOGLE_REDIRECT_URI` | Google callback URL |
| `OAUTH2_LINUX_DO_CLIENT_ID` | Linux-DO OAuth client ID |
| `OAUTH2_LINUX_DO_CLIENT_SECRET` | Linux-DO OAuth secret |
| `OAUTH2_LINUX_DO_REDIRECT_URI` | Linux-DO callback URL |
| `OAUTH2_STATE_REDIS_PREFIX` | State storage prefix |
| `OAUTH2_STATE_EXPIRE_SECONDS` | State TTL (180s) |
| `OAUTH2_FRONTEND_LOGIN_REDIRECT_URI` | Frontend redirect after login |
| `OAUTH2_FRONTEND_BINDING_REDIRECT_URI` | Frontend redirect after binding |

---

## Database Model

```python
class UserSocial(Base):
    """OAuth user binding"""
    __tablename__ = "sys_user_social"
    
    id: Mapped[id_key]
    user_id: Mapped[int]           # Local user ID
    source: Mapped[str]            # Provider name (github/google/linux-do)
    open_id: Mapped[str]           # Provider user ID
    access_token: Mapped[str]      # OAuth access token
    # ...
```

---

*Last Updated: December 2024*
