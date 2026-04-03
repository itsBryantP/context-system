#!/usr/bin/env bash
# install.sh — install ctx with all features (core + extractors)
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/itsBryantP/context-system/main/install.sh | bash
#   — or —
#   bash install.sh          # from a local clone
#   bash install.sh --dev    # also install dev/test dependencies

set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { printf "  ${GREEN}✓${RESET}  %s\n" "$*"; }
warn()    { printf "  ${YELLOW}!${RESET}  %s\n" "$*"; }
error()   { printf "  ${RED}✗${RESET}  %s\n" "$*" >&2; }
heading() { printf "\n${BOLD}%s${RESET}\n" "$*"; }

# ── Argument parsing ──────────────────────────────────────────────────────────

DEV=false
for arg in "$@"; do
  case "$arg" in
    --dev) DEV=true ;;
    --help|-h)
      echo "Usage: bash install.sh [--dev]"
      echo ""
      echo "  --dev   Also install pytest and dev tools"
      exit 0
      ;;
    *)
      error "Unknown argument: $arg"
      exit 1
      ;;
  esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────

require_cmd() {
  if ! command -v "$1" &>/dev/null; then
    return 1
  fi
  return 0
}

python_version_ok() {
  local pybin="$1"
  local major minor
  major=$("$pybin" -c "import sys; print(sys.version_info.major)")
  minor=$("$pybin" -c "import sys; print(sys.version_info.minor)")
  [[ "$major" -ge 3 && "$minor" -ge 11 ]]
}

# ── Banner ────────────────────────────────────────────────────────────────────

heading "ctx — context module system installer"
echo   "  Installing core + all extractors (PDF, PPTX, HTML, Markdown)"
$DEV && echo "  Dev mode: pytest and coverage tools included"

# ── 1. Locate Python 3.11+ ───────────────────────────────────────────────────

heading "1. Checking Python"

PYTHON=""
for candidate in python3 python3.13 python3.12 python3.11 python; do
  if require_cmd "$candidate" && python_version_ok "$candidate"; then
    PYTHON="$candidate"
    break
  fi
done

if [[ -z "$PYTHON" ]]; then
  error "Python 3.11 or higher is required but was not found."
  echo  ""
  echo  "  Install it via your package manager, or from https://python.org"
  echo  "  On macOS:  brew install python@3.12"
  echo  "  On Ubuntu: sudo apt install python3.12"
  exit 1
fi

PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
info "Found Python $PY_VER at $(command -v "$PYTHON")"

# ── 2. Locate or install uv ──────────────────────────────────────────────────

heading "2. Checking uv"

if require_cmd uv; then
  UV_VER=$(uv --version 2>&1 | head -1)
  info "Found $UV_VER"
else
  warn "uv not found — installing via the official installer"
  curl -fsSL https://astral.sh/uv/install.sh | sh

  # Reload PATH for the rest of this script
  export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"

  if ! require_cmd uv; then
    error "uv installation failed. Install manually: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
  fi
  info "uv installed: $(uv --version 2>&1 | head -1)"
fi

# ── 3. Detect install mode ───────────────────────────────────────────────────

heading "3. Detecting install mode"

# Are we inside the cloned repository?
if [[ -f "pyproject.toml" ]] && grep -q 'name = "ctx-modules"' pyproject.toml 2>/dev/null; then
  INSTALL_MODE="local"
  info "Found local clone — installing in editable mode"
else
  INSTALL_MODE="remote"
  info "No local clone detected — installing from PyPI"
fi

# ── 4. Install ctx-modules ───────────────────────────────────────────────────

heading "4. Installing ctx-modules"

EXTRAS="extractors"
$DEV && EXTRAS="extractors,dev"

if [[ "$INSTALL_MODE" == "local" ]]; then
  uv pip install --python "$PYTHON" -e ".[$EXTRAS]"
else
  uv pip install --python "$PYTHON" "ctx-modules[$EXTRAS]"
fi

info "ctx-modules installed with extras: $EXTRAS"

# ── 5. Check for optional system tools ──────────────────────────────────────

heading "5. Optional system dependencies"

# pdftotext (poppler) — primary PDF backend, faster and more accurate
if require_cmd pdftotext; then
  info "pdftotext (poppler) found — PDF extraction: full quality"
else
  warn "pdftotext not found — PDFs will fall back to PyMuPDF (still works)"
  echo  "     Install for best results:"
  echo  "       macOS:  brew install poppler"
  echo  "       Ubuntu: sudo apt install poppler-utils"
fi

# LibreOffice — future .doc/.docx support (optional, not used yet)
if require_cmd soffice; then
  info "LibreOffice found"
fi

# ── 6. Verify installation ───────────────────────────────────────────────────

heading "6. Verifying installation"

if ! require_cmd ctx; then
  # Try to find it in uv's managed location
  CTX_PATH=$(uv run --python "$PYTHON" which ctx 2>/dev/null || true)
  if [[ -n "$CTX_PATH" ]]; then
    warn "ctx is installed but not on PATH. Use 'uv run ctx' or add the following to your shell:"
    UV_BIN_DIR=$(dirname "$CTX_PATH")
    echo  "     export PATH=\"$UV_BIN_DIR:\$PATH\""
  else
    error "ctx command not found after installation — something went wrong."
    exit 1
  fi
else
  CTX_VERSION=$(ctx --version 2>/dev/null || echo "(no --version flag)")
  info "ctx is available at $(command -v ctx)"
fi

# Quick smoke test
if require_cmd ctx; then
  ctx --help > /dev/null 2>&1 && info "ctx --help: OK"
else
  uv run --python "$PYTHON" ctx --help > /dev/null 2>&1 && info "uv run ctx --help: OK"
fi

# ── Done ─────────────────────────────────────────────────────────────────────

heading "Installation complete"
echo  ""
echo  "  Get started:"
echo  "    ctx --help                          # full command reference"
echo  "    ctx pack ./my-docs/                 # pack a directory → JSONL"
echo  "    ctx pack ./my-docs/ -o ./my-module  # pack → module directory"
echo  "    ctx init && ctx create my-module    # start a new module from scratch"
echo  ""

if ! require_cmd ctx 2>/dev/null; then
  echo  "  Note: run commands via 'uv run ctx ...' until you update your PATH."
  echo  ""
fi
