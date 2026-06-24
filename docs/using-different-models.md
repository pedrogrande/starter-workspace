# Using Different Model Providers

> How to use Anthropic, Google, OpenAI, Groq, or any other provider in your agents.

The platform defaults to `Ollama(id="glm-5.1:cloud")` via `app.settings.default_model()`. The `OLLAMA_API_KEY` and `OPENAI_API_KEY` are pre-filled in the workspace environment. For any other provider, you need to install the package and provide your own API key.

## Quick reference

| Provider | pip package | Model class | Env var | Example model ID |
|---|---|---|---|---|
| Ollama (cloud) | built-in | `Ollama` | `OLLAMA_API_KEY` (pre-filled) | `glm-5.1:cloud` |
| OpenAI | `openai` | `OpenAIChat` | `OPENAI_API_KEY` (pre-filled) | `gpt-4o` |
| Anthropic | `anthropic` | `Claude` | `ANTHROPIC_API_KEY` | `claude-sonnet-4-20250514` |
| Google Gemini | `google-generativeai` | `Gemini` | `GOOGLE_API_KEY` | `gemini-2.0-flash` |
| Groq | `groq` | `Groq` | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| Mistral | `mistralai` | `Mistral` | `MISTRAL_API_KEY` | `mistral-large-latest` |
| Cohere | `cohere` | `Cohere` | `COHERE_API_KEY` | `command-r-plus` |
| Together | `together` | `Together` | `TOGETHER_API_KEY` | `meta.llama/Meta-Llama-3.1-70B-Instruct-Turbo` |
| AWS Bedrock | `boto3` | `AwsBedrock` | AWS credentials | `anthropic.claude-3-sonnet-20240229-v1:0` |
| Azure OpenAI | `openai` | `AzureOpenAI` | `AZURE_OPENAI_API_KEY` | your deployment name |

