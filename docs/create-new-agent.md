# Create a New Agent

> Claude Code prompt. Open Claude Code in this repo and paste:
> `Run docs/create-new-agent.md`

You are creating a new agent in this AgentOS template. The user already has the platform running locally on `http://localhost:8000` with hot-reload enabled (`RUNTIME_ENV=dev`). Edits to `agents/`, `app/`, and `db/` reload uvicorn within ~1s — no restart needed unless you change dependencies.

## 0. Preconditions

- `agentos-api` container is up: `docker compose ps` should show it running.
- `curl -sSf http://localhost:8000/health` returns 200.

If either is missing, ask the user to run `docker compose up -d --build` and wait for it to come up.

## 1. Ask the user

**How to ask:** Use the `AskUserQuestion` tool for choice-shaped prompts — the branching opener, the role pick, the systems multiselect, the agent-idea suggestions, and the **Pattern** pick are all good fits. It renders click-to-select buttons, much smoother than parsing free-text replies. Use plain prompts only for free-form fields (the recurring-task description, the slug).

Open with a single branching question — don't dump five questions at once:

> Do you have an agent in mind, or would you like a guided experience?

If the user immediately describes a concrete agent ("build me a GitHub PR reviewer"), they've picked the second branch — skip to **Specifics**.

### Guided experience

Ask three light discovery questions in one message:

- What's your role? (engineer, PM, founder, analyst, ops, …)
- What's a recurring task that takes you real time?
- Which systems do you live in day-to-day? (Slack, GitHub, Linear, Notion, your own DB, …)

Use the answers + the `agno-docs` MCP (configured in [`.mcp.json`](../.mcp.json)) to surface **3-5 concrete agent ideas** grounded in real agno toolkits. For each suggestion: a short name, a one-sentence purpose, and the toolkit(s) it would use.

Common starting points: GitHub PR reviewer, Linear triager, knowledge-base Q&A over a `docs/` folder, Slack on-call digest, market-scan / web research.

Once the user picks one, you have name, purpose, and tools settled — only ask for what's still unknown under **Specifics**.

### Specifics

Ask, in one consolidated message:

1. **Name and purpose** — what should this agent do? One sentence.
2. **Pattern** — does it use:
   - **Direct tools** (like the WebSearch Agent's raw `MCPTools`)? Best when the user knows exactly what tools the agent needs and wants them visible on the agent.
   - **A context provider** (like the CodeSearch Agent's `WorkspaceContextProvider`)? Best when the agent should query a single information source through one `query_<thing>` tool.
3. **Tools / sources** — which MCP servers, toolkits, or context providers? URL of the MCP server if any. (Default: nothing — just chat.)
4. **Model** — default is `gpt-5.4` via `app.settings.default_model()`. Override only if the user asks.
5. **Slug** — short kebab-case id (e.g. `linear-agent`). Used as the agent's `id`, in URLs, and in `app/config.yaml`.

Skip any item the guided path already settled. Propose sensible defaults for **Pattern** and **Slug** when you can — don't make the user re-answer questions.

## 2. Ground the design in agno docs

If the user named any specific toolkit, MCP server, or integration the agent should use (Linear, Stripe, GitHub, Anthropic Claude, etc.), search agno docs **before** writing code:

- Preferred: the `agno-docs` MCP server (configured in [`.mcp.json`](../.mcp.json)) — search for the toolkit / integration name and read the relevant page(s).
- Fallback: fetch <https://docs.agno.com/llms.txt> and search inline for the relevant sections.

Use what you find to ground the `tools=[…]` list in the real agno API — correct import path, constructor args, required env vars. Don't guess. Skip this step if the agent is chat-only with no tools.

## 3. Generate the agent file

Create `agents/<slug>.py` (replacing `-` with `_` for the filename: `agents/linear_agent.py`). Follow the pattern of one of the two reference agents:

- **Direct tools** → mirror [`agents/web_search.py`](../agents/web_search.py).
- **Context provider** → mirror [`agents/code_search.py`](../agents/code_search.py).

Required structure:

```python
"""
<Title>
=======
"""

from agno.agent import Agent

from app.settings import default_model
from db import get_postgres_db

INSTRUCTIONS = """\
<one short paragraph describing the agent's job, tools, and the rules
it should follow when answering>
"""

<slug_underscore> = Agent(
    id="<slug>",
    name="<DisplayName>",
    model=default_model(),
    db=get_postgres_db(),
    tools=[...],                     # or context_provider.get_tools()
    instructions=INSTRUCTIONS,
    enable_agentic_memory=True,
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
)
```

Notes:

- Don't add a `if __name__ == "__main__":` smoke block — the platform-driven workflow is the smoke test.
- If the agent uses an `MCPTools` instance, pass it through `tools=[mcp_tools]` directly. AgentOS connects/closes MCP servers automatically — don't manage the lifecycle yourself.
- If a context provider needs a model, reuse `default_model()` so the model id stays in one place.

## 4. Register in `app/main.py`

Add the import and append to the `agents=[…]` list:

```python
from agents.<slug_underscore> import <slug_underscore>

agent_os = AgentOS(
    ...
    agents=[web_search, code_search, <slug_underscore>],
    ...
)
```

## 5. Quick prompts

Add three suggested prompts to [`app/config.yaml`](../app/config.yaml) under `chat.quick_prompts`, keyed by the agent's `id`:

```yaml
chat:
  quick_prompts:
    <slug>:
      - "First example prompt"
      - "Second example prompt"
      - "Third example prompt"
```

## 6. Dependencies (only if needed)

If the agent imports a new package (e.g. `from anthropic import …` for a Claude tool), add it to the `dependencies` list in [`pyproject.toml`](../pyproject.toml), then regenerate the lockfile:

```bash
./scripts/generate_requirements.sh
```

Then rebuild the container:

```bash
docker compose up -d --build
```

If no new dependency was added, hot-reload will pick the new agent up automatically — no rebuild needed.

## 7. Smoke test

Wait ~2 seconds for hot-reload, then probe the agent via cURL:

```bash
curl -sS -X POST http://localhost:8000/agents/<slug>/runs \
  -F "message=<a representative question for this agent>" \
  -F "user_id=claude-create-agent" \
  -F "stream=false" \
  -o /tmp/agent-out.json \
  -w "HTTP %{http_code} in %{time_total}s\n"

jq -r '.content // .' < /tmp/agent-out.json
```

Check the container logs to see which tools fired:

```bash
docker logs agentos-api --since 30s 2>&1 | grep -E "Tool Calls|Running:|Error" | head -40
```

## 8. If the smoke test fails

- **HTTP 404** — the agent isn't registered. Re-check Step 4.
- **HTTP 5xx** — read `docker logs agentos-api --tail 50` for the traceback. Most failures are import errors, missing env vars, or a typo in the agent's `tools=` list.
- **Empty response** — check the logs for tool call errors (rate limits, missing API keys, MCP server unreachable). Surface the issue to the user; don't paper over it.
- **Tool not firing when expected** — the instruction prompt isn't strong enough. Tell the user; suggest tightening or running `docs/improve-agent.md` once the agent is loaded.

Iterate at most 2-3 times on the prompt before stopping and surfacing the question to the user.

## 9. Done

When the smoke test passes:

1. Tell the user the agent's slug and the URL: `https://os.agno.com` (their already-connected OS) — they can chat with the new agent immediately.
2. Mention `docs/improve-agent.md` for the next-step iteration loop if behavior needs tuning.

A simple agent usually takes 5-10 minutes from "Run docs/create-new-agent.md" to working. More if the user asks for custom tools or an MCP server with auth.
