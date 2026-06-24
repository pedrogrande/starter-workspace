# Phase 5: Verification Guide

This guide walks you through the remaining verification steps for your Coder workspace setup. Along the way, you'll learn how Coder works — how workspaces start and stop, how data persists, how the agent communicates, and how to interact with your workspace.

**Prerequisites:**

- A healthy workspace running in Coder (completed in Phase 3/4)
- SSH access to the VPS
- The Coder CLI authenticated locally

---

## Coder Concepts You'll Need

Before diving in, here's a quick orientation to how Coder works:

### Workspaces

A **workspace** is a set of cloud resources (in our case, a Docker container + a Docker volume) provisioned by a Terraform template. Each workspace belongs to one user. When you **start** a workspace, Coder runs `terraform apply` to create the resources. When you **stop** it, Coder runs `terraform destroy` on ephemeral resources but preserves persistent ones (like our data volume).

### The Coder Agent

The **Coder agent** is a small binary that runs inside the workspace container. It:

- Connects to the Coder server via a coordination RPC
- Runs the `startup_script` you defined in the template
- Provides SSH access, port forwarding, and app proxying
- Reports health status back to the dashboard

The agent is what makes the workspace "alive" — without it, the container is just a box with no way in.

### Apps

**Coder apps** are HTTP endpoints inside the workspace that Coder proxies to the outside world. Our template defines one app: `agentos` on port 8000. When you click the app link in the dashboard, Coder tunnels your browser request through the agent to port 8000 inside the container.

### Volumes and Persistence

Docker volumes persist data outside the container's filesystem. Our template creates a volume mounted at `/app/data` — this survives workspace stop/start. The container itself is destroyed and recreated on each start, but the volume stays. This is where SQLite databases and ChromaDB vectors live.

---

## Step 1: Verify the Workspace is Running and API Responds

We already confirmed this during setup, but let's do it systematically and understand what we're checking.

### 1.1 Check workspace health in the dashboard

1. Open `http://74.208.237.168` in your browser
2. Click your workspace name (`starter-one`)
3. The **Agent** section should show a green "Connected" status

**What this tells you:** The Coder agent inside the container has established a connection to the Coder server. The agent communicates via a WireGuard-based tailnet (you can see DERP relay connections in the logs). If the agent can't connect, the workspace shows as "unhealthy."

### 1.2 Access the AgentOS API via the Coder proxy

1. In the workspace page, click the **AgentOS** app link
2. You should see the AgentOS API JSON response: `{"name":"AgentOS API","version":"1.0.0"}`

**What this tells you:** The Coder agent is proxying HTTP requests from your browser through the tailnet to port 8000 inside the container. Uvicorn is running and serving the AgentOS FastAPI app.

> **Note: Swagger UI (`/docs`) doesn't work through the Coder proxy.** The Coder app proxy serves the workspace at a subpath (e.g., `/@pedrog/starter-one/apps/agentos/`), but Swagger UI fetches its schema from `/openapi.json` using a relative URL, which resolves to the wrong path through the proxy. This is a general limitation of Swagger UI behind any reverse proxy that uses a subpath — not a bug in your setup.
>
> **To access the Swagger UI**, use SSH port forwarding instead:
>
> First, set up Coder's SSH config (one-time setup):
>
> ```bash
> coder config-ssh
> # Type "yes" when prompted to update ~/.ssh/config
> ```
>
> Then connect with standard SSH port forwarding:
>
> ```bash
> ssh -L 8000:localhost:8000 starter-one.coder
> # Then open http://localhost:8000/docs in your browser
> ```
>
> Note: `coder ssh` doesn't support `-L` for local port forwarding. You must use `coder config-ssh` first, then use standard `ssh -L` with the `.coder` hostname suffix.
>
> The Swagger UI works perfectly via SSH because there's no reverse proxy in the way. You'll see all 107 routes registered. Students will use the AgentOS playground UI (which works through the proxy) rather than the raw Swagger UI.

### 1.3 Access the AgentOS playground

The AgentOS UI is served on the same port as the API. In the Coder dashboard:

1. Click the **AgentOS** app link
2. Navigate to `/` (the root) — you should see the AgentOS playground
3. Try sending a message to one of the agents (e.g., `web-search`)

**What this tells you:** The full agent stack is working — the API, the database (SQLite for sessions), and the model provider (Ollama for the LLM). If the agent responds, the entire chain is functional.

### 1.4 Verify sessions persist in SQLite

