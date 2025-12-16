# Internationalization (i18n)

The `locale/` directory contains translation files for multi-language support.

---

## Directory Structure

```
locale/
├── en-US.json               # English translations
└── zh-CN.yml                # Chinese translations (default)
```

---

## Translation Format

### JSON Format (en-US.json)

```json
{
  "common": {
    "success": "Success",
    "error": "Error",
    "not_found": "Not found"
  },
  "user": {
    "login_success": "Login successful",
    "logout_success": "Logout successful",
    "invalid_credentials": "Invalid username or password"
  },
  "validation": {
    "required": "This field is required",
    "email": "Invalid email format"
  }
}
```

### YAML Format (zh-CN.yml)

```yaml
common:
  success: 成功
  error: 错误
  not_found: 未找到

user:
  login_success: 登录成功
  logout_success: 登出成功
  invalid_credentials: 用户名或密码无效

validation:
  required: 此字段必填
  email: 邮箱格式无效
```

---

## Usage

### In Code

```python
from backend.common.i18n import _

# Get translated string
message = _("user.login_success")
# Returns: "Login successful" (en-US) or "登录成功" (zh-CN)
```

### Language Detection

Language is detected in this order:
1. `Accept-Language` header
2. `lang` query parameter
3. Default: `zh-CN` (from settings)

```python
# Request with Accept-Language: en-US
# Will use en-US.json translations
```

---

## Configuration

```python
# In conf.py
I18N_DEFAULT_LANGUAGE = "zh-CN"
```

---

## Adding New Languages

1. Create new translation file: `locale/fr-FR.json`
2. Add all translation keys
3. Restart application

---

*Last Updated: December 2024*