Full list: [Agno model providers](https://docs.agno.com/models)

---

## Step-by-step: Add Anthropic Claude to an agent

### 1. Install the provider package

```bash
# In the workspace terminal
uv pip install anthropic --system
echo "anthropic" >> requirements.txt
```

Adding it to `requirements.txt` ensures it survives a workspace restart (the startup script runs `uv pip sync requirements.txt --system`).

### 2. Set your API key

Get an Anthropic API key at <https://console.anthropic.com/settings/keys>.

Store it in `/app/data/.env` — this is on the persistent Docker volume, so it survives workspace stop/start:

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-your-key-here' >> /app/data/.env
```

The app loads `.env` files via `evals/dotenv.py` at startup. But `/app/data/.env` isn't loaded automatically — you need to either:

**Option A:** Symlink it to `/app/.env` (simplest):

```bash
ln -sf /app/data/.env /app/.env
```

**Option B:** Export it in your shell before starting the API:

```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

This only lasts for the current shell session — use Option A for persistence.

### 3. Use the model in your agent

Edit your agent file (e.g., `agents/my_agent.py`):

```python
"""
My Agent
=======
"""

from agno.agent import Agent
from agno.models.anthropic import Claude

from db import get_db

INSTRUCTIONS = """\
You are a helpful assistant. Answer questions clearly and concisely.
"""

my_agent = Agent(
    id="my-agent",
    name="My Agent",
    model=Claude(id="claude-sonnet-4-20250514"),  # ← Anthropic model
    db=get_db(),
    instructions=INSTRUCTIONS,
    enable_agentic_memory=True,
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
)
```

### 4. Register and restart

If this is a **new** agent file, register it in `app/main.py`:

```python
from agents.my_agent import my_agent

agent_os = AgentOS(
    ...
    agents=[web_search, code_search, my_agent],
    ...
)
```

Then restart the API:

```bash
./scripts/restart-api.sh
```

If you only **edited** an existing agent file (swapped the model), hot-reload picks it up — no restart needed.

### 5. Verify

```bash
curl -s http://localhost:8000/agents | jq -r '.[].id' | grep my-agent
```

Then chat with the agent through Agent-UI or via cURL:

```bash
curl -sS -X POST http://localhost:8000/agents/my-agent/runs \
  -F "message=Hello, what model are you?" \
  -F "stream=false" | jq -r '.content'
```

---

## Using a different model for just one agent

You don't have to change the default model. Each agent can use a different provider:

```python
from agno.models.anthropic import Claude
from agno.models.openai import OpenAIChat
from agno.models.ollama import Ollama
from app.settings import default_model

# Agent 1 — uses the default (Ollama Cloud)
agent_one = Agent(model=default_model(), ...)

# Agent 2 — uses Anthropic
agent_two = Agent(model=Claude(id="claude-sonnet-4-20250514"), ...)

# Agent 3 — uses OpenAI
agent_three = Agent(model=OpenAIChat(id="gpt-4o"), ...)
```

Each provider reads its own env var (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.), so you can mix providers in the same platform.

---

## Using a different model for the whole platform

To change the default for all agents, edit `app/settings.py`:

```python
from agno.models.anthropic import Claude

def default_model() -> Claude:
    return Claude(id="claude-sonnet-4-20250514")
```

Hot-reload picks this up — all agents using `default_model()` will switch on the next request.

---

## Storing API keys securely

| Location | Persists across restart? | In git? | Notes |
|---|---|---|---|
| `/app/data/.env` + symlink to `/app/.env` | ✅ (on volume) | ❌ (gitignored) | **Recommended** |
| `/app/.env` directly | ❌ (overwritten by `git pull`) | ❌ | Lost on workspace restart |
| Shell `export` | ❌ (session only) | ❌ | Good for quick testing |
| Coder user secrets | ✅ | ❌ | See [Coder user secrets](https://coder.com/docs/user-guides/user-secrets) |

### Recommended: `/app/data/.env` with symlink

```bash
# One-time setup (persists across workspace restarts)
echo 'ANTHROPIC_API_KEY=sk-ant-your-key' >> /app/data/.env
echo 'GOOGLE_API_KEY=your-key' >> /app/data/.env
ln -sf /app/data/.env /app/.env
```

The symlink ensures the app picks up the keys. The file is on the persistent volume, so it survives stop/start. It's gitignored, so it never gets committed.

### Alternative: Coder user secrets

If you prefer not to have keys in files, use Coder's user secrets (Beta):

```bash
# From your local machine (authenticated with Coder)
echo -n "sk-ant-your-key" | coder secret create anthropic-key --env ANTHROPIC_API_KEY
```

The key is injected as an environment variable on the next workspace start. See the [Coder user secrets guide](https://coder.com/docs/user-guides/user-secrets) for details.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'anthropic'`**
→ You forgot to install the package: `uv pip install anthropic --system`

**`AuthenticationError` / `401`**
→ The API key isn't set or is wrong. Check: `echo $ANTHROPIC_API_KEY`

**`RateLimitError` / `429`**
→ You've hit the provider's rate limit. Wait and retry, or upgrade your plan.

**Model not showing in Agent-UI dropdown**
→ You added a new agent file but didn't restart: `./scripts/restart-api.sh`

**Key lost after workspace restart**
→ You put the key in `/app/.env` (overwritten by `git pull`). Move it to `/app/data/.env` and symlink: `ln -sf /app/data/.env /app/.env`

---

## Pre-filled vs student-provided keys

| Key | Who provides it | How |
|---|---|---|
| `OPENAI_API_KEY` | Course (pre-filled) | `TF_VAR_openai_api_key` on the VPS |
| `OLLAMA_API_KEY` | Course (pre-filled) | `TF_VAR_ollama_api_key` on the VPS |
| `ANTHROPIC_API_KEY` | Student | `/app/data/.env` or Coder user secret |
| `GOOGLE_API_KEY` | Student | `/app/data/.env` or Coder user secret |
| Any other provider | Student | `/app/data/.env` or Coder user secret |

The course provides OpenAI (for embeddings) and Ollama (for the default model). Any additional providers are student-managed — they bring their own keys and manage their own costs.

---

**Docs:** [Agno models](https://docs.agno.com/models) — full list of supported providers and model IDs.