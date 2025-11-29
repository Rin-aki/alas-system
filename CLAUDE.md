# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ALAS System is a multi-tenant service management platform built with a microservices architecture. It provides user authentication, reverse proxy services, and Docker container management for multiple isolated user environments.

### Technology Stack

**Backend (Python/FastAPI):**
- Authentication Service (`auth_service.py`) - Port 6200
- Proxy Service (`proxy_service.py`) - Port 6300
- Database: MySQL with SQLAlchemy ORM
- JWT-based authentication with HTTP-only cookies
- WebSocket support for real-time container management

**Frontend (Vue 3):**
- Vue 3 with Composition API and `<script setup>`
- Vue Router for navigation
- Element Plus UI framework
- Vite as build tool

### Repository Structure

```
alasm/
├── backend/
│   ├── auth_service.py          # User authentication, registration, IP allocation
│   ├── proxy_service.py         # HTTP/WebSocket reverse proxy
│   ├── requirements-auth.txt    # Auth service dependencies
│   ├── requirements-proxy.txt   # Proxy service dependencies
│   ├── Dockerfile.auth          # Auth service container
│   └── Dockerfile.proxy         # Proxy service container
├── alas-system-frontend/
│   ├── src/
│   │   ├── views/              # Vue pages (Login, Register, Dashboard, Fix)
│   │   ├── router/             # Vue Router configuration
│   │   └── services/api.js     # API client with fetch wrapper
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
└── docker-compose.yml
```

## Development Commands

### Backend Services

**Run Auth Service Locally:**
```bash
cd backend
uvicorn auth_service:app --host 0.0.0.0 --port 6200 --reload
```

**Run Proxy Service Locally:**
```bash
cd backend
python proxy_service.py
# or
uvicorn proxy_service:app --host 0.0.0.0 --port 6300 --reload
```

**Install Backend Dependencies:**
```bash
cd backend
pip install -r requirements-auth.txt  # For auth service
pip install -r requirements-proxy.txt # For proxy service
```

### Frontend

**Development Server:**
```bash
cd alas-system-frontend
npm install
npm run dev  # Runs on 0.0.0.0 (configurable via vite.config.js)
```

**Production Build:**
```bash
cd alas-system-frontend
npm run build
npm run preview
```

### Docker Deployment

**Build and Run All Services:**
```bash
docker-compose up --build
```

**Run Individual Services:**
```bash
docker-compose up auth-service
docker-compose up proxy-service
docker-compose up frontend
```

## Architecture Details

### Multi-Service Architecture

The system uses a microservices approach with three main components:

1. **Auth Service (port 6200):**
   - User registration with automatic IP allocation (range: 10.10.10.30-99)
   - JWT-based authentication with HTTP-only cookies (30min expiry)
   - Purchase/subscription management with expiration tracking
   - WebSocket endpoint `/fix` for Docker container restarts
   - HTTP endpoint `/reconnect` for ws-scrcpy container restart only
   - SSH-based remote Docker container management using `sshpass`

2. **Proxy Service (port 6300):**
   - Reverse proxy for HTTP and WebSocket connections
   - Routes requests to user-specific IPs based on JWT token
   - Supports two service types:
     - `scrcpy` (ws-scrcpy): Routes to `10.10.10.{user.ws_ip}:8000`
     - `alas` (AzurLaneAutoScript): Routes to `10.10.10.{user.alas_ip}:22267`
   - User caching (15min TTL) to reduce database queries
   - Automatic purchase expiration checks on each request
   - Database connection pooling with immediate release after auth

3. **Frontend (port 4173 in production):**
   - Vue 3 SPA with client-side routing
   - Authentication state managed via cookies
   - Route guards check auth status before navigation
   - API base URL: `https://api.gjiang.xyz:58000`

### Database Schema

**User Table:**
- `id` (Integer, Primary Key)
- `email` (String, Unique)
- `password_hash` (String)
- `is_active` (Boolean, default=True)
- `has_purchased` (Boolean, default=False)
- `purchase_expires` (DateTime, nullable)
- `alas_ip` (Integer) - Allocated IP suffix for ALAS service
- `blhx_ip` (Integer) - Allocated IP suffix for BLHX service
- `ws_ip` (Integer) - Allocated IP suffix for ws-scrcpy service
- `server_ip` (Integer) - Target server IP suffix

### IP Allocation Strategy

New users automatically receive 3 sequential IPs from the range 30-99:
- First available IP → `alas_ip`
- Second available IP → `blhx_ip`
- Third available IP → `ws_ip`

The system fills gaps first (e.g., if IPs 31-32 are free, they're used before 98-99).

### Authentication Flow

1. User logs in via `/login` endpoint
2. Backend validates credentials and creates JWT token
3. Token stored in HTTP-only cookie (domain: `.gjiang.xyz`, SameSite=None, Secure)
4. Frontend uses `credentials: 'include'` for all authenticated requests
5. Proxy service validates token and routes to user-specific backend

### Container Management

**Fix Service (`/fix` WebSocket):**
- Restarts all three user containers:
  - `blhx_{user_id}`
  - `alas_{user_id}`
  - `ws-scrcpy_{user_id}`
- Connects to remote server via SSH using `sshpass`
- Provides real-time progress updates via WebSocket

**Reconnect Service (`/reconnect` HTTP POST):**
- Only restarts `ws-scrcpy_{user_id}` container
- Returns JSON response with success/failure status

### CORS Configuration

- Auth service: Restricted to `https://alasm.gjiang.xyz:58000`
- Proxy service: Wildcard origins (`*`) with credentials support
- All services support credentials for cookie-based auth

## Important Notes

### Security Considerations

- **Credentials in Code:** The codebase contains hardcoded database credentials, SSH passwords, and secret keys. These should be moved to environment variables before deploying to production.
- **JWT Secret:** `SECRET_KEY = "lpfH5a3h78"` is shared between auth and proxy services
- **SSH Authentication:** Uses `sshpass` with hardcoded password for remote container management

### Database Connection Management

Both services implement connection pooling and caching strategies:
- **Auth Service:** Basic connection pooling via SQLAlchemy
- **Proxy Service:** Enhanced pooling (pool_size=10, max_overflow=20) with 15min user cache
- WebSocket handlers explicitly release DB connections after authentication

### Purchase Expiration

The proxy service automatically disables `has_purchased` flag when `purchase_expires < current_time`. Users are blocked from accessing proxied services until they renew.

### Frontend API Client

The `apiRequest` helper in `src/services/api.js`:
- Wraps `fetch` with JSON handling
- Requires `credentials: 'include'` for authenticated endpoints
- Returns `{status, data, ok}` structure
