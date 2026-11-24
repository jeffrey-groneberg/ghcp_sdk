#!/usr/bin/env bash
# Runs once after the Codespace or dev container is built: installs the pinned
# SDK from PyPI and downloads its matching Copilot runtime.
set -euo pipefail
cd "$(dirname "$0")/.."

PY="$(command -v python3 || command -v python)"
echo "Using $("$PY" --version 2>&1) at $PY"

"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r requirements.txt

# Optional: the SDK would also download the runtime on first use.
"$PY" -m copilot download-runtime --in-process \
  || echo "Runtime download failed; the SDK retries on first use."

"$PY" -c "import importlib.metadata as m; print('microsoft-copilot-sdk', m.version('microsoft-copilot-sdk'))"

cat <<'MSG'

Microsoft Copilot SDK examples are ready.

Sign-in: in a Codespace the SDK uses the Codespace's GITHUB_TOKEN. Elsewhere,
run `gh auth login` (or set COPILOT_GITHUB_TOKEN). Then try:

  python examples/01_simple_chat.py

All examples: examples/README.md
MSG
