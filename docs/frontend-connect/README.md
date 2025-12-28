# Frontend Connection Guide

> Complete documentation for connecting a React/TypeScript frontend to the Agents Backend API.

---

## Overview

This guide covers how to connect your frontend application to the backend APIs for:

| Feature | Documentation | API Prefix |
|---------|---------------|------------|
| **Authentication** | [authentication.md](./authentication.md) | `/api/v1/admin/auth` |
| **OAuth2 Social Login** | [authentication.md](./authentication.md#oauth2-authentication) | `/api/v1/oauth2` |
| **Admin & User Management** | [Admin API](../api-contracts/admin-api.md) | `/api/v1/admin` |
| **MCP Configuration** | [mcp-settings-api.md](./mcp-settings-api.md) | `/api/v1/agent/user-settings` |
| **Sandbox Management** | [sandbox-api.md](./sandbox-api.md) | `/api/v1/agent/sandboxes` |
| **Agent Chat Streaming** | [chat-api.md](./chat-api.md) | `/api/v1/agent/chat` |

---

## API Base URLs

```typescript
// Core API
const API_BASE = "http://localhost:8000/api/v1";

// Agent-specific API
const AGENT_API = "http://localhost:8000/api/v1/agent";

// Auth API
const AUTH_API = "http://localhost:8000/api/v1/admin/auth";

// OAuth2 API
const OAUTH_API = "http://localhost:8000/api/v1/oauth2";
```

---

## Getting Started

### Step 1: Install Dependencies

```bash
npm install axios dayjs sonner react-router-dom
```

### Step 2: Create API Client

```typescript
// lib/api.ts
import axios from 'axios';

export const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  withCredentials: true, // For refresh token cookie
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auto-refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      try {
        const res = await api.post('/admin/auth/token/refresh');
        localStorage.setItem('access_token', res.data.data.access_token);
        error.config.headers.Authorization = `Bearer ${res.data.data.access_token}`;
        return api.request(error.config);
      } catch {
        localStorage.clear();
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);
```

### Step 3: Set Up Authentication

See [authentication.md](./authentication.md) for complete auth implementation including:
- JWT login/logout
- OAuth2 (GitHub, Google)
- Token refresh
- Protected routes

---

## Documentation Index

### Authentication & Users

| Document | Description |
|----------|-------------|
| [Authentication](./authentication.md) | JWT login, OAuth2, token refresh |
| [Admin API](../api-contracts/admin-api.md) | User CRUD, roles, permissions |

### Agent Features

| Document | Description |
|----------|-------------|
| [MCP Settings API](./mcp-settings-api.md) | Configure Codex, Claude Code, custom MCP |
| [Sandbox API](./sandbox-api.md) | Create/manage sandboxes |
| [Chat Streaming API](./chat-api.md) | Agent chat with SSE |

### Infrastructure

| Document | Description |
|----------|-------------|
| [Database Schema](../api-contracts/database.md) | All database tables |
| [Deployment Guide](../deployment/README.md) | Docker, local dev, deployment |

---

## Reference Components

The `components/` directory contains working React/TypeScript examples:

| Component | Purpose |
|-----------|---------|
| [codex-setting.tsx](./components/codex-setting.tsx) | Codex configuration UI |
| [claude-code-setting.tsx](./components/claude-code-setting.tsx) | Claude Code OAuth UI |
| [mcp-setting.tsx](./components/mcp-setting.tsx) | MCP server configuration |
| [tool-setting.tsx](./components/tool-setting.tsx) | Tool management |

---

## Common Patterns

### Error Handling

```typescript
try {
  const response = await api.post('/endpoint', data);
  toast.success('Success!');
  return response.data.data;
} catch (error) {
  if (axios.isAxiosError(error)) {
    const message = error.response?.data?.msg || 'An error occurred';
    toast.error(message);
  }
  throw error;
}
```

### Pagination

```typescript
interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

const { data } = await api.get<{ data: PaginatedResponse<User> }>('/admin/users', {
  params: { page: 1, size: 20 }
});
```

### SSE Streaming

```typescript
const eventSource = new EventSource(
  `${API_BASE}/agent/chat/stream?thread_id=${threadId}`,
  { withCredentials: true }
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle streaming response
};
```

---

## CORS Configuration

The backend needs to allow your frontend origin:

```bash
# Backend .env
AGENT_ALLOWED_ORIGINS='http://localhost:3000,https://your-domain.com'
```

---

## Environment Variables

Frontend environment configuration:

```typescript
// .env.local
REACT_APP_API_URL=http://localhost:8000/api/v1
REACT_APP_OAUTH_CALLBACK=http://localhost:3000/oauth/callback

// Usage
const API_BASE = process.env.REACT_APP_API_URL;
```

---

## Related Documentation

- [Lifecycle Documentation](../lifecycle/README.md) - System flow diagrams
- [Tool Server API](../api-contracts/tool-server.md) - MCP tool reference
