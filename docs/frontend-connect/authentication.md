# Authentication Guide for Frontend

> Complete JWT and OAuth2 authentication for frontend integration.

---

## Overview

The Agents Backend supports multiple authentication methods:

| Method | Use Case | Endpoint Prefix |
|--------|----------|-----------------|
| JWT (Username/Password) | Standard login | `/api/v1/admin/auth` |
| OAuth2 (GitHub) | Social login | `/api/v1/oauth2/github` |
| OAuth2 (Google) | Social login | `/api/v1/oauth2/google` |
| API Key | Agent/M2M access | Header: `X-API-Key` |

---

## JWT Authentication

### Login Flow

```
┌─────────────┐                     ┌─────────────┐                    ┌─────────────┐
│   Frontend  │                     │   Backend   │                    │    Redis    │
└──────┬──────┘                     └──────┬──────┘                    └──────┬──────┘
       │                                   │                                  │
       │  POST /api/v1/admin/auth/login    │                                  │
       │  { username, password }           │                                  │
       │ ─────────────────────────────────►│                                  │
       │                                   │                                  │
       │                                   │  Validate credentials            │
       │                                   │  Generate JWT tokens             │
       │                                   │                                  │
       │                                   │  Store session                   │
       │                                   │ ─────────────────────────────────►
       │                                   │                                  │
       │  { access_token, user }           │                                  │
       │ ◄─────────────────────────────────│                                  │
       │                                   │                                  │
       │  Set refresh_token cookie         │                                  │
       │ ◄─────────────────────────────────│                                  │
       │                                   │                                  │
```

### Login Endpoint

**`POST /api/v1/admin/auth/login`**

**Request:**
```typescript
interface LoginRequest {
  username: string;
  password: string;
  captcha?: string;  // If CAPTCHA enabled
}
```

**Response:**
```typescript
interface LoginResponse {
  code: 200;
  msg: string;
  data: {
    access_token: string;
    access_token_expire_time: string;  // ISO datetime
    session_uuid: string;
    user: {
      id: number;
      uuid: string;
      username: string;
      nickname: string;
      email: string | null;
      avatar: string | null;
      phone: string | null;
      roles: Role[];
      dept: Department | null;
    };
  };
}
```

**Example (React/TypeScript):**
```typescript
import axios from 'axios';

const API_BASE = 'http://localhost:8000/api/v1';

interface LoginCredentials {
  username: string;
  password: string;
}

export async function login(credentials: LoginCredentials) {
  const response = await axios.post(`${API_BASE}/admin/auth/login`, credentials, {
    withCredentials: true,  // Important: receives refresh_token cookie
  });
  
  const { access_token, user } = response.data.data;
  
  // Store access token
  localStorage.setItem('access_token', access_token);
  localStorage.setItem('user', JSON.stringify(user));
  
  return user;
}
```

---

### Using the Access Token

Include the token in all authenticated requests:

