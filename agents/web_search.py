"""
WebSearch Agent
===============

This agent searches the web for current information. It supports two
backends depending on whether a Parallel API key is available:

  • With PARALLEL_API_KEY — uses the official Parallel SDK, which gives
    the agent `parallel_search` and `parallel_extract` tools directly.
  • Without a key — falls back to a keyless MCP endpoint, which gives
    the agent `web_search` and `web_fetch` tools instead.

Both paths produce the same user experience; the key just raises the
rate ceiling and unlocks richer extraction.
"""

# getenv reads environment variables. Used here to check whether a
# Parallel API key has been configured.
from os import getenv

# Agent is the core class from Agno. Every agent you create is an
# instance of this class — it bundles a model, tools, instructions,
# and persistence into one object.
from agno.agent import Agent

# MCPTools lets an agent call an external MCP (Model Context Protocol)
# server. MCP is a protocol for exposing tools over HTTP — the agent
# doesn't need to know how the tool works internally, just that it can
# call it. Used here for the keyless fallback path.
from agno.tools.mcp import MCPTools

# ParallelTools is the official SDK for Parallel's web search API.
# When PARALLEL_API_KEY is set, this gives the agent direct access to
# `parallel_search` and `parallel_extract` without going through MCP.
from agno.tools.parallel import ParallelTools

# default_model() is our project-wide factory that returns a fresh model
# instance. We use it everywhere so changing the model is a one-line edit.
from app.settings import default_model

# get_db() returns the database backend (Postgres or SQLite) that stores
# agent sessions, memory, and metrics. Every agent needs one.
from db import get_db

# ── Tool selection ────────────────────────────────────────────────────
# When PARALLEL_API_KEY is set, use the official parallel-web SDK —
# the agent gets `parallel_search` and `parallel_extract` directly.
# Without a key, fall back to the keyless MCP endpoint and the agent
# gets `web_search` and `web_fetch` instead. AgentOS handles MCP
# connect/close as part of its lifespan.
#
#   ParallelTools()  — no args needed; it reads PARALLEL_API_KEY from
#                      the environment automatically.
#   MCPTools(...)    — connects to Parallel's public MCP server.
#                      "streamable-http" streams responses over HTTP
#                      for better responsiveness.
if getenv("PARALLEL_API_KEY"):
    web_tools: ParallelTools | MCPTools = ParallelTools()
else:
    web_tools = MCPTools(
        url="https://search.parallel.ai/mcp", transport="streamable-http"
    )


WEB_SEARCH_INSTRUCTIONS = """\
Search the web for current information.

Workflow:
1. Use the search tool to find candidate sources for the question.
2. For recent-event, “latest,” or “recently” questions, answer only from search results you actually found in this run; do not infer newer publications, titles, or dates beyond what the results support.
3. When the user asks about specific pages, or when search snippets are too thin to safely summarize a recent claim, follow up with the extract / fetch tool to read the most relevant URLs before answering.
4. Cite the sources you used as plain URLs. Prefer recent, authoritative pages. If you cannot find a good answer, say so plainly.
"""


web_search = Agent(
    id="web-search",
    name="WebSearch",
    model=default_model(),
    db=get_db(),
    tools=[web_tools],
    instructions=WEB_SEARCH_INSTRUCTIONS,
    enable_agentic_memory=True,
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
)
