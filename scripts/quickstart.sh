#!/usr/bin/env bash
# AlphaPilot one-click quick start (CLI demo or Docker API).
#
# Usage:
#   bash scripts/quickstart.sh                  # CLI demo: 0700.HK
#   bash scripts/quickstart.sh --demo AAPL      # CLI demo: custom symbol
#   bash scripts/quickstart.sh --docker         # Docker API on :8000
#   bash scripts/quickstart.sh --setup-only     # create .env + pip install only
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ALPHAPILOT_DIR="$REPO_ROOT/alphapilot"
ENV_FILE="$ALPHAPILOT_DIR/.env"
ENV_EXAMPLE="$ALPHAPILOT_DIR/.env.example"
SYMBOL="0700.HK"
MODE="demo"

usage() {
  sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --demo)
      MODE="demo"
      SYMBOL="${2:-0700.HK}"
      shift 2
      ;;
    --docker)
      MODE="docker"
      shift
      ;;
    --setup-only)
      MODE="setup"
      shift
      ;;
    -h|--help)
      usage 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage 1
      ;;
  esac
done

ensure_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "$ENV_EXAMPLE" ]]; then
      cp "$ENV_EXAMPLE" "$ENV_FILE"
      echo "Created $ENV_FILE from .env.example"
    else
      echo "Missing $ENV_FILE — create it with DEEPSEEK_API_KEY and JWT_SECRET" >&2
      exit 1
    fi
  fi

  if ! grep -qE '^DEEPSEEK_API_KEY=.+$' "$ENV_FILE" 2>/dev/null; then
    echo "Edit $ENV_FILE and set DEEPSEEK_API_KEY, then re-run." >&2
    exit 1
  fi
}

ensure_python_deps() {
  echo "Installing Python dependencies..."
  pip install -q -r "$ALPHAPILOT_DIR/requirements.txt"
}

ensure_doc_index() {
  if [[ ! -f "$ALPHAPILOT_DIR/rag_data/faiss_index/index.faiss" ]]; then
    echo "FAISS index not found — running document ingest (first time only)..."
    (cd "$ALPHAPILOT_DIR" && PYTHONPATH=. python ../scripts/reingest_0700.py)
    (cd "$ALPHAPILOT_DIR" && PYTHONPATH=. python ../scripts/prepare_demo_ingest.py --symbol AAPL)
  fi
}

run_demo() {
  ensure_env
  ensure_python_deps
  ensure_doc_index
  echo ""
  echo "=== Running multi-agent pipeline for $SYMBOL (no Web UI) ==="
  (cd "$ALPHAPILOT_DIR" && PYTHONPATH=. python ../scripts/run_analysis_direct.py "$SYMBOL")
}

run_docker() {
  ensure_env
  echo "Starting Docker API (http://localhost:8000)..."
  docker compose -f "$ALPHAPILOT_DIR/docker-compose.yml" up -d --build
  echo ""
  echo "API health: http://localhost:8000/health"
  echo "Web UI is not included in this compose file."
  echo "For the React UI, run in another terminal:"
  echo "  cd frontend && npm install && npm run dev"
  echo "  → http://localhost:5173"
}

case "$MODE" in
  demo) run_demo ;;
  docker) run_docker ;;
  setup)
    ensure_env
    ensure_python_deps
    echo "Setup complete. Run: bash scripts/quickstart.sh --demo $SYMBOL"
    ;;
esac
