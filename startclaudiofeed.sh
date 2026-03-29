#!/usr/bin/env bash
# startclaudiofeed.sh — set up and launch the Claudio Daily Report server
set -euo pipefail

# ── Helpers ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[claudio]${NC} $*"; }
warn()  { echo -e "${YELLOW}[claudio]${NC} $*"; }
error() { echo -e "${RED}[claudio]${NC} $*" >&2; }

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"
PORT="${PORT:-8765}"

# ── 1. Load .env if present ──────────────────────────────────────────────────
if [[ -f "$REPO_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO_DIR/.env"
  set +a
  info "Loaded .env"
fi

# ── 2. Check Python 3.10+ ────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  error "python3 not found. Please install Python 3.10 or later."
  exit 1
fi

PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
PY_VERSION="$PY_MAJOR.$PY_MINOR"

if [[ "$PY_MAJOR" -lt 3 || ( "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 10 ) ]]; then
  error "Python 3.10+ required (found $PY_VERSION)."
  exit 1
fi

info "Python $PY_VERSION ✓"

# ── 3. Create virtual environment if needed ───────────────────────────────────
if [[ ! -d "$VENV_DIR" ]]; then
  info "Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
  info "Virtual environment created ✓"
else
  info "Virtual environment found ✓"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ── 4. Install / sync dependencies ───────────────────────────────────────────
info "Checking dependencies..."
pip install -q -r "$REPO_DIR/requirements.txt"
info "Dependencies ready ✓"

# ── 5. Warn if API key is missing ────────────────────────────────────────────
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  warn "ANTHROPIC_API_KEY is not set — feed updates will fail."
  warn "Add it to a .env file in this directory:"
  warn "  echo 'ANTHROPIC_API_KEY=sk-...' >> .env"
fi

# ── 6. Open browser after server is ready ────────────────────────────────────
open_browser() {
  local url="$1"
  if command -v open &>/dev/null; then        # macOS
    open "$url"
  elif command -v xdg-open &>/dev/null; then  # Linux
    xdg-open "$url"
  fi
}
(sleep 1.5 && open_browser "http://localhost:$PORT") &

# ── 7. Start server ──────────────────────────────────────────────────────────
info "Starting server at http://localhost:$PORT"
info "Press Ctrl+C to stop"
cd "$REPO_DIR"
exec python3 src/server.py
