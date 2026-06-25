#!/bin/bash
##############################################################################
#
#   restart-api.sh — Restart the AgentOS API server
#
#   Use this when you add a brand-new agent file or make changes that
#   hot-reload can't pick up (new module imports, new dependencies, etc.).
#
#   Hot-reload (--reload) handles edits to existing files automatically:
#     - Tweaking agent instructions
#     - Changing tool definitions
#     - Updating config.yaml prompts
#     - Editing any file in agents/ or app/
#
#   But a full restart is needed when you:
#     - Add a new agent file (e.g., agents/my_agent.py)
#     - Register a new agent/team in app/main.py's agents=[...] list
#     - Add a new Python dependency to requirements.txt
#     - Change db/session.py or other shared modules outside agents/ and app/
#
#   Usage:
#       ./scripts/restart-api.sh          # restart and wait for ready
#       ./scripts/restart-api.sh -q       # restart quietly (minimal output)
#
##############################################################################

set -e

QUIET=false
if [ "$1" = "-q" ]; then
    QUIET=true
fi

log() {
    if [ "$QUIET" = false ]; then echo "$1"; fi
}

# Must run from /app
cd /app

# Ensure PostgreSQL is running (in-container, data on persistent volume)
export PGDATA=/app/data/pgdata
if ! su postgres -c "pg_isready -q" 2>/dev/null; then
    log "🔄 Starting PostgreSQL..."
    su postgres -c "pg_ctl -D '$PGDATA' start -w -l /tmp/pg.log" 2>/dev/null || true
    until su postgres -c "pg_isready -q" 2>/dev/null; do sleep 1; done
    log "✅ PostgreSQL is ready."
fi

# Find the running uvicorn process (match the app module, not this script)
UVICORN_PID=$(pgrep -f "uvicorn app.main:app" || true)

if [ -z "$UVICORN_PID" ]; then
    log "⚠️  AgentOS API is not running. Starting it fresh..."
else
    log "🔄 Stopping AgentOS API (PID: $UVICORN_PID)..."
    kill "$UVICORN_PID" 2>/dev/null || true
    # Wait for the process to fully stop
    sleep 2
    # Force kill if still running
    kill -9 "$UVICORN_PID" 2>/dev/null || true
    sleep 1
fi

log "🚀 Starting AgentOS API on port 8000 (with hot-reload)..."
nohup uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --reload-dir agents \
    --reload-dir app \
    > /tmp/agentos.log 2>&1 &

NEW_PID=$!
log "   PID: $NEW_PID"
log "   Logs: /tmp/agentos.log  (tail -f /tmp/agentos.log)"

# Wait for the API to be ready
log "⏳ Waiting for API to be ready..."
ATTEMPTS=0
MAX_ATTEMPTS=30
until curl -s http://localhost:8000/ > /dev/null 2>&1; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
        echo "❌ AgentOS API failed to start within 30 seconds."
        echo "   Check the logs: tail -50 /tmp/agentos.log"
        exit 1
    fi
    sleep 1
done

log "✅ AgentOS API is ready at http://localhost:8000"
log "   Refresh your browser to see any new agents."