Let's confirm that conversations are being saved to the SQLite database.

**Via SSH to the VPS:**

```bash
ssh root@74.208.237.168
docker exec student-pedrog-starter-one ls -la /app/data/
```

You should see `agents.db` — this is the SQLite database.

```bash
# Check that sessions are being written
docker exec student-pedrog-starter-one python3 -c "
import sqlite3
conn = sqlite3.connect('/app/data/agents.db')
cursor = conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"')
tables = [row[0] for row in cursor.fetchall()]
print('Tables:', tables)
conn.close()
"
```

You should see tables like `agno_sessions`, `agno_memories`, `agno_metrics`, etc.

**What this tells you:** Agno's `SqliteDb` is creating tables and persisting session data to the file-based database. The `DATA_DIR=/app/data` env var is directing all data to the mounted volume.

---

## Step 2: Verify RAG Works (Knowledge Base + ChromaDB)

This step tests that the ChromaDB vector database is functioning — students will use this for RAG (Retrieval-Augmented Generation) exercises.

### 2.1 Create a knowledge base via the API

From your browser (using the Coder-proxied AgentOS URL), or via SSH:

```bash
ssh root@74.208.237.168
docker exec student-pedrog-starter-one curl -s -X POST http://localhost:8000/v1/knowledge \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Knowledge",
    "description": "Testing ChromaDB vector storage",
    "table_name": "test_vectors"
  }' | python3 -m json.tool
```

Note the `id` from the response — you'll need it for the next step.

**What this tells you:** The `create_knowledge()` function in `db/session.py` is working with ChromaDB. It creates a ChromaDB collection called `test_vectors` in `/app/data/chromadb/` and a contents table in SQLite.

### 2.2 Verify ChromaDB created the collection

```bash
docker exec student-pedrog-starter-one ls -la /app/data/chromadb/
```

You should see a directory structure — ChromaDB stores collections as subdirectories with vector index files.

### 2.3 Insert a document and search

```bash
# Insert a document
docker exec student-pedrog-starter-one curl -s -X POST http://localhost:8000/v1/knowledge/<KNOWLEDGE_ID>/content \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Agno is a framework for building multi-agent AI systems with memory, knowledge, and tools.",
    "name": "Agno Overview"
  }' | python3 -m json.tool

# Wait a few seconds for embedding + indexing, then search
sleep 5

docker exec student-pedrog-starter-one curl -s -X POST http://localhost:8000/v1/knowledge/<KNOWLEDGE_ID>/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is Agno?"
  }' | python3 -m json.tool
```

You should see the document returned in the search results.

**What this tells you:** The full RAG pipeline works:

1. OpenAI's `text-embedding-3-small` generated an embedding for the document
2. ChromaDB stored the embedding in its persistent collection
3. Hybrid search (vector + keyword) found the document matching the query

This is the same pipeline students will use for their RAG exercises — just with different documents.

---

## Step 3: Verify Per-Student Isolation

This step confirms that each student's data is isolated — no shared state between students.

### 3.1 Understand the isolation model

Each student workspace gets:

- Its own Docker container (named `student-<username>-<workspace>`)
- Its own Docker volume (named `student-<username>-data`)
- Its own SQLite database (inside the volume at `/app/data/agents.db`)
- Its own ChromaDB instance (inside the volume at `/app/data/chromadb/`)

There is no shared database, no shared filesystem, and no shared network namespace. The only shared resource is the VPS host's Docker daemon (which Coder uses to provision containers).

### 3.2 Verify on the VPS

```bash
ssh root@74.208.237.168

# List all workspace containers — each student has their own
docker ps --filter "name=student-" --format "{{.Names}} {{.Status}}"

# List all workspace volumes — each student has their own
docker volume ls --filter "name=student-"

# Inspect a specific student's volume
docker volume inspect student-pedrog-data
```

You should see one container and one volume per student, each named with the student's username.

### 3.3 Create a second workspace (simulating a second student)

If you want to verify isolation practically:

1. Create a second user in the Coder dashboard (Users → New User)
2. Log in as that user (or use a different browser session)
3. Create a workspace with different API keys
4. On the VPS, confirm the second workspace has its own container and volume:

```bash
docker ps --filter "name=student-" --format "{{.Names}}"
# Should show two containers:
# student-pedrog-starter-one
# student-<second-user>-starter-one

docker volume ls --filter "name=student-"
# Should show two volumes:
# student-pedrog-data
# student-<second-user>-data
```

