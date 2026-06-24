"""
Agno Support Agent
==================

This agent answers questions about the Agno framework and AgentOS.
It uses an MCP (Model Context Protocol) tool to look up real documentation
before answering — so it never guesses, it cites.
"""

# Agent is the core class from Agno. Every agent you create is an instance
# of this class. It bundles a model, tools, instructions, and persistence.
from agno.agent import Agent

# MCPTools lets an agent call an external MCP server. MCP is a protocol
# for exposing tools over HTTP — the agent doesn't need to know how the
# tool works internally, just that it can call it.
from agno.tools.mcp import MCPTools

# default_model() is our project-wide factory that returns a fresh model
# instance. We use it everywhere so changing the model is a one-line edit.
from app.settings import default_model

# get_db() returns the database backend (Postgres or SQLite) that stores
# agent sessions, memory, and metrics. Every agent needs one.
from db import get_db

# MCPTools can connect to any MCP-compatible server. Here we point it at
# the Agno docs server, which exposes search tools the agent can call.
# "streamable-http" is the transport — it streams responses over HTTP,
# which is more responsive than waiting for the full response at once.
# AgentOS handles the connect/close lifecycle as part of its lifespan hook,
# so we don't need to manage it manually.
mcp_tools = MCPTools(transport="streamable-http", url="https://docs.agno.com/mcp")


INSTRUCTIONS = """\
You answer questions about the Agno framework and AgentOS. Use the
Agno docs MCP tool to look up authoritative information before
answering — quote real doc paths and code snippets from the results,
never guess. Cite the docs pages you used as plain URLs. If a question
is off-topic or not covered by the Agno docs, say so plainly and
offer to take an Agno-related question instead.
"""


# ── Agent definition ──────────────────────────────────────────────────
# This is where the agent is assembled. Each parameter controls a
# different aspect of the agent's behaviour:
#
#   id              — unique identifier used in URLs, logs, and the
#                    AgentOS dashboard. Must be URL-safe (kebab-case).
#   name            — human-readable name shown in the UI.
#   model           — the LLM that powers the agent. default_model()
#                    returns a fresh Ollama instance so agents don't
#                    share mutable state.
#   db              — where sessions, memory, and metrics are stored.
#                    get_db() picks Postgres or SQLite based on env.
#   tools           — list of tools the agent can call. Here it's just
#                    the MCP connection to the Agno docs server.
#   instructions    — the system prompt that tells the agent how to
#                    behave. This is the single most important lever
#                    for shaping agent behaviour.
#   tool_call_limit — maximum number of tool calls in a single run.
#                    Prevents runaway loops (e.g., the agent keeps
#                    searching forever). 10 is generous for a docs
#                    lookup agent.
#   enable_agentic_memory
#                    — lets the agent remember facts across sessions.
#                    Without this, every conversation starts from
#                    scratch.
#   add_datetime_to_context
#                    — injects the current date/time into the system
#                    prompt so the agent knows "today".
#   add_history_to_context
#                    — includes previous conversation turns in the
#                    prompt so the agent can refer back to earlier
#                    messages.
#   num_history_runs — how many past runs (full conversations) to
#                    include. 3 means the agent sees the last 3
#                    complete sessions.
#   markdown        — tells the agent to format its responses in
#                    Markdown, which renders nicely in the UI.
agno_support_agent = Agent(
    id="agno-support-agent",
    name="Agno Support Agent",
    model=default_model(),
    db=get_db(),
    tools=[mcp_tools],
    instructions=INSTRUCTIONS,
    tool_call_limit=10,
    enable_agentic_memory=True,
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=3,
    markdown=True,
)
