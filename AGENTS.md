# AgentOS Coder Course Template

This file is the source of truth for any agent (Claude Code, Codex, others) working in this repo. `CLAUDE.md` is a symlink to this file — edit one, both update.

## Project Overview

A unified agent platform built on [Agno](https://docs.agno.com), shipped as a copy-pasteable starting point for students. Two reference agents demonstrate the two common shapes for supplying context to an agent. SQLite + ChromaDB handle persistence for sessions, memory, and knowledge (zero-server, file-based). Designed to run inside a Coder workspace — no external databases or Docker Compose needed.

## Architecture

```
AgentOS  (app/main.py)
├── WebSearch  (agents/web_search.py)   — Parallel SDK or keyless MCPTools
├── CodeSearch (agents/code_search.py)  — WorkspaceContextProvider
└── AgnoSupport (agents/agno_support.py) — Agno docs MCP

Teams:
└── EngineeringTeam (teams/engineering_team.py) — PM + Tech Lead coordination
```

Shared:

- SQLite for agent storage (sessions, memory, metrics, evals, knowledge, schedules).
- ChromaDB for vector storage (RAG knowledge bases, hybrid search).
- Both stored on a persistent Docker volume at `/app/data` — survives workspace stop/start.
- `app.settings.default_model()` returns `Ollama(id="glm-5.1:cloud")` — bump the model in one place.
- OpenAI key used only for embeddings (`text-embedding-3-small`).
- Scheduler enabled by default (`scheduler=True`).
- Slack interface lights up automatically when both `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` are set.
- JWT auth on whenever `RUNTIME_ENV == "prd"` (so production deploys are gated by default). Coder sets `RUNTIME_ENV=dev`.

## Key Files

| File | Purpose |
|------|---------|
| [`app/main.py`](app/main.py) | AgentOS entrypoint — lifespan hook, conditional Slack, JWT gate. |
| [`app/settings.py`](app/settings.py) | `default_model()` factory. |
| [`app/config.yaml`](app/config.yaml) | Quick prompts per agent (keyed by agent `id`). |
| [`agents/web_search.py`](agents/web_search.py) | Reference agent — direct tools (Parallel SDK or MCP). |
| [`agents/code_search.py`](agents/code_search.py) | Reference agent — context provider. |
| [`db/session.py`](db/session.py) | `get_db()`, `create_knowledge()` — SQLite or Postgres backend. |
| [`db/url.py`](db/url.py) | Builds the Postgres database URL from env (only used when `DB_BACKEND=postgres`). |
| [`evals/cases.py`](evals/cases.py) | Eval cases (each is a `Case` with optional judge + reliability checks). |
| [`evals/__main__.py`](evals/__main__.py) | `python -m evals` runner — wraps agno's `AgentAsJudgeEval` + `ReliabilityEval`. |
| [`scripts/restart-api.sh`](scripts/restart-api.sh) | Restart the AgentOS API after adding a new agent or new dependencies. |
| [`compose.yaml`](compose.yaml) | Docker Compose for local development (outside Coder). |
| [`coder-template/main.tf`](coder-template/main.tf) | Coder Terraform template — workspace provisioning. |
| [`Dockerfile.workspace`](Dockerfile.workspace) | Multi-stage build for the Coder workspace image. |

## Development Setup

### Inside a Coder Workspace

Students access the platform through a Coder workspace. The workspace container pre-bakes Python dependencies and Agent-UI. At workspace start, the Coder agent clones this repo into `/app`, starts uvicorn (with hot-reload), code-server (VS Code in browser), and Agent-UI.

**Services running in the workspace:**

| Service | Port | Purpose |
|---|---|---|
| AgentOS API | 8000 | The agent platform — agents, teams, knowledge, sessions. |
| Agent-UI | 3000 | Next.js chat interface with Sessions, Memory, Knowledge views. |
| VS Code Browser | 13337 | code-server (VS Code in the browser). |

**IDE options:** Students can connect using any of:
- **VS Code Browser** — click "VS Code Browser" in the Coder dashboard (code-server, no install needed).
- **VS Code Desktop** — install the [Coder extension](https://marketplace.visualstudio.com/items?itemName=coder.coder), open the Command Palette → "Coder: Connect to Workspace".
- **Cursor** — install the Coder extension in Cursor, connect the same way as VS Code.
- **Windsurf** — install the Coder extension in Windsurf, connect the same way.
- **SSH** — `coder config-ssh` then `ssh coder.<workspace>` from any terminal.

All IDEs connect via SSH to the workspace — no port configuration needed.

**Hot-reload:** Uvicorn runs with `--reload --reload-dir agents --reload-dir app`. Edits to files in `agents/` and `app/` are picked up automatically within ~1s — just refresh the browser. Adding a **new** agent file or registering a new agent in `app/main.py` requires a full restart:

```bash
./scripts/restart-api.sh
```

**Logs:** The restart script writes uvicorn output to `/tmp/agentos.log`:

```bash
tail -f /tmp/agentos.log
```

### Local Development (Outside Coder)

If you want to run the platform on your own machine (not in Coder):

```bash
cp example.env .env
# Edit .env and set OPENAI_API_KEY and OLLAMA_API_KEY

docker compose up -d --build
```

Hot-reload watches `agents/`, `app/`, `db/`. Edits land in <2s. `compose.yaml` sets `RUNTIME_ENV=dev`, `AGNO_DEBUG=True`, and `WAIT_FOR_DB=True` so JWT is off and the API blocks on the DB before serving.

### Format & Validate

The format / validate / eval scripts run on the host, so they need a venv. Set one up once:

```bash
./scripts/venv_setup.sh
source .venv/bin/activate
```

Then:

```bash
./scripts/format.sh     # ruff format + import sort
./scripts/validate.sh   # ruff check + mypy (runs both, summarizes)
```

CI installs the same pinned `requirements.txt` and runs the same `scripts/validate.sh` — local and CI never drift.

## Conventions

### Agent pattern

Every agent file has the same shape:

```python
"""
<Title> Agent
=============
"""

from agno.agent import Agent

from app.settings import default_model
from db import get_db

INSTRUCTIONS = """\
<one short paragraph: what the agent does, which tools it uses, the
rules to follow when answering>
"""

my_agent = Agent(
    id="my-agent",
    name="My Agent",
    model=default_model(),
    db=get_db(),
    tools=[...],
    instructions=INSTRUCTIONS,
    enable_agentic_memory=True,
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
)
```

Two patterns to copy from:

- **Direct tools** — see [`agents/web_search.py`](agents/web_search.py). The agent sees each tool individually. Best when the user knows which tools the agent needs.
- **Context provider** — see [`agents/code_search.py`](agents/code_search.py). The agent sees one `query_<thing>` tool that hands off to a sub-agent. Best for one-source agents and when collapsing many tools into one keeps the model focused.

### Database

The default backend is SQLite + ChromaDB (set `DB_BACKEND=sqlite` or leave unset). Both store data on the persistent volume at `/app/data` — no external database server needed. For production or multi-agent shared state, switch to Postgres + pgvector with `DB_BACKEND=postgres`.

```python
# Plain agent — sessions, memory, agentic memory live here
from db import get_db
agent_db = get_db()

# Agent with a Knowledge base (RAG) — pass through `knowledge=`
from db import create_knowledge
my_kb = create_knowledge("My Knowledge", "my_vectors")
```

Knowledge bases use hybrid search (`SearchType.hybrid`) and `text-embedding-3-small` embeddings. With SQLite backend, vectors go into ChromaDB at `/app/data/chromadb`; document contents go into `<table_name>_contents` in SQLite. With Postgres backend, vectors use PgVector and contents use Postgres.

## Adding a new agent

Two options:

1. **Hand it to your coding agent** — paste `Run docs/create-new-agent.md` into a Claude Code / Copilot session pointed at this repo. The agent asks what the agent should do, generates the file, registers it, smoke-tests it.
2. **Do it manually** — create `agents/<slug>.py`, register in `app/main.py`, add prompts to `app/config.yaml`. Then run `./scripts/restart-api.sh` — uvicorn hot-reload doesn't pick up newly-registered modules, so a restart is required for the new agent to load.

## Iterating on an agent

Two recursive loops over the same agent. Use them together.

- [`docs/extend-agent.md`](docs/extend-agent.md) — **you drive.** Add a tool, add a capability, refine the prompt, fix a known bug. Claude is the Agno-aware pair-programmer (uses the `agno-docs` MCP for any toolkit research). Loop: change → smoke-test → "anything else?".
- [`docs/improve-agent.md`](docs/improve-agent.md) — **Claude drives.** Derives probes from the agent's `INSTRUCTIONS`, judges, edits, re-runs. No user input needed. Loop: probe → judge → edit → re-probe.

Use `extend-agent.md` to *change* the agent; use `improve-agent.md` to *harden* it against its stated intent. Most fixes from either loop are one sentence in `INSTRUCTIONS`.

## Evals

The eval suite lives in [`evals/`](evals/). Each case wraps agno's [`AgentAsJudgeEval`](https://docs.agno.com/evals/agent-as-judge) (LLM judge against a rubric, binary pass/fail) and/or [`ReliabilityEval`](https://docs.agno.com/evals/reliability) (tool-call assertion). Run with `python -m evals`. Results log to the database via `db=eval_db` so history is visible at os.agno.com.

To diagnose failures and fix in scope, run [`docs/eval-and-improve.md`](docs/eval-and-improve.md) in your coding agent.

## Reviewing the repo

Run [`docs/review-and-improve.md`](docs/review-and-improve.md). A recurring sweep that diffs docs against code: every agent registered, every env var documented, every path in a doc still exists, every script behaves as advertised. Auto-fixes mechanical drift; flags anything bigger. Best run before a public-facing release or after a refactor.

## Environment Variables

In the Coder workspace, `OPENAI_API_KEY` and `OLLAMA_API_KEY` are pre-filled from a `terraform.tfvars` file on the VPS (not in the public repo). Students don't need to enter API keys. The rest are set by the Coder template's `coder_agent` env block.

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | yes | — | OpenAI key for embeddings (`text-embedding-3-small`). Pre-filled via Terraform variable. |
| `OLLAMA_API_KEY` | yes | — | Ollama key for the default model (`glm-5.1:cloud`). Pre-filled via Terraform variable. |
| `DB_BACKEND` | no | `sqlite` | `sqlite` (default, zero-server) or `postgres` (external Postgres + pgvector). |
| `DATA_DIR` | no | `data` | Where SQLite DB + ChromaDB files are stored. Coder sets this to `/app/data` (persistent volume). |
| `RUNTIME_ENV` | no | `prd` | `dev` enables hot-reload and disables JWT. Coder sets this to `dev`. |
| `JWT_VERIFICATION_KEY` | prd | — | Public key from os.agno.com. Required when `RUNTIME_ENV=prd` and `authorization=True`. |
| `AGENTOS_URL` | no | `http://127.0.0.1:8000` | Scheduler base URL. |
| `PARALLEL_API_KEY` | no | — | Authenticates the WebSearch Agent's Parallel SDK / MCP connection (raises rate ceiling). |
| `SLACK_BOT_TOKEN` | no | — | Bot token. Set with signing secret to enable Slack interface. |
| `SLACK_SIGNING_SECRET` | no | — | Signing secret. Both must be set for the interface to load. |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASS` / `DB_DATABASE` | no | matches compose | Postgres connection (only used when `DB_BACKEND=postgres`). |
| `DB_DRIVER` | no | `postgresql+psycopg` | SQLAlchemy driver (only used when `DB_BACKEND=postgres`). |
| `PORT` | no | `8000` | API server port. |
| `AGNO_DEBUG` | no | `False` | If `True`, agno emits verbose debug logs. Coder sets this for dev. |
| `WAIT_FOR_DB` | no | `False` | If `True`, the entrypoint blocks on the DB before starting. Compose sets this. |

## Ports

- AgentOS API: `8000`
- Agent-UI: `3000`
- VS Code Browser (code-server): `13337`
- Postgres (optional, when `DB_BACKEND=postgres`): `5432`

## Scheduler

`scheduler=True` is on in [`app/main.py`](app/main.py). Hand the scheduler an agent / workflow + a cron expression and it runs in the background. Use it for:

- **Maintenance** — purge old sessions, vacuum tables, rotate trace data.
- **Proactive runs** — every weekday morning, summarize overnight news for your portfolio.
- **Periodic re-evaluation** — run `python -m evals` weekly to catch regressions.

See [agno scheduler docs](https://docs.agno.com/agent-os/scheduler) for the cron API.

## Slack

Set `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` and restart. The default wiring in `app/main.py` routes Slack messages to `code_search` — change the `agent=` arg to point at any other agent. See the [agno Slack interface docs](https://docs.agno.com/agent-os/interfaces/overview) for the Slack-side app setup.

For Discord, Telegram, WhatsApp, and custom UIs, mirror the Slack conditional pattern with the relevant agno interface — see [agno interfaces overview](https://docs.agno.com/agent-os/interfaces/overview).

## Deploying to Coder

The Coder template lives in [`coder-template/main.tf`](coder-template/main.tf). The workspace Docker image is built from [`Dockerfile.workspace`](Dockerfile.workspace) and pushed to GHCR.

**Updating the workspace image** (when Agent-UI or Python dependencies change):

```bash
# Build and push the image (from the repo root, on a machine with Docker buildx)
docker buildx prune -af
docker buildx build --platform linux/amd64 --no-cache --output type=registry \
  -t ghcr.io/pedrogrande/course-workspace:latest \
  -f Dockerfile.workspace .

# Pull on the VPS and recreate workspaces
ssh root@<vps> 'docker pull ghcr.io/pedrogrande/course-workspace:latest'
ssh root@<vps> 'echo yes | coder stop <user>/<workspace>; sleep 5; echo yes | coder start <user>/<workspace>'
```

**Pushing template changes** (when `main.tf` changes):

```bash
scp coder-template/main.tf root@<vps>:/tmp/main.tf
ssh root@<vps> 'cp /tmp/main.tf /tmp/coder-template/ && cd /tmp/coder-template && \
  echo yes | coder templates push agentos-course --directory . \
  --var-file=/tmp/coder-template/terraform.tfvars'
```

API keys are passed via `terraform.tfvars` (gitignored on the VPS, not in the public repo). See `coder-template/terraform.tfvars.example` for the format.

See [`docs/pushing-changes-to-Coder.md`](docs/pushing-changes-to-Coder.md) for the full guide on what needs a rebuild vs. just a git push.

## Common Tasks

```bash
# Add a Python dependency (persists across restarts)
# 1. Edit pyproject.toml
echo "new-package" >> requirements.txt
uv pip install new-package --system
git add requirements.txt pyproject.toml && git commit && git push
# Then rebuild the Docker image (see Deploying to Coder above)

# Install a package quickly (won't survive workspace restart)
uv pip install <package> --system

# Restart the API after adding a new agent
./scripts/restart-api.sh

# Tail API logs
tail -f /tmp/agentos.log

# Build a multi-arch image (maintainer-only)
./scripts/build_image.sh
```

## Documentation Links

- [Agno docs](https://docs.agno.com) — full framework reference.
- [Agno LLM-friendly docs](https://docs.agno.com/llms.txt) — concise overview, good for fetching.
- [AgentOS introduction](https://docs.agno.com/agent-os/introduction).
- [Agno tools / toolkits](https://docs.agno.com/tools/toolkits) — 100+ integrations.
- [Agno model providers](https://docs.agno.com/models) — OpenAI, Anthropic, Google, Ollama, Bedrock, Azure, etc.
- [Agno teams](https://docs.agno.com/teams/overview) — multi-agent routing/coordination.
- [Agno workflows](https://docs.agno.com/workflows/overview) — deterministic step-by-step pipelines.
- [Agno interfaces](https://docs.agno.com/agent-os/interfaces/overview) — Slack, Discord, Telegram, WhatsApp, custom UIs.
