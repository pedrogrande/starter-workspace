"""
AgentOS Entrypoint
==================
"""

from contextlib import asynccontextmanager
from os import getenv
from pathlib import Path

from agno.os import AgentOS
from agno.registry import Registry
from agno.tools.mcp import MCPTools
from agno.tools.parallel import ParallelTools
from agno.utils.log import log_error, log_info

from agents.agno_support import agno_support_agent
from agents.code_search import code_search
from agents.web_search import web_search
from app.settings import default_model
from db import create_knowledge, get_db
from teams.engineering_team import engineering_team

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
runtime_env = getenv("RUNTIME_ENV", "prd")
scheduler_base_url = getenv("AGENTOS_URL", "http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# Interfaces
# - The CodeSearch agent becomes available on Slack when both env vars are set
# ---------------------------------------------------------------------------
SLACK_BOT_TOKEN = getenv("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = getenv("SLACK_SIGNING_SECRET", "")

interfaces: list = []
if SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET:
    from agno.os.interfaces.slack import Slack

    interfaces.append(
        Slack(
            agent=code_search,
            streaming=True,
            token=SLACK_BOT_TOKEN,
            signing_secret=SLACK_SIGNING_SECRET,
            resolve_user_identity=True,
        )
    )


# ---------------------------------------------------------------------------
# Lifespan — extension hook for app-level startup / teardown.
#
# AgentOS handles the MCP lifecycle (connect on startup, close on shutdown).
# Keep this hook in place so you can plug in your own setup as needed.
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app):  # type: ignore[no-untyped-def]
    log_info("AgentOS lifespan: startup")
    try:
        yield
    except Exception as e:
        log_error(f"AgentOS lifespan error: {e}")
        raise
    finally:
        log_info("AgentOS lifespan: shutdown")


# ---------------------------------------------------------------------------
# Studio Registry
#
# The Registry exposes tools, models, databases, and knowledge bases to the
# AgentOS Studio (os.agno.com). Students can build agents visually in the
# Studio by selecting from these registered components — no code needed.
#
# When a student creates an agent in the Studio, they pick a model, tools,
# and optionally a knowledge base from the Registry. The Studio serializes
# the agent definition and sends it to AgentOS, which instantiates it at
# runtime using the registered components.
#
# To add a new tool or model to the Studio, register it here. The component
# appears in the Studio's component picker immediately after restart.
# ---------------------------------------------------------------------------

# Tools available in the Studio — students can add these to their agents
studio_tools = []
if getenv("PARALLEL_API_KEY"):
    studio_tools.append(ParallelTools())
else:
    studio_tools.append(
        MCPTools(url="https://search.parallel.ai/mcp", transport="streamable-http")
    )
# Agno docs MCP — lets Studio-built agents search Agno documentation
studio_tools.append(
    MCPTools(transport="streamable-http", url="https://docs.agno.com/mcp")
)

# Models available in the Studio
studio_models = [default_model()]

# Databases available in the Studio
studio_dbs = [get_db()]

# Pre-built knowledge bases students can attach to their agents
studio_knowledge = [
    create_knowledge("Studio Knowledge", "studio_knowledge"),
]

registry = Registry(
    name="Course Registry",
    tools=studio_tools,
    models=studio_models,
    dbs=studio_dbs,
    knowledge=studio_knowledge,
)


# ---------------------------------------------------------------------------
# Create AgentOS
# ---------------------------------------------------------------------------
agent_os = AgentOS(
    name="AgentOS",
    tracing=getenv("AGNO_TRACING", "false").lower() == "true",
    scheduler=True,
    scheduler_base_url=scheduler_base_url,
    authorization=runtime_env == "prd",
    lifespan=lifespan,
    db=get_db(),
    agents=[web_search, code_search, agno_support_agent],
    teams=[engineering_team],
    interfaces=interfaces,
    registry=registry,
    config=str(Path(__file__).parent / "config.yaml"),
)
app = agent_os.get_app()


if __name__ == "__main__":
    agent_os.serve(app="app.main:app", reload=runtime_env == "dev")
