# Email Plugin

The `email/` plugin provides SMTP email sending capabilities.

---

## Directory Structure

```
email/
├── plugin.toml              # Plugin metadata
├── api/                     # REST endpoints
├── schema/                  # Email schemas
├── service/                 # Email service
├── crud/                    # Email log CRUD
└── model/                   # Email log model
```

---

## Features

- **SMTP Sending**: Send emails via configurable SMTP server
- **Email Captcha**: Send verification codes
- **Template Support**: HTML email templates
- **Logging**: Track sent emails

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/email/send` | POST | Send email |
| `/api/v1/email/captcha` | POST | Send captcha code |
| `/api/v1/email/verify` | POST | Verify captcha |

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `EMAIL_HOST` | `smtp.qq.com` | SMTP server host |
| `EMAIL_PORT` | `465` | SMTP server port |
| `EMAIL_SSL` | `True` | Use SSL encryption |
| `EMAIL_USERNAME` | - | SMTP username |
| `EMAIL_PASSWORD` | - | SMTP password/app key |
| `EMAIL_CAPTCHA_REDIS_PREFIX` | `fba:email:captcha` | Captcha Redis prefix |
| `EMAIL_CAPTCHA_EXPIRE_SECONDS` | `180` | Captcha TTL (3 min) |

---

## Usage Example

```python
from backend.plugin.email.service import email_service

# Send email
await email_service.send(
    to="user@example.com",
    subject="Welcome",
    body="<h1>Welcome to our platform!</h1>",
    html=True
)

# Send captcha
await email_service.send_captcha("user@example.com")
```

---

*Last Updated: December 2024*
