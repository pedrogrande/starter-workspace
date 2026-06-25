"""
Studio Registry
===============

The Registry exposes tools, models, databases, and knowledge bases to the
AgentOS Studio (os.agno.com). Students can build agents visually in the
Studio by selecting from these registered components — no code needed.

When a student creates an agent in the Studio, they pick a model, tools,
and optionally a knowledge base from the Registry. The Studio serializes
the agent definition and sends it to AgentOS, which instantiates it at
runtime using the registered components.

To add a new tool or model to the Studio, add it to the appropriate list
below. The component appears in the Studio's component picker immediately
after restart (``./scripts/restart-api.sh``).

Docs: https://docs.agno.com/agent-os/studio/registry
"""

from os import getenv

from agno.registry import Registry
from agno.tools.mcp import MCPTools
from agno.tools.parallel import ParallelTools

from app.settings import default_model
from db import create_knowledge, get_db


def build_registry() -> Registry:
    """Build the Studio Registry with available tools, models, and databases.

    Called once at app startup from ``app/main.py``. The returned Registry
    is passed to ``AgentOS(registry=...)`` which exposes the ``GET /registry``
    endpoint that the Studio reads.
    """
    # ── Tools ──────────────────────────────────────────────────────────
    # Tools available in the Studio — students can add these to their agents.
    tools = []

    # Web search: Parallel SDK if key is set, otherwise keyless MCP endpoint
    if getenv("PARALLEL_API_KEY"):
        tools.append(ParallelTools())
    else:
        tools.append(
            MCPTools(
                url="https://search.parallel.ai/mcp",
                transport="streamable-http",
            )
        )

    # Agno docs MCP — lets Studio-built agents search Agno documentation
    tools.append(
        MCPTools(transport="streamable-http", url="https://docs.agno.com/mcp")
    )

    # ── Models ─────────────────────────────────────────────────────────
    # Models available in the Studio. Add more providers here (Anthropic,
    # Google, OpenAI, etc.) — see docs/using-different-models.md.
    models = [default_model()]

    # ── Databases ──────────────────────────────────────────────────────
    # Databases available in the Studio for agent persistence.
    dbs = [get_db()]

    # ── Knowledge Bases ────────────────────────────────────────────────
    # Pre-built knowledge bases students can attach to their agents.
    # Each gets its own PgVector table for hybrid search.
    knowledge = [
        create_knowledge("Studio Knowledge", "studio_knowledge"),
    ]

    return Registry(
        name="Course Registry",
        tools=tools,
        models=models,
        dbs=dbs,
        knowledge=knowledge,
    )