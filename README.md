# AgentOS Railway Template

A unified agent platform you can run on Railway for ~$20/month. Two reference agents, Postgres-backed memory and knowledge, conditional Slack interface, and a Claude-Code-driven workflow for shipping and improving agents.

The platform is built around five pieces:

1. **Runtime** — FastAPI + AgentOS (`app/main.py`).
2. **Storage** — PostgreSQL + pgvector (sessions, memory, knowledge, traces).
3. **Connectors** — MCP servers and toolkits (`agno.tools.*`).
4. **Interfaces** — Slack out of the box; Discord / Telegram / custom UIs via [agno interfaces](https://docs.agno.com/agent-os/interfaces/overview).
5. **Infrastructure** — Docker locally, Railway in production.

For the full narrative ("How to Build an Agent Platform for Your Company"), see the blog post.

---

## Step 1: Run locally

> **Prerequisite:** [Docker](https://www.docker.com/get-started/) installed and running.

```sh
git clone https://github.com/agno-agi/agentos-railway-template.git agent-platform
cd agent-platform

cp example.env .env
# Edit .env and set OPENAI_API_KEY

docker compose up -d --build
```

Confirm AgentOS is live at [http://localhost:8000/docs](http://localhost:8000/docs).

Connect a UI: open [os.agno.com](https://os.agno.com), click **Add OS** → **Local**, enter `http://localhost:8000`, and connect.

## Step 2: Create your first agent

The template ships with two reference agents:

| Agent | Pattern | Tools |
|---|---|---|
| WebSearch Agent | Direct tools (Parallel SDK or MCP) | `parallel_search` / `parallel_extract` with `PARALLEL_API_KEY`; `web_search` / `web_fetch` keyless |
| CodeSearch Agent | Context provider (sub-agent) | `query_my_codebase` |

These cover the two common shapes of supplying context to an agent — direct tools, and a single `query_<source>` tool backed by a sub-agent. Most agents you build will extend one of these.

**To create a new agent:** open [Claude Code](https://claude.ai/code) in this repo and paste:

```
Run docs/create-new-agent.md
```

Claude asks what the agent should do, generates the file in `agents/`, registers it in `app/main.py`, adds prompts to `app/config.yaml`, and smoke-tests via cURL. Hot-reload picks up the new file in <2s. Usually 5-10 minutes for a simple agent.

## Step 3: Test your agent

Chat with it at [os.agno.com](https://os.agno.com), or hit it directly:

```sh
curl -X POST http://localhost:8000/agents/<agent-id>/runs \
  -F "message=hello" \
  -F "user_id=me" \
  -F "stream=false"
```

Run realistic prompts. Try edge cases. Watch the traces and sessions in the UI.

## Step 4: Auto-improve your agent

When the agent does something wrong, hand Claude Code the improvement prompt:

```
Run docs/improve-agent.md
```

The seven-step loop:

1. **Define test cases** — 3-5 inputs + expected behaviors.
2. **Run them against the live agent** via cURL.
3. **Read the result** — response + container logs (which tools fired, what the model thought).
4. **Edit the agent** — one file, surgical edits to instructions / tools / model.
5. **Hot-reload** picks up the change automatically.
6. **Re-run** the test cases. Compare.
7. **Iterate** until they pass.

Concrete example. The WebSearch Agent fails on "what changed in Anthropic's research this week?" — vague answer, no citations. Claude reads the logs, sees the agent called `web_search` once and stopped, never called `web_fetch`. Claude adds one sentence to the instructions ("on recent-events questions, follow up with at least one `web_fetch`"), hot-reloads, re-runs. Passes. One-line fix found by reading the actual behavior.

This loop only closes if the agent code, the live platform, and the iteration tool all live in one place. That's the point of owning the stack.

## Evals

Improve-agent is the fast iteration loop. Evals are the regression suite that runs the same prompts against your agents on a schedule and tells you when behavior drifts.

The eval surface is two files: [`evals/cases.py`](evals/cases.py) (declarative cases) and [`evals/__main__.py`](evals/__main__.py) (runner). Each case binds an input to an agent and uses agno's built-in [`AccuracyEval`](https://docs.agno.com/evals/accuracy) (LLM judge against an expected-output rubric) and/or [`ReliabilityEval`](https://docs.agno.com/evals/reliability) (tool-call assertion). No custom DSL, no separate harness — agno's primitives directly.

```bash
python -m evals                # run the suite
python -m evals --case <name>  # run one case
```

Results log to Postgres via `db=eval_db` — connect your AgentOS at [os.agno.com](https://os.agno.com) to see eval history over time. Hand Claude Code [`docs/run-evals.md`](docs/run-evals.md) to run the suite, diagnose failures, and fix in scope.

## Going beyond agents

For most things one agent is enough. When it isn't:

- **[Multi-agent teams](https://docs.agno.com/teams/overview)** — coordinate (a leader plans + synthesizes), route (a router picks the right specialist), or broadcast (run everyone in parallel). Use when the right specialist isn't known up front.
- **[Agentic workflows](https://docs.agno.com/workflows/overview)** — deterministic step-by-step pipelines. Use when a process needs to run the same way every time.

Rule of thumb: agents for open questions, teams for routing, workflows for processes.

## Scheduled tasks

`scheduler=True` is on in [`app/main.py`](app/main.py). Schedule any agent or workflow on a cron:

- **Maintenance** — purge sessions older than 90 days; vacuum tables.
- **Proactive runs** — every weekday morning, summarize overnight news for your portfolio. Send to Slack.
- **Periodic re-evaluation** — schedule `python -m evals` weekly to catch behavior drift before users do.

See [agno scheduler docs](https://docs.agno.com/agent-os/scheduler) for the cron API.

---

## Step 5: Run on Railway

Requires the [Railway CLI](https://docs.railway.com/cli#installing-the-cli) and `railway login`.

### 5.1 Set up your production env

```sh
cp .env .env.production
# Edit .env.production with production values
```

The deploy scripts read `.env.production` first and fall back to `.env`. This lets you keep separate values for local and production: different OpenAI keys, production-only credentials, a different Slack workspace. `.env.production` is gitignored.

### 5.2 Deploy

```sh
./scripts/railway/up.sh
```

This provisions Postgres + the app service on the same private network.

### 5.3 Your first deploy will fail. That's expected.

Token-Based Authorization is ON by default. Without `JWT_VERIFICATION_KEY`, the app refuses to serve traffic — the platform's job is to keep your data off the public web.

Token-Based Auth gives you three things:

1. **No public access** — the server rejects requests without a valid token.
2. **Per-request identity** — middleware parses the token and injects `user_id`, `session_id`, and custom claims into your endpoints. Each request is tied to a user and session.
3. **Granular permissions** — user tokens can run an agent and view their own sessions; admin tokens read everyone's sessions and test any agent.

### 5.4 Get your verification key

1. Open [os.agno.com](https://os.agno.com), click **Add OS** → **Live**, enter your Railway domain, and connect.
2. Enable **Token Based Authorization**.
3. Paste the public key into `.env.production` (full PEM block, no surrounding quotes):

```sh
JWT_VERIFICATION_KEY=-----BEGIN PUBLIC KEY-----
MIIBIjANBgkq...
-----END PUBLIC KEY-----
```

> Live connections to AgentOS are paid. Use the `PLATFORM30` coupon code for a 1-month free trial. Remember to cancel before the trial ends if you don't want to be charged.

### 5.5 Sync env and verify

While you have `.env.production` open, point the in-cluster scheduler at your public Railway domain so cron triggers can reach AgentOS:

```sh
# .env.production
AGENTOS_URL=https://<your-app>.up.railway.app
```

Then push every variable to Railway:

```sh
./scripts/railway/env-sync.sh
```

Railway auto-deploys when env values change. Watch the logs and confirm the platform is serving:

```sh
railway logs --service agent-os
```

Once you see successful requests, AgentOS will connect through your Railway domain and you're live.

### 5.6 Redeploy after code changes

For one-off updates from your machine:

```sh
./scripts/railway/redeploy.sh
```

To auto-deploy on every push to `main`:

1. Open the Railway dashboard → your project → the agent-os service → **Settings**.
2. Under **Source**, click **Connect Repo** and pick your repo.
3. Set the deploy branch to `main`, save.

Push to `main` then triggers a build + rolling deploy. `./scripts/railway/env-sync.sh` is still how you sync env changes.

### Opting out of JWT (not recommended)

Set `authorization=False` in [`app/main.py`](app/main.py) and redeploy. Only inside a private VPC behind another auth layer. Without it, anyone who guesses your Railway domain can read your sessions and run your agents.

### Scaling

The default deploy is two replicas at 4Gi memory / 2 vCPU each (zero-downtime rolling deploys + basic fault tolerance). Bump `numReplicas` and `limits` in [`railway.json`](railway.json) as your usage grows.

---

## Connect to interfaces

The team uses agents where work happens — Slack, Discord, Telegram, custom UIs in your product.

**Slack** is pre-wired. Set `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` in your env, and the interface lights up automatically. See the [agno Slack interface docs](https://docs.agno.com/agent-os/interfaces/overview) for the Slack-side app setup.

For Discord, Telegram, WhatsApp, or a custom UI, the pattern is the same — mirror the Slack conditional in `app/main.py` with the relevant interface from agno. See the [agno interfaces guide](https://docs.agno.com/agent-os/interfaces/overview).

When the same person reaches your agent across surfaces — Slack today, web tomorrow — you'll want the agent to know it's the same user. The pattern: an identity table mapping `(surface, surface_user_id)` to a canonical `user_id`, resolved in your webhook handler before invoking the agent. This is left as an exercise.

## Add tools and MCP servers

The WebSearch agent in [`agents/web_search.py`](agents/web_search.py) shows the MCPTools pattern (URL + transport) — copy it to wire any MCP server. For built-in toolkits (Slack tools, Gmail, GitHub, Linear, etc.), see [agno tools](https://docs.agno.com/tools/toolkits).

---

## What you just built

A unified agent platform running securely in your cloud. Technical users on your team can create and deploy agents using Claude Code; non-technical users can use the no-code UI at os.agno.com. Sessions, traces, and knowledge live in your database. Your infrastructure is gated behind JWT-based RBAC and API keys are managed in one place.

You can run agents, route across teams, run deterministic workflows, schedule background tasks, auto-improve agents against test cases, and connect to any surface where work happens.

## Why control your data

Every interaction with your platform produces data — sessions, memory, knowledge, traces — and it all flows into your Postgres. Two reasons this matters:

1. **Compliance.** Customer data, proprietary code, and internal documents stay in your own database. The moment any of that touches a third-party trace tool or memory service, you've added a vendor to your security review.
2. **Iteration.** The improve-agent loop only closes because the trace data lives where the iteration tool can read it. Vendor-stitched stacks split this surface across three SaaS products and the loop never closes.

The agents you ship today are the smallest part of what you've built. The platform underneath them, and the iteration loop it enables, is the thing that compounds.

---

## Environment variables

`compose.yaml` sets the dev defaults (`RUNTIME_ENV=dev`, `AGNO_DEBUG=True`, `WAIT_FOR_DB=True`) so local Docker runs hot-reload and skips JWT. Production reads everything from `.env.production` via `./scripts/railway/env-sync.sh`.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | yes | — | OpenAI key for models + embeddings. |
| `RUNTIME_ENV` | no | `prd` | `dev` enables hot-reload and disables JWT. Compose sets this to `dev` for local. |
| `JWT_VERIFICATION_KEY` | prd | — | Public key from os.agno.com. Required when `RUNTIME_ENV=prd`. |
| `AGENTOS_URL` | no | `http://127.0.0.1:8000` | Scheduler base URL. Set to your Railway domain in production. |
| `PARALLEL_API_KEY` | no | — | Authenticates the WebSearch Agent's Parallel SDK / MCP connection. |
| `SLACK_BOT_TOKEN` / `SLACK_SIGNING_SECRET` | no | — | Both must be set to enable the Slack interface. |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASS` / `DB_DATABASE` | no | matches compose | Postgres connection. |
| `DB_DRIVER` | no | `postgresql+psycopg` | SQLAlchemy driver. |
| `PORT` | no | `8000` | API server port. |
| `AGNO_DEBUG` | no | `False` | If `True`, agno emits verbose debug logs. Compose sets this for dev. |
| `WAIT_FOR_DB` | no | `False` | If `True`, the entrypoint blocks on the DB before starting. Compose sets this. |

## Learn more

- [Agno documentation](https://docs.agno.com)
- [AgentOS introduction](https://docs.agno.com/agent-os/introduction)
- [Agno Discord](https://agno.com/discord)

---

*AgentOS is open-source — you don't have to use the os.agno.com UI if you don't want to.*
