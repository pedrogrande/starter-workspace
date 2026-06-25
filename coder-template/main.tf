terraform {
  required_providers {
    coder = {
      source  = "coder/coder"
      version = "~> 2.0"
    }
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "coder" {}

# Connect to the Docker daemon on the VPS host
provider "docker" {}

data "coder_workspace" "me" {}
data "coder_workspace_owner" "me" {}

# ---------------------------------------------------------------------------
# API keys — passed via -var or .tfvars at template push time.
# Keys are NOT stored in this file (public repo). Use a .tfvars file on the
# ---------------------------------------------------------------------------
# API keys — read from TF_VAR_* environment variables on the VPS.
#
# Set these once in the Coder provisioner's environment (e.g. /etc/coder/coder.env
# on the VPS):
#
#   TF_VAR_openai_api_key=sk-...
#   TF_VAR_ollama_api_key=ollama-...
#
# Terraform automatically picks up TF_VAR_<name> as the value for variable <name>.
# Keys are never stored in this file (public repo), never appear in the Coder
# dashboard, and are marked sensitive so they don't show in Terraform output.
#
# After setting the env vars, restart the Coder server:
#   systemctl restart coder
#
# Then push the template (no --var flags needed):
#   echo yes | coder templates push agentos-course --directory .
# ---------------------------------------------------------------------------

variable "openai_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "ollama_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

# ---------------------------------------------------------------------------
# Persistent data volume — survives workspace stop/start
# Critical: declared WITHOUT count so it persists across stop/start cycles.
# Mounted at /app/data (a subdirectory) so it doesn't shadow the git-cloned
# repo at /app.
# ---------------------------------------------------------------------------

resource "docker_volume" "workspace_data" {
  name = "student-${data.coder_workspace_owner.me.name}-data"
}

# ---------------------------------------------------------------------------
# Workspace container — single container, no Postgres, no DinD
# ---------------------------------------------------------------------------

resource "docker_container" "workspace" {
  count = data.coder_workspace.me.start_count
  name  = "student-${data.coder_workspace_owner.me.name}-${data.coder_workspace.me.name}"
  image = "ghcr.io/pedrogrande/course-workspace:latest"

  # Data volume at /app/data — persists Postgres data + any other state
  # across restarts. Postgres data lives at /app/data/pgdata.
  volumes {
    volume_name    = docker_volume.workspace_data.name
    container_path = "/app/data"
  }

  # Only the agent token goes in the container env — everything else
  # is set via the coder_agent env block below. This matches the
  # official Coder Docker template pattern.
  env = ["CODER_AGENT_TOKEN=${coder_agent.main.token}"]

  # Resource limits — 3 GB RAM / 2 vCPU per student.
  # Postgres + uvicorn --reload + Next.js + code-server all run in one container.
  memory    = 3221225472  # 3 GB (Postgres + uvicorn + Next.js + code-server)
  cpu_quota = 200000      # 2 vCPU

  # The entrypoint runs the Coder agent init script, which downloads and
  # starts the agent. The agent then runs the startup_script (clone repo,
  # start uvicorn). No replace() needed — CODER_AGENT_URL is already set
  # to the VPS's external IP by the Coder server, so the agent connects
  # directly without needing host.docker.internal.
  entrypoint = ["sh", "-c", coder_agent.main.init_script]

  # Restart policy
  restart = "unless-stopped"

  # Keep the container even when workspace is stopped
  lifecycle {
    ignore_changes = [image]
  }
}

# ---------------------------------------------------------------------------
# Coder agent — runs inside the workspace container
# ---------------------------------------------------------------------------

resource "coder_agent" "main" {
  os   = "linux"
  arch = "amd64"
  dir  = "/app"

  startup_script_behavior = "non-blocking"

  # The startup script runs inside the container after it starts.
  # It clones the repo, installs deps (fast — pre-baked in image),
  # and starts uvicorn in the foreground.
  startup_script = <<-EOT
    set -e

    # PostgreSQL server binaries live in /usr/lib/postgresql/16/bin/ (not on PATH).
    # Use full paths for all su postgres -c commands since su starts a new shell
    # that doesn't inherit exported PATH.
    PG_BIN="/usr/lib/postgresql/16/bin"

    # Clone the repo if it doesn't exist
    if [ ! -d /app/.git ]; then
      echo "Cloning repository..."
      git clone https://github.com/pedrogrande/starter-workspace /app-tmp
      cp -a /app-tmp/. /app/
      rm -rf /app-tmp
    else
      echo "Repository already cloned, pulling latest..."
      cd /app && git pull || true
    fi

    # Ensure data directory exists (volume may be empty on first start)
    mkdir -p /app/data
    chown postgres:postgres /app/data

    # Install dependencies (fast — pre-baked in image, this is a safety net)
    cd /app
    uv pip sync requirements.txt --system 2>/dev/null || true

    # Make entrypoint executable
    chmod +x /app/scripts/entrypoint.sh 2>/dev/null || true

    # Start PostgreSQL (in-container, data on persistent volume)
    # PostgreSQL binaries are at /usr/lib/postgresql/16/bin/ — not on PATH.
    # We use full absolute paths in every su postgres -c command because
    # su starts a new shell that doesn't inherit the parent's PATH.
    export PGDATA=/app/data/pgdata
    if [ ! -d "$PGDATA" ] || [ ! -f "$PGDATA/postgresql.conf" ]; then
      echo "Initializing PostgreSQL database..."
      mkdir -p "$PGDATA"
      chown postgres:postgres "$PGDATA"
      chmod 700 "$PGDATA"
      su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /app/data/pgdata --auth=trust' 2>&1 | tail -5
      # Configure Postgres to listen on localhost
      echo "listen_addresses = 'localhost'" >> "$PGDATA/postgresql.conf"
      echo "unix_socket_directories = '/tmp'" >> "$PGDATA/postgresql.conf"
      su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /app/data/pgdata start -w -l /tmp/pg.log'
      # Create the course database and user via a SQL script file.
      # This avoids the quoting nightmare of nested su -c '...' -c "..." layers.
      cat > /tmp/init.sql << 'SQLEOF'
CREATE USER ai WITH PASSWORD 'ai' SUPERUSER;
CREATE DATABASE ai OWNER ai;
\c ai
CREATE EXTENSION IF NOT EXISTS vector;
SQLEOF
      chown postgres:postgres /tmp/init.sql
      su postgres -c '/usr/lib/postgresql/16/bin/psql -f /tmp/init.sql' 2>&1
      rm -f /tmp/init.sql
      echo "PostgreSQL initialized with pgvector extension."
    else
      echo "Starting PostgreSQL..."
      su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /app/data/pgdata start -w -l /tmp/pg.log' 2>/dev/null || true
    fi
    # Wait for Postgres to be ready
    until su postgres -c '/usr/lib/postgresql/16/bin/pg_isready -q' 2>/dev/null; do sleep 1; done
    echo "PostgreSQL is ready."

    # Install code-server (VS Code in the browser) if not already present
    if ! command -v code-server &>/dev/null; then
      echo "Installing code-server..."
      curl -fsSL https://code-server.dev/install.sh | sh
    fi

    # Start code-server in the background (auth none for Coder proxy)
    echo "Starting VS Code Browser on port 13337..."
    code-server --auth none --port 13337 --disable-telemetry /app &

    # Start the AgentOS API in the background with hot-reload.
    # --reload watches files in agents/ and app/ and auto-reloads on edits.
    # Adding a brand-new agent file still needs a full restart —
    # run `./scripts/restart-api.sh` in that case.
    echo "Starting AgentOS on port 8000 (with hot-reload)..."
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir agents --reload-dir app &

    # Wait for AgentOS to be ready
    until curl -s http://localhost:8000/ > /dev/null 2>&1; do
      sleep 1
    done
    echo "AgentOS is ready."

    # Start Agent-UI in the foreground (clean kill on workspace stop)
    echo "Starting Agent-UI on port 3000..."
    cd /agent-ui && exec npx next start -p 3000
  EOT

  # App environment variables — these are injected by the agent into
  # the startup_script's shell environment.
  env = {
    DB_BACKEND      = "postgres"
    DB_HOST         = "localhost"
    DB_PORT         = "5432"
    DB_USER         = "ai"
    DB_PASS         = "ai"
    DB_DATABASE     = "ai"
    RUNTIME_ENV     = "dev"
    AGNO_DEBUG      = "True"
    DATA_DIR        = "/app/data"
    PGDATA          = "/app/data/pgdata"
    AGENTOS_URL     = "http://localhost:8000"
    OPENAI_API_KEY  = var.openai_api_key
    OLLAMA_API_KEY  = var.ollama_api_key
    # Point the Ollama CLI / extension at Ollama Cloud (not localhost:11434)
    OLLAMA_HOST     = "https://ollama.com"
  }
}

# ---------------------------------------------------------------------------
# Coder apps — clickable URLs in the dashboard
# ---------------------------------------------------------------------------

# Agent-UI chat interface (port 3000) — primary student interface
# NOTE: subdomain=true is required for Next.js apps to work correctly through
# the Coder proxy (path-based proxying breaks absolute asset paths).
# To enable: set CODER_WILDCARD_ACCESS_URL on the VPS and uncomment subdomain.
# See docs/coder-workspace-setup-guide.md for details.
resource "coder_app" "agent_ui" {
  count        = data.coder_workspace.me.start_count
  agent_id     = coder_agent.main.id
  slug         = "agent-ui"
  display_name = "Agent UI"
  url          = "http://localhost:3000"
  icon         = "https://raw.githubusercontent.com/pedrogrande/starter-workspace/main/docs/agno-orange.svg"
  share        = "owner"
  order        = 1
  subdomain    = true
}

# AgentOS API (port 8000) — secondary, for API exploration
resource "coder_app" "agentos" {
  count        = data.coder_workspace.me.start_count
  agent_id     = coder_agent.main.id
  slug         = "agentos"
  display_name = "AgentOS API"
  url          = "http://localhost:8000"
  icon         = "https://raw.githubusercontent.com/pedrogrande/starter-workspace/main/docs/agno-black.svg"
  share        = "owner"
  order        = 2
  subdomain    = true
}

# VS Code in the browser (code-server) — web-based IDE
resource "coder_app" "vscode_browser" {
  count        = data.coder_workspace.me.start_count
  agent_id     = coder_agent.main.id
  slug         = "vscode-browser"
  display_name = "VS Code Browser"
  url          = "http://localhost:13337"
  icon         = "${data.coder_workspace.me.access_url}/icon/code.svg"
  share        = "owner"
  order        = 3
  subdomain    = true
  healthcheck {
    url       = "http://localhost:13337/healthz"
    interval  = 5
    threshold = 6
  }
}

# ---------------------------------------------------------------------------
# Metadata — surface useful info in the dashboard
# ---------------------------------------------------------------------------

resource "coder_metadata" "workspace_info" {
  count       = data.coder_workspace.me.start_count
  resource_id = docker_container.workspace[0].id
  item {
    key   = "Agent UI"
    value = "http://localhost:3000"
  }
  item {
    key   = "API URL"
    value = "http://localhost:8000"
  }
  item {
    key   = "Data volume"
    value = docker_volume.workspace_data.name
  }
  item {
    key   = "Database"
    value = "PostgreSQL 16 + pgvector (localhost:5432)"
  }
  item {
    key   = "DB Data"
    value = "/app/data/pgdata (persistent volume)"
  }
}