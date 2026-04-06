# Environment Profiles

This project now has separate compose files for development and production.

## Development

1. Copy variables:

```bash
cp .env.dev.example .env.dev
```

2. Start:

```bash
docker compose --env-file .env.dev -f docker-compose.dev.yml up -d --build
```

## Production

1. Copy variables:

```bash
cp .env.prod.example .env.prod
```

2. Edit `.env.prod` with real secrets and URLs.

3. Start:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

## systemd Auto Start

`deploy/alas-system.service` is configured for production profile:

- `COMPOSE_FILE=docker-compose.prod.yml`
- `EnvironmentFile=/opt/alas-system/.env.prod`

Install/update service:

```bash
sudo cp /opt/alas-system/deploy/alas-system.service /etc/systemd/system/alas-system.service
sudo systemctl daemon-reload
sudo systemctl enable alas-system.service
sudo systemctl restart alas-system.service
```

## Logs

```bash
journalctl -u alas-system.service -n 200 --no-pager
```
