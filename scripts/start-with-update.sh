#!/usr/bin/env bash
set -euo pipefail

BRANCH="${BRANCH:-main}"
REMOTE="${REMOTE:-origin}"
REPO_DIR="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

COMPOSE_CMD=(docker compose -f "$COMPOSE_FILE")

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

cd "$REPO_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  log "ERROR: $REPO_DIR is not a git repository."
  exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  log "ERROR: compose file not found: $COMPOSE_FILE"
  exit 1
fi

log "INFO: Using compose file: $COMPOSE_FILE"

if ! git diff --quiet || ! git diff --cached --quiet; then
  log "WARN: Working tree has local changes. Skip auto-pull for safety."
  log "INFO: Continue startup with current local code."
  "${COMPOSE_CMD[@]}" up -d
  exit 0
fi

current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$current_branch" != "$BRANCH" ]]; then
  log "INFO: Switching branch from $current_branch to $BRANCH"
  git checkout "$BRANCH"
fi

log "INFO: Fetching $REMOTE/$BRANCH..."
git fetch "$REMOTE" "$BRANCH" --quiet

local_sha="$(git rev-parse "$BRANCH")"
remote_sha="$(git rev-parse "$REMOTE/$BRANCH")"

if [[ "$local_sha" != "$remote_sha" ]]; then
  log "INFO: New version detected on $REMOTE/$BRANCH. Pulling latest code..."
  git pull --ff-only "$REMOTE" "$BRANCH"
  log "INFO: Rebuilding and starting containers..."
  "${COMPOSE_CMD[@]}" up -d --build --remove-orphans
else
  log "INFO: No new version on $REMOTE/$BRANCH. Starting containers normally..."
  "${COMPOSE_CMD[@]}" up -d
fi

log "INFO: Startup completed."
