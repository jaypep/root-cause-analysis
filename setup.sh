#!/usr/bin/env bash
# Root Cause Analysis — Linux/macOS setup script
# Run from the project root: bash setup.sh

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }
info() { echo -e "${CYAN}$*${NC}"; }

prompt_yn() {
    read -rp "$1 [y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]]
}

echo ""
info "=== Root Cause Analysis Setup ==="
echo ""

# ── 1. Find Python 3.12+ ──────────────────────────────────────────────────────
PYTHON=""
for cmd in python3.12 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [[ "$major" -gt 3 ]] || [[ "$major" -eq 3 && "$minor" -ge 12 ]]; then
            PYTHON="$cmd"
            ok "Found Python $ver ($cmd)"
            break
        else
            warn "Found Python $ver but 3.12+ is required."
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo ""
    err "Python 3.12 or newer not found on PATH."
    echo "Install it via your package manager, or download from https://www.python.org/downloads/"
    echo ""
    echo "  macOS:   brew install python@3.12"
    echo "  Ubuntu:  sudo apt install python3.12 python3.12-venv"
    exit 1
fi

# ── 2. Virtual environment ────────────────────────────────────────────────────
if [[ -f "venv/bin/activate" ]]; then
    ok "Virtual environment already exists."
else
    echo ""
    warn "No virtual environment found."
    if prompt_yn "Create one now?"; then
        info "Creating venv..."
        "$PYTHON" -m venv venv
        ok "venv created."
    else
        warn "Skipping venv creation. Dependencies will be installed globally."
    fi
fi

PIP="pip"
UVICORN="uvicorn"
if [[ -f "venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
    PIP="venv/bin/pip"
    UVICORN="venv/bin/uvicorn"
    ok "Virtual environment activated."
fi

# ── 3. Install dependencies ───────────────────────────────────────────────────
echo ""
installed=$("$PIP" freeze 2>/dev/null || true)

if echo "$installed" | grep -qi "fastapi" && \
   echo "$installed" | grep -qi "uvicorn" && \
   echo "$installed" | grep -qi "pydantic"; then
    ok "Dependencies already installed."
else
    warn "Missing one or more dependencies (fastapi, uvicorn, pydantic)."
    if prompt_yn "Install from requirements.txt now?"; then
        info "Installing..."
        "$PIP" install -r requirements.txt
        ok "Dependencies installed."
    else
        warn "Skipping install. The app may not start correctly."
    fi
fi

# ── 4. Start the app ──────────────────────────────────────────────────────────
echo ""
ok "Setup complete."
echo ""

if prompt_yn "Bind to 0.0.0.0 so other devices on your network can connect?"; then
    HOST="0.0.0.0"
    # Print local IP for convenience
    local_ip=""
    if command -v ip &>/dev/null; then
        local_ip=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i=="src") print $(i+1)}' | head -1)
    elif command -v ipconfig &>/dev/null; then
        local_ip=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)
    fi
    if [[ -n "$local_ip" ]]; then
        info "Other devices on your network can connect at: http://${local_ip}:8000"
    fi
else
    HOST="127.0.0.1"
fi

if prompt_yn "Start the app now?"; then
    echo ""
    info "Starting app at http://${HOST}:8000 — press Ctrl+C to stop."
    echo ""
    "$UVICORN" main:app --host "$HOST" --port 8000 --reload
fi
