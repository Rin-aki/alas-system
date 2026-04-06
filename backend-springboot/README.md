# backend-springboot

Spring Boot replacement for the original `backend/auth_service.py`.

## Current migration scope

Implemented endpoints:

- `POST /register`
- `POST /login`
- `POST /purchase`
- `GET /purchase/status`
- `GET /auth/check`
- `POST /logout`
- `GET /user/info`
- `POST /reconnect`
- `GET /health`
- `POST /admin/login`
- `POST /admin/logout`
- `GET /admin/check`
- `GET /announcement/latest`
- `POST /admin/announcement`
- `GET /system/status`
- `POST /admin/maintenance`

## Not migrated yet

- `WebSocket /fix`

## Run locally

```bash
cd backend-springboot
mvn spring-boot:run
```

## Build image

```bash
docker compose build auth-service
```
