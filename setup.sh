#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command not found: $1" >&2
    exit 1
  fi
}

need git
need node
need npm
need python3

if [[ ! -f vilna-daf/index.html ]]; then
  echo "Initializing the vilna-daf submodule..."
  git submodule update --init --recursive
fi

if [[ ! -f vilna-daf/index.html ]]; then
  echo "vilna-daf is missing. Clone this repository with --recurse-submodules," >&2
  echo "or run: git submodule update --init --recursive" >&2
  exit 1
fi

echo "Installing npm packages..."
npm install

echo "Installing Playwright Chromium..."
npx playwright install chromium

echo "Creating a local Python virtual environment and installing pymupdf..."
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo
echo "Setup is complete. Examples:"
echo "  ./daf-print"
echo "  ./daf-print 2026-11-20"
echo "  ./daf-print 2026-11-17 2026-11-23"
echo "  ./daf-print --daf Bekhorot 60"