```typescript
// Axios interceptor
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

**Or per-request:**
```typescript
const response = await axios.get('/api/v1/agent/sandboxes', {
  headers: {
    Authorization: `Bearer ${accessToken}`,
  },
});
```

---

### Token Refresh

Access tokens expire (default: 30 minutes). Use the refresh token to get a new one.

**`POST /api/v1/admin/auth/token/refresh`**

The refresh token is automatically sent via HTTP-only cookie.

**Response:**
```typescript
interface TokenRefreshResponse {
  code: 200;
  data: {
    access_token: string;
    access_token_expire_time: string;
  };
}
```

**Implementation:**
```typescript
// Axios interceptor for auto-refresh
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      try {
        // Attempt token refresh
        const refreshResponse = await axios.post(
          `${API_BASE}/admin/auth/token/refresh`,
          {},
          { withCredentials: true }
        );
        
        const newToken = refreshResponse.data.data.access_token;
        localStorage.setItem('access_token', newToken);
        
        // Retry original request
        error.config.headers.Authorization = `Bearer ${newToken}`;
        return axios.request(error.config);
      } catch (refreshError) {
        // Refresh failed, redirect to login
        localStorage.clear();
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);
```

---

### Logout

**`POST /api/v1/admin/auth/logout`**

```typescript
export async function logout() {
  await axios.post(`${API_BASE}/admin/auth/logout`, {}, {
    withCredentials: true,
  });
  
  localStorage.removeItem('access_token');
  localStorage.removeItem('user');
}
```

---

## OAuth2 Authentication

### Supported Providers

| Provider | Get URL | Callback |
|----------|---------|----------|
| GitHub | `GET /api/v1/oauth2/github` | `GET /api/v1/oauth2/github/callback` |
| Google | `GET /api/v1/oauth2/google` | `GET /api/v1/oauth2/google/callback` |
| LinuxDo | `GET /api/v1/oauth2/linux-do` | `GET /api/v1/oauth2/linux-do/callback` |

### OAuth2 Login Flow

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Frontend  │       │   Backend   │       │   GitHub    │       │   Redis     │
└──────┬──────┘       └──────┬──────┘       └──────┬──────┘       └──────┬──────┘
       │                     │                     │                     │
       │ GET /oauth2/github  │                     │                     │
       │ ───────────────────►│                     │                     │
       │                     │                     │                     │
       │                     │ Generate state      │                     │
       │                     │ Store in Redis      │                     │
       │                     │ ─────────────────────────────────────────►│
       │                     │                     │                     │
       │ { authorization_url }                     │                     │
       │ ◄───────────────────│                     │                     │
       │                     │                     │                     │
       │ Redirect user       │                     │                     │
       │ ══════════════════════════════════════════►                     │
       │                     │                     │                     │
       │                     │    User authorizes  │                     │
       │                     │ ◄═══════════════════                     │
       │                     │                     │                     │
       │                     │ Callback with code  │                     │
       │ ◄═══════════════════│                     │                     │
       │                     │                     │                     │
       │ Redirect with token │                     │                     │
       │ ◄═══════════════════│                     │                     │
```

### GitHub OAuth2

**Step 1: Get Authorization URL**

```typescript
// Frontend initiates OAuth
async function loginWithGitHub() {
  const response = await axios.get(`${API_BASE}/oauth2/github`);
  const { data: authUrl } = response.data;
  
  // Redirect to GitHub
  window.location.href = authUrl;
}
```

**Step 2: Handle Callback**

After GitHub authorization, user is redirected to:
```
https://your-frontend.com/oauth/callback?access_token=xxx&session_uuid=xxx
```

Configure this URL in your `.env`:
```bash
OAUTH2_FRONTEND_LOGIN_REDIRECT_URI=http://localhost:3000/oauth/callback
OAUTH2_FRONTEND_BINDING_REDIRECT_URI=http://localhost:3000/settings/social
```

**Step 3: Process Token**

```typescript
// In your OAuth callback page component
import { useSearchParams, useNavigate } from 'react-router-dom';

function OAuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  
  useEffect(() => {
    const accessToken = searchParams.get('access_token');
    const sessionUuid = searchParams.get('session_uuid');
    
    if (accessToken) {
      localStorage.setItem('access_token', accessToken);
      
      // Fetch user info
      fetchUserInfo().then((user) => {
        localStorage.setItem('user', JSON.stringify(user));
        navigate('/dashboard');
      });
    }
  }, []);
  
  return <div>Processing login...</div>;
}

async function fetchUserInfo() {
  const response = await axios.get(`${API_BASE}/admin/users/me`);
  return response.data.data;
}
```

### Google OAuth2

Same flow as GitHub:

```typescript
async function loginWithGoogle() {
  const response = await axios.get(`${API_BASE}/oauth2/google`);
  window.location.href = response.data.data;
}
```

---

## Account Binding

Link social accounts to existing user:

```typescript
// Get binding URL
async function bindGitHub() {
  const response = await axios.get(`${API_BASE}/oauth2/user-social/github/bind`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  window.location.href = response.data.data;
}

// Get linked accounts
async function getLinkedAccounts() {
  const response = await axios.get(`${API_BASE}/oauth2/user-social/list`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  return response.data.data;
}

// Unlink account
async function unlinkAccount(socialId: number) {
  await axios.delete(`${API_BASE}/oauth2/user-social/${socialId}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
}
```

---

## User Registration

**`POST /api/v1/admin/auth/register`**

```typescript
interface RegisterRequest {
  username: string;
  password: string;
  nickname?: string;
  email?: string;
  captcha?: string;
}
```

**Example:**
```typescript
async function register(data: RegisterRequest) {
  const response = await axios.post(`${API_BASE}/admin/auth/register`, data);
  return response.data.data;
}
```

---

## Protected Routes (Frontend)

**React Router Example:**
```typescript
import { Navigate, Outlet } from 'react-router-dom';

