"""
Engineering Leadership Team
============================

A team that coordinates a project manager and a technical lead
to handle engineering planning, review, and decision-making.
"""

from agno.agent import Agent
from agno.learn import (
    DecisionLogConfig,
    EntityMemoryConfig,
    LearnedKnowledgeConfig,
    LearningMachine,
    LearningMode,
    SessionContextConfig,
    UserMemoryConfig,
    UserProfileConfig,
)
from agno.team import Team
from agno.team.mode import TeamMode

from agents.agno_support import agno_support_agent
from agents.code_search import code_search
from agents.web_search import web_search
from app.settings import default_model
from db import create_knowledge, get_postgres_db

# ---------------------------------------------------------------------------
# Team Members
# ---------------------------------------------------------------------------

project_manager = Agent(
    id="project-manager",
    name="Project Manager",
    model=default_model(),
    db=get_postgres_db(),
    instructions="""\
You are a project manager on the Engineering Leadership team.
Focus on scope, timelines, priorities, and stakeholder communication.
Delegate technical questions to the Technical Lead when appropriate.
Use the web search tool when you need current information about
technologies, libraries, or industry trends.
""",
    tools=[web_search],  # type: ignore[list-item]
    add_history_to_context=True,
    num_history_runs=3,
    markdown=True,
)

technical_lead = Agent(
    id="technical-lead",
    name="Technical Lead",
    model=default_model(),
    db=get_postgres_db(),
    instructions="""\
You are a technical lead on the Engineering Leadership team.
Focus on architecture, code quality, technical feasibility, and
implementation details. Delegate broad research to the Project Manager
when appropriate. Use the code search tool when you need to inspect
the codebase.
""",
    tools=[code_search],  # type: ignore[list-item]
    add_history_to_context=True,
    num_history_runs=3,
    markdown=True,
)

# ---------------------------------------------------------------------------
# Knowledge — uses the project's shared Postgres + PgVector infrastructure
# ---------------------------------------------------------------------------

knowledge = create_knowledge(
    name="Engineering Learnings",
    table_name="engineering_learnings",
)

# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------

engineering_team = Team(
    id="engineering-leadership",
    name="Engineering Leadership",
    mode=TeamMode.coordinate,
    model=default_model(),
    members=[
        project_manager,
        technical_lead,
        web_search,
        code_search,
        agno_support_agent,
    ],
    db=get_postgres_db(),
    instructions="""\
You are an Engineering Leadership team. Coordinate between your
members to provide comprehensive answers that address both
organizational and technical concerns:

- Project Manager — scope, timelines, priorities, stakeholder communication.
- Technical Lead — architecture, code quality, technical feasibility.
- WebSearch — current information from the web on technologies, libraries, and industry trends.
- CodeSearch — answers about this project's own codebase (file paths, line numbers, structure).
- Agno Support Agent — questions about the Agno framework and AgentOS, sourced from the Agno docs.

Delegate to the member best suited for the question. Prefer specific,
cited answers over generalities.
""",
    tool_call_limit=15,
    learning=LearningMachine(
        # Who the user is — always capture automatically
        user_profile=UserProfileConfig(mode=LearningMode.ALWAYS),
        # Unstructured preferences — always capture
        user_memory=UserMemoryConfig(mode=LearningMode.ALWAYS),
        # Track session goals and progress
        session_context=SessionContextConfig(enable_planning=True),
        # Track projects, people, companies — shared across the team
        entity_memory=EntityMemoryConfig(
            mode=LearningMode.ALWAYS,
            namespace="engineering",
        ),
        # Agent decides what insights are worth saving for the org
        learned_knowledge=LearnedKnowledgeConfig(
            mode=LearningMode.AGENTIC,
        ),
        knowledge=knowledge,
        # Agent logs significant decisions (with reasoning and alternatives)
        decision_log=DecisionLogConfig(mode=LearningMode.AGENTIC),
    ),
    markdown=True,
)
