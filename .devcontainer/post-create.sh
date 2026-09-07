#!/usr/bin/env bash
# post-create.sh — runs once after the Codespace is built.
# Installs the Python SDK + example dependencies and prints a welcome message.
set -euo pipefail

cd "$(dirname "$0")/.."

# Use whichever interpreter the base image provides. `python3` is guaranteed
# on every devcontainer image; fall back to `python` just in case.
PY="$(command -v python3 || command -v python)"
echo "Using interpreter: $PY ($("$PY" --version 2>&1))"

echo "── Installing Python dependencies ────────────────────────────"
"$PY" -m pip install --upgrade pip || true
# Install the deps. If the base image marks its Python as externally managed
# (PEP 668), retry with --break-system-packages so the build still succeeds.
"$PY" -m pip install -r requirements.txt \
  || "$PY" -m pip install --break-system-packages -r requirements.txt

echo
echo "── Verifying the Python SDK import ───────────────────────────"
# Importing does not start or download a runtime, or verify authentication.
"$PY" -c "import importlib.metadata as m; from copilot import CopilotClient; print('SDK ready:', m.version('github-copilot-sdk'))"

cat <<'EOF'

============================================================
GitHub Copilot SDK — Examples ready ✅
============================================================
For browser sign-in, install the interactive Copilot CLI separately, then:

  copilot login

Alternatively provision COPILOT_GITHUB_TOKEN securely in your environment.
The Python SDK does not put the interactive copilot command on PATH.
It downloads/caches its release-matched runtime on first use.
To pre-download without making model calls:

  python -m copilot download-runtime

Then run any example (model access/quota and organization policy apply):

  python examples/01_simple_chat.py
  python examples/02_custom_tools.py
  python examples/03_custom_agents.py
  python examples/04_hooks.py
  python examples/05_mcp_servers.py
  python examples/06_session_resume.py
  python examples/07_human_in_the_loop.py

Example 5 uses remote HTTP MCP: no Node/npx or local MCP server is required.
It checks GITHUB_TOKEN, GH_TOKEN, then gh auth token. The token must be
accepted by the hosted MCP server and authorized for the target repository;
an existing Codespaces login alone does not guarantee that access.
============================================================

EOF
