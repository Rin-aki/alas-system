# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ALAS System is a multi-tenant service management platform. It provides user authentication, reverse proxy services, and Docker container management for isolated per-user environments running AzurLaneAutoScript (ALAS) and ws-scrcpy.

## Technology Stack

- **Auth Service** (`backend-springboot/`) — Spring Boot 3, Java, JPA/Hibernate, MySQL, port 6200
- **Proxy Service** (`backend/proxy_service.py`) — Python/FastAPI, port 6300
- **Frontend** (`alas-system-frontend/`) — Vue 3 (Composition API, `<script setup>`), Element Plus, Vite, port 4173

The original Python auth service (`backend/auth_service.py`) has been removed. All endpoints including the `/fix` WebSocket are now served by the Spring Boot service.

## Development Commands

### Auth Service (Spring Boot)
```bash
cd backend-springboot
mvn spring-boot:run          # Runs on port 6200
```

### Proxy Service (Python)
```bash
cd backend
pip install -r requirements-proxy.txt
uvicorn proxy_service:app --host 0.0.0.0 --port 6300 --reload
```

### Frontend
```bash
cd alas-system-frontend
npm install
npm run dev      # Dev server on 0.0.0.0
npm run build    # Production build (bakes VITE_* env vars at compile time)
```

## Docker Deployment

The project has separate compose files for each environment. All config is supplied via an env file — never hardcoded in compose files (prod).

```bash
# Development
cp .env.dev.example .env.dev
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d --build

# Production
cp .env.prod.example .env.prod
# Edit .env.prod — fill in secrets, real URLs, COOKIE_DOMAIN, JWT secrets
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

The `scripts/start-with-update.sh` script is used in production: it pulls the latest git revision only when the working tree is clean, then rebuilds if new commits are present.

### systemd (production)
```bash
sudo cp deploy/alas-system.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now alas-system.service
journalctl -u alas-system.service -n 200 --no-pager
```

## Architecture

### Service Responsibilities

**Auth Service (Spring Boot, port 6200):**
- User registration with automatic IP allocation (range `10.10.10.30–99`; each user gets three sequential IPs for `alas_ip`, `blhx_ip`, `ws_ip`)
- Two independent JWT flows: user token (`access_token` cookie, 30 min) and admin token (`admin_token` cookie, 60 min), each with separate secrets
- Purchase/subscription management; `ExpirationScheduler` runs hourly to auto-disable expired users
- Announcements and maintenance mode (`SystemStatus` table, id=1 is the singleton row)
- `/reconnect` HTTP endpoint — restarts only `ws-scrcpy_{user_id}` via SSH
- `/fix` WebSocket — restarts user's `blhx_{id}` and `alas_{id}` containers via SSH, implemented in `FixWebSocketHandler.java`
- **Stripe payment** — `GET /payment/plans`, `POST /payment/create-session`, `GET /payment/verify`, `POST /payment/webhook`; orders recorded in `stripe_order` table; webhook activates user purchase on `checkout.session.completed`

**Proxy Service (Python, port 6300):**
- Reverse proxy for HTTP and WebSocket traffic, routes to per-user IPs
  - `scrcpy` path → `10.10.10.{user.ws_ip}:8000`
  - `alas` path → `10.10.10.{user.alas_ip}:22267`
- Reads the JWT from `access_token` cookie to resolve the target user; validates purchase expiry on every request
- 15-minute in-process user cache to reduce DB queries; cache is cleared on expiry

**Frontend (Vue 3, port 4173):**
- Routes: `/login`, `/register`, `/dashboard`, `/fix`, `/device`, `/checkout`, `/checkout/success`, `/admin-login`, `/admin`
- `router/index.js` global guard: user routes call `userService.isAuthenticated()` → `/auth/check`; admin routes call `adminService.isAuthenticated()` → `/admin/check`
- All service URLs (`VITE_API_BASE_URL`, `VITE_WS_FIX_URL`, `VITE_SCRCPY_BASE_URL`, `VITE_ALAS_BASE_URL`) are injected at build time as Vite env vars — changing them requires a rebuild

### Spring Boot Package Layout

```
backend-springboot/src/main/java/com/alas/system/
├── controller/   AuthController.java, AdminController.java, PaymentController.java, ApiExceptionHandler.java
├── service/      UserService.java, AdminService.java, ReconnectService.java, ExpirationScheduler.java, PaymentService.java
├── repository/   UserRepository, AnnouncementRepository, SystemStatusRepository, StripeOrderRepository (Spring Data JPA)
├── domain/       User, Announcement, SystemStatus, StripeOrder
├── security/     JwtService.java, CookieFactory.java, PasswordService.java
└── config/       CorsConfig.java
```

### Authentication Flow

1. User/admin POSTs credentials → backend returns JWT in an HTTP-only cookie
2. Cookie attributes are driven by env vars: `COOKIE_DOMAIN` and `COOKIE_SECURE` (set `COOKIE_DOMAIN=` empty and `COOKIE_SECURE=false` for local dev without HTTPS)
3. Frontend sends `credentials: 'include'` on every request
4. Proxy service reads `access_token` cookie to route requests

### Key Environment Variables

| Variable | Used by | Purpose |
|---|---|---|
| `DB_URL`, `DB_USER`, `DB_PASSWORD` | auth-service | MySQL connection |
| `PROXY_DATABASE_URL` | proxy-service | MySQL connection (SQLAlchemy URL) |
| `USER_JWT_SECRET`, `ADMIN_JWT_SECRET` | auth-service | Separate signing keys |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | auth-service | Admin credentials |
| `COOKIE_DOMAIN`, `COOKIE_SECURE` | auth-service | Cookie scope |
| `CORS_ALLOWED_ORIGIN_PATTERNS` | auth-service | CORS origins |
| `VITE_API_BASE_URL`, `VITE_WS_FIX_URL`, `VITE_SCRCPY_BASE_URL`, `VITE_ALAS_BASE_URL` | frontend (build) | Baked-in API endpoints |
| `STRIPE_SECRET_KEY` | auth-service | Stripe secret key (`sk_live_…` / `sk_test_…`) |
| `STRIPE_WEBHOOK_SECRET` | auth-service | Stripe webhook signing secret (`whsec_…`) |
| `FRONTEND_URL` | auth-service | Base URL for Stripe success/cancel redirects (e.g. `https://alasm.gjiang.xyz:58000`) |

