#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/alphapilot}"
GIT_REPO="${GIT_REPO:-}"
GIT_BRANCH="${GIT_BRANCH:-main}"

if [[ -z "${BACKEND_IMAGE:-}" || -z "${FRONTEND_IMAGE:-}" ]]; then
  echo "BACKEND_IMAGE and FRONTEND_IMAGE are required"
  exit 1
fi

if [[ ! -d "$APP_DIR" ]]; then
  if [[ -z "$GIT_REPO" ]]; then
    echo "APP_DIR does not exist and GIT_REPO is not provided"
    exit 1
  fi
  git clone "$GIT_REPO" "$APP_DIR"
fi

cd "$APP_DIR"
git fetch origin "$GIT_BRANCH"
git checkout "$GIT_BRANCH"
git reset --hard "origin/$GIT_BRANCH"

mkdir -p runtime/rag_data runtime/data runtime/checkpoints runtime/hf_cache runtime/backups

if [[ -n "${PROD_ENV_CONTENT:-}" ]]; then
  printf "%s" "$PROD_ENV_CONTENT" > .env.prod
fi

if [[ ! -f ".env.prod" ]]; then
  echo ".env.prod not found and PROD_ENV_CONTENT not provided"
  exit 1
fi

PREV_BACKEND_IMAGE="$(docker inspect -f '{{.Config.Image}}' alphapilot-api 2>/dev/null || true)"
PREV_FRONTEND_IMAGE="$(docker inspect -f '{{.Config.Image}}' alphapilot-web 2>/dev/null || true)"

export BACKEND_IMAGE
export FRONTEND_IMAGE
docker compose -f deploy/docker-compose.prod.yml pull
docker compose -f deploy/docker-compose.prod.yml up -d --remove-orphans

echo "Waiting for /health..."
if ! timeout 120 bash -c 'until curl -fsS http://localhost/health >/dev/null; do sleep 3; done'; then
  echo "Health check failed, rolling back..."
  if [[ -n "$PREV_BACKEND_IMAGE" && -n "$PREV_FRONTEND_IMAGE" ]]; then
    export BACKEND_IMAGE="$PREV_BACKEND_IMAGE"
    export FRONTEND_IMAGE="$PREV_FRONTEND_IMAGE"
    docker compose -f deploy/docker-compose.prod.yml up -d --remove-orphans
  fi
  exit 1
fi

echo "Deployment successful"