**What this tells you:** The Terraform template's use of `data.coder_workspace_owner.me.name` in resource names ensures each student gets uniquely named containers and volumes. There's no way for one student to access another's data.

---

## Step 4: Verify No Docker-in-Docker

This step confirms that Docker is not available inside the workspace container — students can't run Docker commands, which means no Docker-in-Docker (DinD) security risks.

### 4.1 Try running Docker inside the workspace

```bash
ssh root@74.208.237.168
docker exec student-pedrog-starter-one docker ps
```

You should see:

```
bash: docker: command not found
```

### 4.2 Understand why this is the case

The workspace image (`Dockerfile.workspace`) is based on `agnohq/python:3.12` — a Python image with no Docker installed. The `Dockerfile.workspace` adds `curl`, `git`, and `postgresql-client`, but not Docker. The container runs on the VPS's Docker daemon (managed by Coder), but the container itself has no Docker client or daemon.

**What this tells you:** The architecture is working as designed. Docker runs only on the VPS host (managed by Coder's provisioner). Student workspaces are plain Python containers with no ability to spawn nested containers. This eliminates the security and complexity concerns of Docker-in-Docker.

---

## Step 5: Test Stop/Start Persistence

This is the most important test — it confirms that student data survives workspace restarts. When a student stops their workspace (to save resources) and starts it again later, their sessions, memory, and knowledge bases should still be there.

### 5.1 Note the current state

Before stopping, note what's in the data volume:

```bash
ssh root@74.208.237.168
docker exec student-pedrog-starter-one ls -la /app/data/
docker exec student-pedrog-starter-one ls -la /app/data/chromadb/
docker exec student-pedrog-starter-one python3 -c "
import sqlite3
conn = sqlite3.connect('/app/data/agents.db')
cursor = conn.execute('SELECT count(*) FROM agno_sessions')
print('Session count:', cursor.fetchone()[0])
conn.close()
"
```

Note the session count and the files present.

### 5.2 Stop the workspace

**Via the Coder dashboard:**

1. Go to your workspace page
2. Click **Stop**
3. Wait for the workspace to show as "Stopped"

**Or via CLI:**

```bash
coder stop pedrog/starter-one
```

**What happens when you stop a workspace:**

- Coder runs `terraform destroy` on the workspace's Terraform state
- The Docker container is destroyed (removed entirely)
- The Docker volume is **NOT destroyed** — it's declared without `count` in the template, so it persists
- The Coder agent disconnects
- The workspace shows as "Stopped" in the dashboard

### 5.3 Verify the volume persists on the VPS

```bash
ssh root@74.208.237.168

# The container should be gone
docker ps --filter "name=student-pedrog" --format "{{.Names}} {{.Status}}"
# Should show nothing (or the container in "Exited" state)

# But the volume should still exist
docker volume ls --filter "name=student-pedrog"
# Should still show: student-pedrog-data

# Inspect the volume — the data is still there
docker run --rm -v student-pedrog-data:/data alpine ls -la /data/
# Should show agents.db, chromadb/, etc.
```

**What this tells you:** The `docker_volume` resource in the Terraform template is declared without `count = data.coder_workspace.me.start_count`, so it's not tied to the workspace's start/stop state. The volume outlives the container.

### 5.4 Start the workspace again

**Via the dashboard:**

1. Click **Start**
2. Wait for the workspace to show as "Started" and "Healthy"

**Or via CLI:**

```bash
coder start pedrog/starter-one
```

**What happens when you start a workspace:**

- Coder runs `terraform apply` to recreate the resources
- A new Docker container is created from the same image
- The existing Docker volume is reattached to `/app/data`
- The Coder agent downloads, connects, and runs the startup script
- The startup script sees `/app/.git` already exists (from the volume? No — the repo is cloned into `/app` which is the container's filesystem, not the volume)

**Important:** The repo is cloned into `/app` (the container's filesystem), which is ephemeral — it's recreated on each start. But the data in `/app/data` (the volume) persists. So the startup script's `git clone` check (`if [ ! -d /app/.git ]`) will re-clone the repo on each start, but the SQLite database and ChromaDB vectors in `/app/data/` will still be there from the previous session.

### 5.5 Verify data persisted

```bash
ssh root@74.208.237.168
docker exec student-pedrog-starter-one ls -la /app/data/
docker exec student-pedrog-starter-one python3 -c "
import sqlite3
conn = sqlite3.connect('/app/data/agents.db')
cursor = conn.execute('SELECT count(*) FROM agno_sessions')
print('Session count after restart:', cursor.fetchone()[0])
conn.close()
"
```

The session count should match what you noted in Step 5.1. The `agents.db` file and `chromadb/` directory should be unchanged.

**What this tells you:** The volume mount at `/app/data` correctly persists data across workspace stop/start cycles. Students can stop their workspace to save VPS resources and start it again later without losing their work.

### 5.6 Verify the API still works

```bash
docker exec student-pedrog-starter-one curl -s http://localhost:8000/
```

Should return `{"name":"AgentOS API","version":"1.0.0"}`.

**What this tells you:** Uvicorn starts cleanly on workspace restart. SQLite doesn't need a "wait for database" step (unlike Postgres) — the database file is instantly available when the volume is mounted. This is a key advantage of the SQLite + ChromaDB architecture over the original Postgres setup.

---

## Step 6: Verify Postgres Fallback

This step confirms that the `DB_BACKEND` switch works — the repo hasn't lost its ability to run with Postgres. This is important if you ever want to teach the Postgres path or deploy to Railway (which uses Postgres).

### 6.1 Start a temporary Postgres on the VPS

```bash
ssh root@74.208.237.168

# Run a temporary Postgres with pgvector
docker run -d --name test-postgres \
  -e POSTGRES_USER=ai \
  -e POSTGRES_PASSWORD=ai \
  -e POSTGRES_DB=ai \
  -p 5433:5432 \
  agnohq/pgvector:18

# Wait for it to be ready
sleep 5
docker exec test-postgres pg_isready -U ai
```

Note: we use port 5433 on the host to avoid conflicts with any existing Postgres.

### 6.2 Test the app with Postgres backend

```bash
# Run a temporary container with DB_BACKEND=postgres, pointing at the test Postgres
docker run --rm -d --name test-pg-app \
  --link test-postgres:postgres \
  -e DB_BACKEND=postgres \
  -e DB_HOST=postgres \
  -e DB_PORT=5432 \
  -e DB_USER=ai \
  -e DB_PASS=ai \
  -e DB_DATABASE=ai \
  -e RUNTIME_ENV=dev \
  -e OPENAI_API_KEY=test \
  -e OLLAMA_API_KEY=test \
  -p 8001:8000 \
  ghcr.io/pedrogrande/course-workspace:latest \
  uvicorn app.main:app --host 0.0.0.0 --port 8000

# Wait for startup
sleep 10

# Test the API
curl -s http://localhost:8001/
```

Should return `{"name":"AgentOS API","version":"1.0.0"}`.

**What this tells you:** The `DB_BACKEND=postgres` switch in `db/session.py` correctly routes to `PostgresDb` and `PgVector` when set. The app works with both SQLite (default) and Postgres (fallback). Students who want to learn the Postgres path can switch by changing the env var.

### 6.3 Clean up

```bash
docker stop test-pg-app test-postgres
docker rm test-postgres
```

---

## Summary Checklist

After completing all 6 steps, verify each box is checked:

- [ ] **Step 1:** Workspace is healthy, AgentOS API responds, sessions persist in SQLite
- [ ] **Step 2:** Knowledge base created, document inserted, ChromaDB hybrid search returns results
- [ ] **Step 3:** Each student has isolated containers and volumes (no shared state)
- [ ] **Step 4:** `docker ps` fails inside the workspace (no DinD)
- [ ] **Step 5:** Workspace data survives stop/start (SQLite + ChromaDB in persistent volume)
- [ ] **Step 6:** `DB_BACKEND=postgres` works with an external Postgres (fallback validated)

---

## What You've Learned About Coder

Through these verification steps, you've seen:

1. **Workspace lifecycle** — how Coder uses Terraform to create/destroy containers while preserving volumes
2. **Agent communication** — how the Coder agent connects to the server and runs startup scripts
3. **App proxying** — how Coder tunnels HTTP from the browser through the agent to the container
4. **Volume persistence** — how Docker volumes declared without `count` survive workspace stop/start
5. **Template parameters** — how per-student API keys are passed through `coder_parameter` → `coder_agent` env
6. **Resource isolation** — how container names and volumes are namespaced by username
7. **Health checking** — how the `startup_script_behavior = "blocking"` setting makes the workspace show as healthy only after the startup script completes

You're now ready to create student accounts and let them start building agents!

G00nFister!