### Stripe Payment Flow

1. User visits `/checkout`, selects a plan (30/90/180/365 天，CNY)
2. Frontend calls `POST /payment/create-session` → backend creates a Stripe Checkout Session and returns its `url`
3. Frontend redirects to Stripe-hosted payment page (`window.location.href = url`)
4. On success Stripe redirects to `/checkout/success?session_id=…`; the page polls `GET /payment/verify` up to 5 times to wait for webhook delivery
5. Stripe fires `checkout.session.completed` → `POST /payment/webhook`; `PaymentService.fulfillOrder()` marks the `StripeOrder` as `paid` and extends `user.purchase_expires`

**Stripe plans** (defined in `PaymentService.PLANS`, amounts in fen):

| Plan ID | Days | Amount |
|---|---|---|
| `plan_30d` | 30 | ¥38 |
| `plan_90d` | 90 | ¥110 |
| `plan_180d` | 180 | ¥215 |
| `plan_365d` | 365 | ¥418 |

**Database table:** `stripe_order` — must be created manually via `backend-springboot/src/main/resources/db/migration/V2__stripe_order.sql` (project uses `ddl-auto: none`).

**Webhook registration:** in Stripe Dashboard, register `https://api.gjiang.xyz:58000/payment/webhook` for event `checkout.session.completed`.

### Timezone

All services run `TZ=Asia/Shanghai` (set in compose files). This affects purchase expiry comparisons and scheduler timing. When running locally without Docker, set `TZ=Asia/Shanghai` in the shell.
