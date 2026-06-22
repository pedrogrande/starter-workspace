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
# Parameters — students provide their API keys at workspace creation time
# ---------------------------------------------------------------------------

data "coder_parameter" "openai_api_key" {
  name         = "openai_api_key"
  display_name = "OpenAI API Key"
  description  = "Used for embeddings (text-embedding-3-small). Get one at https://platform.openai.com/api-keys"
  type         = "string"
  mutable      = true
  default      = ""
}

data "coder_parameter" "ollama_api_key" {
  name         = "ollama_api_key"
  display_name = "Ollama API Key"
  description  = "Used for the default model (glm-5.1:cloud). Get one at https://ollama.com"
  type         = "string"
  mutable      = true
  default      = ""
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

  # Data volume at /app/data — persists SQLite DB + ChromaDB across restarts
  volumes {
    volume_name    = docker_volume.workspace_data.name
    container_path = "/app/data"
  }

  # Only the agent token goes in the container env — everything else
  # is set via the coder_agent env block below. This matches the
  # official Coder Docker template pattern.
  env = ["CODER_AGENT_TOKEN=${coder_agent.main.token}"]

  # Resource limits — 1 GB RAM / 1 vCPU per student is sufficient for
  # the Python app + SQLite + ChromaDB. Bump if students run heavy evals.
  memory    = 1073741824  # 1 GB
  cpu_quota = 100000      # 1 vCPU (100ms per 100ms = 1 full CPU)

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

  startup_script_behavior = "blocking"

  # The startup script runs inside the container after it starts.
  # It clones the repo, installs deps (fast — pre-baked in image),
  # and starts uvicorn in the foreground.
  startup_script = <<-EOT
    set -e

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

    # Install dependencies (fast — pre-baked in image, this is a safety net)
    cd /app
    uv pip sync requirements.txt --system 2>/dev/null || true

    # Make entrypoint executable
    chmod +x /app/scripts/entrypoint.sh 2>/dev/null || true

    # Start the AgentOS API in the foreground
    # (foreground = clean kill on workspace stop, no zombie processes)
    echo "Starting AgentOS on port 8000..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
  EOT

  # App environment variables — these are injected by the agent into
  # the startup_script's shell environment.
  env = {
    DB_BACKEND      = "sqlite"
    RUNTIME_ENV     = "dev"
    AGNO_DEBUG      = "True"
    DATA_DIR        = "/app/data"
    AGENTOS_URL     = "http://localhost:8000"
    OPENAI_API_KEY  = data.coder_parameter.openai_api_key.value
    OLLAMA_API_KEY  = data.coder_parameter.ollama_api_key.value
  }
}

# ---------------------------------------------------------------------------
# Coder apps — clickable URLs in the dashboard
# ---------------------------------------------------------------------------

# AgentOS API + UI (port 8000)
resource "coder_app" "agentos" {
  count        = data.coder_workspace.me.start_count
  agent_id     = coder_agent.main.id
  slug         = "agentos"
  display_name = "AgentOS"
  url          = "http://localhost:8000"
  icon         = "/icon/gear.svg"
  share        = "owner"
  order        = 1
}

# ---------------------------------------------------------------------------
# Metadata — surface useful info in the dashboard
# ---------------------------------------------------------------------------

resource "coder_metadata" "workspace_info" {
  count       = data.coder_workspace.me.start_count
  resource_id = docker_container.workspace[0].id
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
    value = "SQLite (/app/data/agents.db)"
  }
  item {
    key   = "Vector DB"
    value = "ChromaDB (/app/data/chromadb)"
  }
}