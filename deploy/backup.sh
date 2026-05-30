#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/alphapilot}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

cd "$APP_DIR"
mkdir -p runtime/backups

STAMP="$(date +"%Y%m%d_%H%M%S")"
TARGET_DIR="runtime/backups/${STAMP}"
mkdir -p "$TARGET_DIR"

if [[ -f "runtime/checkpoints/app.db" ]]; then
  cp "runtime/checkpoints/app.db" "${TARGET_DIR}/app.db"
fi

if [[ -f "runtime/checkpoints/app.db-wal" ]]; then
  cp "runtime/checkpoints/app.db-wal" "${TARGET_DIR}/app.db-wal"
fi

if [[ -d "runtime/data" ]]; then
  tar -czf "${TARGET_DIR}/data.tar.gz" runtime/data
fi

if [[ -d "runtime/rag_data" ]]; then
  tar -czf "${TARGET_DIR}/rag_data.tar.gz" runtime/rag_data
fi

find runtime/backups -mindepth 1 -maxdepth 1 -type d -mtime +"${RETENTION_DAYS}" -exec rm -rf {} +
echo "Backup complete at ${TARGET_DIR}"
