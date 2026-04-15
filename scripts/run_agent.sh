#!/bin/bash
# Run AI Agent Runner locally on Mac
# Connects to remote Redis + Postgres (e.g. Oracle VPS Docker, Railway, or other) + MT5 Bridge; uses Kimi (MOONSHOT_API_KEY)
#
# Prerequisites:
#   1. Expose Redis + Postgres to this machine (public host/port or VPN) if not local
#   2. Update backend/.env.local with URLs and MOONSHOT_API_KEY
#
# Usage: ./scripts/run_agent.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"

echo "=== AI Trading Agent — Agent Runner ==="
echo "Starting agent runner on local Mac..."
echo ""

# Check .env.local
if [ ! -f "$BACKEND_DIR/.env.local" ]; then
    echo "ERROR: backend/.env.local not found. Create it first (see template)."
    exit 1
fi

# Check for REPLACE placeholders
if grep -q "REPLACE_WITH" "$BACKEND_DIR/.env.local"; then
    echo "ERROR: backend/.env.local still has REPLACE_WITH placeholders."
    echo "Update Redis/Postgres URLs in backend/.env.local to reachable hosts."
    exit 1
fi

# Load env
set -a
source "$BACKEND_DIR/.env.local"
set +a

if [ -z "${MOONSHOT_API_KEY:-}" ]; then
    echo "ERROR: MOONSHOT_API_KEY not set in backend/.env.local"
    exit 1
fi

# Set Python path
export PYTHONPATH="$BACKEND_DIR:$PROJECT_DIR:$PYTHONPATH"

echo "Runner ID:     $RUNNER_ID"
echo "Agent Mode:    $AGENT_MODE"
echo "Rollout Mode:  $ROLLOUT_MODE"
echo "Redis:         ${REDIS_URL:0:30}..."
echo "MT5 Bridge:    $MT5_BRIDGE_URL"
echo ""

# Run
cd "$BACKEND_DIR"
VENV_PYTHON="$BACKEND_DIR/venv/bin/python"
if [ -f "$VENV_PYTHON" ]; then
    exec "$VENV_PYTHON" -m app.runner.agent_entrypoint
else
    exec python3 -m app.runner.agent_entrypoint
fi
