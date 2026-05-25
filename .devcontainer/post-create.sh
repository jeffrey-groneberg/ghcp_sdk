#!/usr/bin/env bash
# post-create.sh — runs once after the Codespace is built.
# Installs the Python SDK + example dependencies and prints a welcome message.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "── Installing Python dependencies ────────────────────────────"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo
echo "── Verifying the bundled Copilot CLI ─────────────────────────"
# The Python SDK bundles the Copilot CLI binary; this confirms it is reachable.
python -c "from copilot import CopilotClient; print('SDK ready:', CopilotClient.__module__)"

cat <<'EOF'

============================================================
GitHub Copilot SDK — Examples ready ✅
============================================================
Sign in to Copilot once (a browser link will appear):

  copilot auth login

Then run any example:

  python examples/01_simple_chat.py
  python examples/02_custom_tools.py
  python examples/03_custom_agents.py
  python examples/04_hooks.py
  python examples/05_mcp_and_persistence.py
  python examples/06_human_in_the_loop.py

Tip: Codespaces already has Node.js + npx installed,
so the filesystem MCP server in example 5 works out of the box.
============================================================

EOF