function ProtectedRoute() {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  
  return <Outlet />;
}

// Usage
<Routes>
  <Route path="/login" element={<Login />} />
  <Route path="/oauth/callback" element={<OAuthCallback />} />
  
  <Route element={<ProtectedRoute />}>
    <Route path="/dashboard" element={<Dashboard />} />
    <Route path="/agents" element={<Agents />} />
    <Route path="/settings" element={<Settings />} />
  </Route>
</Routes>
```

---

## API Key Authentication

For programmatic access (M2M, CLI):

**Create API Key:**
```typescript
const response = await axios.post(`${API_BASE}/admin/users/api-key`, {}, {
  headers: { Authorization: `Bearer ${getToken()}` },
});
const apiKey = response.data.data.api_key;
```

**Use API Key:**
```typescript
const response = await axios.get(`${API_BASE}/agent/sandboxes`, {
  headers: { 'X-API-Key': apiKey },
});
```

---

## CORS Configuration

The backend allows these origins (configure in `.env`):

```bash
AGENT_ALLOWED_ORIGINS='http://localhost:3000,https://your-domain.com'
```

---

## Session Management

### Get Current Session
```typescript
const response = await axios.get(`${API_BASE}/admin/auth/session`);
const session = response.data.data;
```

### List Active Sessions
```typescript
const response = await axios.get(`${API_BASE}/admin/users/sessions`);
const sessions = response.data.data;
```

### Revoke Session
```typescript
await axios.delete(`${API_BASE}/admin/users/sessions/${sessionUuid}`);
```

---

## Error Handling

| HTTP Code | Meaning | Action |
|-----------|---------|--------|
| 401 | Token expired/invalid | Refresh or redirect to login |
| 403 | Permission denied | Show error, don't retry |
| 422 | Validation error | Show field errors |
| 429 | Rate limited | Wait and retry |

**Example:**
```typescript
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized
    } else if (error.response?.status === 403) {
      alert('Permission denied');
    } else if (error.response?.status === 422) {
      const errors = error.response.data.detail;
      // Display validation errors
    }
    return Promise.reject(error);
  }
);
```

---

## Environment Configuration

Frontend should set these:

```typescript
// config.ts
export const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';
export const OAUTH_CALLBACK_URL = process.env.REACT_APP_OAUTH_CALLBACK || 'http://localhost:3000/oauth/callback';
```

---

## Complete Example: Auth Context

```typescript
// AuthContext.tsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

interface User {
  id: number;
  username: string;
  nickname: string;
  email: string | null;
  avatar: string | null;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  loginWithGitHub: () => void;
  loginWithGoogle: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  
  useEffect(() => {
    // Check for existing session
    const token = localStorage.getItem('access_token');
    if (token) {
      fetchUser().catch(() => {
        localStorage.clear();
      });
    } else {
      setIsLoading(false);
    }
  }, []);
  
  async function fetchUser() {
    try {
      const response = await axios.get('/api/v1/admin/users/me');
      setUser(response.data.data);
    } finally {
      setIsLoading(false);
    }
  }
  
  async function login(username: string, password: string) {
    const response = await axios.post('/api/v1/admin/auth/login', {
      username,
      password,
    }, { withCredentials: true });
    
    const { access_token, user } = response.data.data;
    localStorage.setItem('access_token', access_token);
    setUser(user);
  }
  
  function loginWithGitHub() {
    axios.get('/api/v1/oauth2/github').then((res) => {
      window.location.href = res.data.data;
    });
  }
  
  function loginWithGoogle() {
    axios.get('/api/v1/oauth2/google').then((res) => {
      window.location.href = res.data.data;
    });
  }
  
  async function logout() {
    await axios.post('/api/v1/admin/auth/logout', {}, { withCredentials: true });
    localStorage.clear();
    setUser(null);
  }
  
  return (
    <AuthContext.Provider value={{ user, isLoading, login, loginWithGitHub, loginWithGoogle, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
```
