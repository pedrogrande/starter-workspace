"""
Agno Support Agent
==================
"""

from agno.agent import Agent
from agno.tools.mcp import MCPTools

from app.settings import default_model
from db import get_postgres_db

# Keyless MCP endpoint serving the Agno docs. AgentOS handles the
# connect/close lifecycle as part of its lifespan hook.
mcp_tools = MCPTools(transport="streamable-http", url="https://docs.agno.com/mcp")


INSTRUCTIONS = """\
You answer questions about the Agno framework and AgentOS. Use the
Agno docs MCP tool to look up authoritative information before
answering — quote real doc paths and code snippets from the results,
never guess. Cite the docs pages you used as plain URLs. If a question
is off-topic or not covered by the Agno docs, say so plainly and
offer to take an Agno-related question instead.
"""


agno_support_agent = Agent(
    id="agno-support-agent",
    name="Agno Support Agent",
    model=default_model(),
    db=get_postgres_db(),
    tools=[mcp_tools],
    instructions=INSTRUCTIONS,
    tool_call_limit=10,
    enable_agentic_memory=True,
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=3,
    markdown=True,
)
