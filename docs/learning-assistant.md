# Learning Assistant

---

## Phased Implementation Plan

Seven phases. Each phase adds one layer, is independently testable, and leaves you with a working agent you can interact with before moving on.

The guiding principle throughout: **start simple, layer in functionality as needed** ([/agents/building-agents](https://docs.agno.com/agents/building-agents)).

---

### Phase 0 — Project Skeleton & Database

**Goal**: Get a running agent with database persistence and basic conversation history. No learning features yet. This is your baseline.

**What you build**:

```python
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from app.settings import default_model
from dataclasses import dataclass, field
from typing import Optional
from agno.learn import LearningMachine, UserProfileConfig, SessionContextConfig
from agno.learn.schemas import UserProfile

# In the Coder workspace, DATA_DIR is set to /app/data (persistent volume)
from os import getenv
from pathlib import Path

data_dir = Path(getenv("DATA_DIR", "data")).resolve()
data_dir.mkdir(parents=True, exist_ok=True)
mentor_db = SqliteDb(db_file=str(data_dir / "mentor.db"))

@dataclass
class LearnerProfile(UserProfile):
    background: Optional[str] = field(
        default=None,
        metadata={"description": "Professional or academic background"}
    )
    experience_level: Optional[str] = field(
        default=None,
        metadata={"description": "Overall level: beginner | intermediate | advanced"}
    )
    learning_goals: Optional[str] = field(
        default=None,
        metadata={"description": "What the learner wants to achieve"}
    )
    preferred_specialisation: Optional[str] = field(
        default=None,
        metadata={"description": "Chosen specialisation pathway, if any"}
    )
    preferred_learning_style: Optional[str] = field(
        default=None,
        metadata={"description": "How the learner prefers to learn: visual | hands-on | reading | project-based"}
    )
    available_time: Optional[str] = field(
        default=None,
        metadata={"description": "Time available for learning per week, e.g. '5 hours/week'"}
    )
    timeline: Optional[str] = field(
        default=None,
        metadata={"description": "Target completion timeframe, e.g. '6 months'"}
    )
    current_skills: Optional[str] = field(
        default=None,
        metadata={"description": "Skills the learner already has in this field"}
    )

mentor_agent = Agent(
    model=default_model(),
    db=mentor_db,
    learning=True, 
    name="Mentori",
    description="You are a personal mentor for agentic AI.",
    instructions=[
        "You are a personal mentor guiding a learner.",
        "Be encouraging, patient, and specific.",
        "Ask questions to understand the learner's background and goals.",
    ],
    add_history_to_context=True,
    num_history_runs=3,
    markdown=True,
    debug_mode=True,
    learning=LearningMachine(
        user_profile=UserProfileConfig(schema=LearnerProfile),
        user_memory=True,
        session_context=SessionContextConfig(enable_planning=True),
    ),
)
```

**Test checklist**:

- [ ] Agent responds coherently
- [ ] Agent remembers the previous message within the same session
- [ ] `debug_mode=True` shows the compiled system message in the console
- [ ] Database file is created at `tmp/mentor.db`

**What you learn**: How the agent builds context, what the system message looks like, how session history works.

**Docs**: [/agents/building-agents](https://docs.agno.com/agents/building-agents), [/agents/usage/agent-with-storage](https://docs.agno.com/agents/usage/agent-with-storage)

---

### Phase 1 — Turn On Learning (`learning=True`)

**Goal**: Activate automatic user profile + user memory extraction. The agent now learns about the learner without any custom configuration.

**What you change**: Add one parameter.

```python
mentor_agent = Agent(
    model=default_model(),
    db=db,
    learning=True,          # ← This one line
    name="Mentor",
    description="You are a personal mentor for [your field].",
    instructions=[...],
    add_history_to_context=True,
    num_history_runs=3,
    markdown=True,
    debug_mode=True,
)
```

From [/learning/quickstart](https://docs.agno.com/learning/quickstart):
> *"The simplest way: set learning=True. This enables user profile and user memory extraction in Always mode."*

**Test checklist**:

- [ ] Run a conversation where the learner shares their name, background, and goals
- [ ] Start a **new session** with the same `user_id` and ask "What do you know about me?"
- [ ] Inspect what was extracted:

```python
lm = agent.learning_machine
lm.user_profile_store.print(user_id="test_learner@example.com")
lm.user_memory_store.print(user_id="test_learner@example.com")
```

- [ ] Verify the profile shows `name` and `preferred_name` fields
- [ ] Verify memories contain observations about the learner
- [ ] Check `debug_mode` output — you should see `<user_profile>` and `<user_memory>` blocks in the system message

**What you learn**: How Always mode extraction works, what the default profile schema captures, how memories are injected into context, the extra LLM call cost per interaction.

**Docs**: [/learning/quickstart](https://docs.agno.com/learning/quickstart), [/examples/learning/quickstart/always-learn](https://docs.agno.com/examples/learning/quickstart/always-learn), [/learning/stores/user-profile](https://docs.agno.com/learning/stores/user-profile), [/learning/stores/user-memory](https://docs.agno.com/learning/stores/user-memory)

---

### Phase 2 — Custom Learner Profile Schema

**Goal**: Replace the default profile (name, preferred_name) with a domain-specific `LearnerProfile` that captures the structured attributes your mentor needs.

**What you change**:

```python
from dataclasses import dataclass, field
from typing import Optional
from agno.learn import LearningMachine, UserProfileConfig
from agno.learn.schemas import UserProfile

@dataclass
class LearnerProfile(UserProfile):
    background: Optional[str] = field(
        default=None,
        metadata={"description": "Professional or academic background"}
    )
    experience_level: Optional[str] = field(
        default=None,
        metadata={"description": "Overall level: beginner | intermediate | advanced"}
    )
    learning_goals: Optional[str] = field(
        default=None,
        metadata={"description": "What the learner wants to achieve"}
    )
    preferred_specialisation: Optional[str] = field(
        default=None,
        metadata={"description": "Chosen specialisation pathway, if any"}
    )
    preferred_learning_style: Optional[str] = field(
        default=None,
        metadata={"description": "How the learner prefers to learn: visual | hands-on | reading | project-based"}
    )
    available_time: Optional[str] = field(
        default=None,
        metadata={"description": "Time available for learning per week, e.g. '5 hours/week'"}
    )
    timeline: Optional[str] = field(
        default=None,
        metadata={"description": "Target completion timeframe, e.g. '6 months'"}
    )
    current_skills: Optional[str] = field(
        default=None,
        metadata={"description": "Skills the learner already has in this field"}
    )

mentor_agent = Agent(
    model=default_model(),
    db=db,
    learning=LearningMachine(
        user_profile=UserProfileConfig(schema=LearnerProfile),
        user_memory=True,
    ),
    ...
)
```

From [/learning/custom-schemas](https://docs.agno.com/learning/custom-schemas):
> *"The metadata["description"] tells the LLM what to extract."*

> *"All custom fields should be Optional with defaults."*

> *"For fields with known options, list them in the description."*

**Test checklist**:

- [ ] Run an onboarding-style conversation: learner shares background, goals, time available
- [ ] Inspect the extracted profile:

```python
lm = agent.learning_machine
lm.user_profile_store.print(user_id="test_learner@example.com")
```

- [ ] Verify custom fields are populated (background, experience_level, learning_goals, etc.)
- [ ] Verify the `<user_profile>` block in debug output shows the custom fields
- [ ] Start a new session — does the agent reference the learner's background and goals?
- [ ] Run a second conversation where the learner *updates* a field (e.g. changes their goal) — verify the profile is updated in place, not duplicated

**Experiment**: Try removing `metadata={"description": ...}` from one field and see how extraction quality degrades. This demonstrates why descriptions matter.

**What you learn**: How custom schemas guide extraction, how profiles are updated in place vs. memories which append, the difference between structured (profile) and unstructured (memory) knowledge.

**Docs**: [/learning/custom-schemas](https://docs.agno.com/learning/custom-schemas), [/learning/stores/user-profile](https://docs.agno.com/learning/stores/user-profile)

---

### Phase 3 — Session Context with Planning

**Goal**: Track what the learner is working on within a session — the goal, the plan steps, and which steps are completed. This replaces manual session state management.

**What you change**:

```python
from agno.learn import LearningMachine, SessionContextConfig

mentor_agent = Agent(
    model=default_model(),
    db=db,
    learning=LearningMachine(
        user_profile=UserProfileConfig(schema=LearnerProfile),
        user_memory=True,
        session_context=SessionContextConfig(enable_planning=True),  # ← New
    ),
    ...
)
```

From [/learning/stores/session-context](https://docs.agno.com/learning/stores/session-context):
> *"Enable planning to track goals, plan steps, and progress."*

The injected context looks like:

```xml
<session_context>
Summary: Helping learner work through a challenge on [topic].

Goal: Complete challenge #3: Build a [something]

Plan:
  1. Understand the problem
  2. Research relevant concepts
  3. Implement the solution
  4. Test and validate

Completed:
  ✓ Understand the problem
  ✓ Research relevant concepts
</session_context>
```

**Test checklist**:

- [ ] Start a session and give the agent a multi-step task (e.g. "Help me work through understanding [concept] step by step")
- [ ] After a few exchanges, inspect the session context:

```python
lm = agent.learning_machine
lm.session_context_store.print(session_id="session_1")
```

- [ ] Verify `goal`, `plan`, and `progress` fields are populated
- [ ] Check debug output for the `<session_context>` block
- [ ] Continue the conversation — does the agent know which steps are completed?
- [ ] Start a new session with a different goal — verify the previous session's context doesn't bleed over

**Experiment**: Have a long conversation (10+ messages) and observe how session context maintains the goal/plan even as chat history gets truncated. Per the docs:
> *"Session context is essential when: Message history gets truncated: long conversations lose early context. Sessions are resumed: user returns after a break."* ([/learning/stores/session-context](https://docs.agno.com/learning/stores/session-context))

**What you learn**: How planning mode tracks multi-step progress, how session context complements chat history, the difference between session-scoped context (replaced each update) and user-scoped stores (persistent).

**Docs**: [/learning/stores/session-context](https://docs.agno.com/learning/stores/session-context)

---

### Phase 4 — Domain Knowledge Base (Agentic RAG)

**Goal**: Give the agent access to your curated domain knowledge so it grounds its mentoring in trustworthy, current content rather than model training data.

**What you build**: A `Knowledge` instance with a vector database, loaded with your domain content.

```python
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.knowledge.knowledge import Knowledge

# Use the project's create_knowledge() helper — it picks the right vector DB
# backend (ChromaDB for SQLite, PgVector for Postgres) automatically.
from db import create_knowledge

domain_knowledge = create_knowledge(
    name="Domain Knowledge Base",
    table_name="domain_knowledge",
)

# Load your content
domain_knowledge.insert(
    file_path="curricula/module1.pdf",
    metadata={"topic": "foundations", "level": "beginner", "pathway": "core"},
)
domain_knowledge.insert(
    file_path="curricula/module2.pdf",
    metadata={"topic": "intermediate", "level": "intermediate", "pathway": "core"},
)
# Add more content...

mentor_agent = Agent(
    model=default_model(),
    db=db,
    learning=LearningMachine(
        user_profile=UserProfileConfig(schema=LearnerProfile),
        user_memory=True,
        session_context=SessionContextConfig(enable_planning=True),
    ),
    knowledge=domain_knowledge,           # ← New
    search_knowledge=True,                # ← New (adds search_knowledge_base tool)
    enable_agentic_knowledge_filters=True, # ← New (let agent filter by metadata)
    ...
)
```

From [/knowledge/overview](https://docs.agno.com/knowledge/overview):
> *"Knowledge gives agents access to information beyond their training data."*

> *"Agno Agents use Agentic RAG by default... it will search this knowledge base, at runtime, for the specific information it needs."* ([/knowledge/agents](https://docs.agno.com/knowledge/agents))

**Test checklist**:

- [ ] Ask the agent a domain-specific question that requires knowledge base content
- [ ] Verify the agent calls `search_knowledge_base` (visible in debug output and stream events)
- [ ] Verify the response is grounded in your content, not hallucinated
- [ ] Ask a question that should be filtered by metadata (e.g. "explain [topic] at a beginner level") and verify the agent uses filters
- [ ] Ask a question outside your knowledge base — does the agent say it doesn't have enough information, or does it hallucinate?

**Experiment**: Load a small set of content (1-2 documents) first. Test retrieval quality. Then load more content and observe how retrieval results change. Try different chunking strategies if results are poor.

**Context cost note**: `enable_agentic_knowledge_filters` adds ~300 tokens of filter instructions to the system message. This is justified — your agent needs to filter by pathway and difficulty level.

**What you learn**: How Agentic RAG works, how metadata filters narrow results, the token cost of knowledge search results in context, when the agent decides to search vs. answer from its own knowledge.

**Docs**: [/knowledge/overview](https://docs.agno.com/knowledge/overview), [/knowledge/agents](https://docs.agno.com/knowledge/agents), [/examples/learning/quickstart/learned-knowledge](https://docs.agno.com/examples/learning/quickstart/learned-knowledge)

---

### Phase 5 — Dynamic Instructions & Onboarding Flow

**Goal**: Make the agent's behaviour adapt based on where the learner is in their journey — onboarding vs. active learning — using dynamic instructions.

**What you change**: Replace static instructions with a callable factory.

```python
from agno.run import RunContext

def get_mentor_instructions(run_context: RunContext):
    state = run_context.session_state or {}
    stage = state.get("onboarding_step", "welcome")
    
    base = [
        "You are a personal mentor guiding the learner on a personalised learning journey.",
        "Be encouraging, patient, and specific in your guidance.",
        "Always ground your teaching in the knowledge base — search it before answering.",
        "Adapt your language to the learner's current skill level.",
        "Never make up information — search the knowledge base or say so.",
    ]
    
    if stage == "welcome":
        return base + [
            "Greet the learner warmly. Introduce yourself as their personal mentor.",
            "Ask them to upload their CV or describe their background.",
            "Ask what they want to learn and why — their motivation matters.",
        ]
    elif stage == "goals":
        return base + [
            "The learner has shared their background. Now explore their goals in depth.",
            "Ask about their preferred learning style, available time, and timeline.",
            "Suggest 2-3 possible learning pathways based on what you know.",
            "Let the learner choose which pathway appeals to them.",
        ]
    elif stage == "active":
        return base + [
            "The learner is on an active learning journey.",
            "Use their profile, memories, and session context to guide them.",
            "Present challenges appropriate to their current skill level.",
            "When the learner completes a challenge, assess it and suggest the next step.",
            "Celebrate progress — acknowledge completed milestones.",
        ]
    
    return base

mentor_agent = Agent(
    model=default_model(),
    db=db,
    learning=LearningMachine(
        user_profile=UserProfileConfig(schema=LearnerProfile),
        user_memory=True,
        session_context=SessionContextConfig(enable_planning=True),
    ),
    knowledge=domain_knowledge,
    search_knowledge=True,
    enable_agentic_knowledge_filters=True,
    instructions=get_mentor_instructions,  # ← Now dynamic
    add_instruction_tags=True,
    ...
)
```

From [/agents/building-agents](https://docs.agno.com/agents/building-agents):
> *"Pass a function instead of a static list for tools or knowledge. The function is called at the start of each run."*

Control the stage externally:

```python
# Onboarding - welcome stage
mentor_agent.run(
    "Hi!",
    user_id="learner@example.com",
    session_id="s1",
    session_state={"onboarding_step": "welcome"},
)

# Move to goals stage
mentor_agent.run(
    "I've uploaded my CV. What pathways are available?",
    user_id="learner@example.com",
    session_id="s2",
    session_state={"onboarding_step": "goals"},
)

# Active learning
mentor_agent.run(
    "I'm ready for my first challenge.",
    user_id="learner@example.com",
    session_id="s3",
    session_state={"onboarding_step": "active"},
)
```

**Test checklist**:

- [ ] Run with `onboarding_step="welcome"` — verify the agent greets and asks for background
- [ ] Run with `onboarding_step="goals"` — verify the agent asks about goals and suggests pathways
- [ ] Run with `onboarding_step="active"` — verify the agent references the learner's profile and knowledge base
- [ ] Check debug output — the `<instructions>` block should differ between stages
- [ ] Verify the agent in "active" stage actually searches the knowledge base

**Experiment**: Try running with no `session_state` (defaults to "welcome"). Then try setting an invalid stage value and see how the fallback `return base` works.

**What you learn**: How callable factories work, how session state drives instruction selection, how the same agent can serve different roles at different stages.

**Docs**: [/agents/building-agents](https://docs.agno.com/agents/building-agents) (Callable Factories), [/context/agent/overview](https://docs.agno.com/context/agent/overview) (Dynamic Instructions example)

---

### Phase 6 — Custom Challenge Tools & Structured Output

**Goal**: Give the agent the ability to create, retrieve, and assess challenges — the core workflow engine of your mentor platform.

**What you build**: Custom tools that integrate with your application's challenge storage, plus structured output schemas for challenges and assessments.

```python
from pydantic import BaseModel, Field
from agno.tools import tool

# ─── Structured output schemas ──────────────────────────────────────

class ChallengeSpec(BaseModel):
    title: str = Field(description="Short, engaging title")
    description: str = Field(description="Clear instructions for the learner")
    difficulty: str = Field(description="beginner | intermediate | advanced")
    skills_assessed: list[str] = Field(description="Skills this challenge evaluates")
    estimated_time: str = Field(description="Rough time to complete, e.g. '30 minutes'")
    pathway: str = Field(description="Which learning pathway this belongs to")
    prerequisites: list[str] = Field(description="Challenge IDs or skills needed first")

class AssessmentResult(BaseModel):
    challenge_id: str
    score: float = Field(ge=0, le=1, description="Score from 0.0 to 1.0")
    skills_demonstrated: list[str] = Field(description="Skills the learner showed")
    skills_needing_work: list[str] = Field(description="Skills not yet demonstrated")
    feedback: str = Field(description="Constructive, specific feedback")
    next_recommended_challenge_id: str = Field(description="ID of the next challenge to try")

# ─── Custom tools ───────────────────────────────────────────────────
# Start with stubs — replace with real app integration later

_challenges_db: dict[str, dict] = {}  # Temporary in-memory store

@tool
def create_challenge(
    title: str,
    description: str,
    difficulty: str,
    skills_assessed: list[str],
    estimated_time: str,
    pathway: str,
) -> dict:
    """Create a new learning challenge and add it to the learner's dashboard.
    
    Args:
        title: Short, engaging title for the challenge.
        description: What the learner needs to do, with clear instructions.
        difficulty: "beginner", "intermediate", or "advanced".
        skills_assessed: List of skill names this challenge evaluates.
        estimated_time: Rough time to complete (e.g. "30 minutes").
        pathway: Which learning pathway this challenge belongs to.
    
    Returns:
        The created challenge with its ID.
    """
    import uuid
    challenge_id = str(uuid.uuid4())[:8]
    challenge = {
        "id": challenge_id,
        "title": title,
        "description": description,
        "difficulty": difficulty,
        "skills_assessed": skills_assessed,
        "estimated_time": estimated_time,
        "pathway": pathway,
        "status": "not_started",
    }
    _challenges_db[challenge_id] = challenge
    return challenge

@tool
def get_available_challenges() -> list[dict]:
    """Get all challenges available to the learner on their dashboard.
    
    Returns:
        List of challenges with their status (not_started, in_progress, completed).
    """
    return list(_challenges_db.values())

@tool
def assess_submission(
    challenge_id: str,
    submission: str,
) -> dict:
    """Assess a learner's challenge submission.
    
    Args:
        challenge_id: The ID of the challenge being assessed.
        submission: The learner's submitted work.
    
    Returns:
        Assessment with score, skills demonstrated, and feedback.
    """
    # In production, this would call the agent with output_schema=AssessmentResult
    # or use a separate assessment model. For now, return a stub.
    challenge = _challenges_db.get(challenge_id, {})
    return {
        "challenge_id": challenge_id,
        "score": 0.8,
        "skills_demonstrated": challenge.get("skills_assessed", [])[:2],
        "skills_needing_work": challenge.get("skills_assessed", [])[2:],
        "feedback": "Good work on the core concepts. Review the advanced sections.",
        "next_recommended_challenge_id": "",
    }

@tool
def get_learner_progress() -> dict:
    """Get the learner's current progress toward their goals.
    
    Returns:
        Progress summary with completed challenges, skills acquired,
        and remaining pathway milestones.
    """
    completed = [c for c in _challenges_db.values() if c.get("status") == "completed"]
    in_progress = [c for c in _challenges_db.values() if c.get("status") == "in_progress"]
    return {
        "completed_challenges": len(completed),
        "in_progress_challenges": len(in_progress),
        "total_challenges": len(_challenges_db),
        "completed": [c["title"] for c in completed],
    }

# ─── Updated agent ──────────────────────────────────────────────────

mentor_agent = Agent(
    model=default_model(),
    db=db,
    learning=LearningMachine(
        user_profile=UserProfileConfig(schema=LearnerProfile),
        user_memory=True,
        session_context=SessionContextConfig(enable_planning=True),
    ),
    knowledge=domain_knowledge,
    search_knowledge=True,
    enable_agentic_knowledge_filters=True,
    instructions=get_mentor_instructions,
    add_instruction_tags=True,
    tools=[                              # ← New
        create_challenge,
        get_available_challenges,
        assess_submission,
        get_learner_progress,
    ],
    tool_call_limit=8,                   # ← New
    ...
)
```

**Test checklist**:

- [ ] Ask the agent to create a challenge for a beginner in a specific topic
- [ ] Verify `create_challenge` is called (visible in debug/stream events)
- [ ] Call `get_available_challenges` through the agent and verify challenges are returned
- [ ] Submit a mock answer to a challenge and verify `assess_submission` is called
- [ ] Ask the agent for progress — verify `get_learner_progress` is called
- [ ] Verify `tool_call_limit=8` prevents runaway tool calls (try giving a prompt that might trigger many calls)

**Experiment with structured output**: Run a challenge creation request with `output_schema=ChallengeSpec`:

```python
response = mentor_agent.run(
    "Create a beginner challenge about [topic] for the core pathway.",
    user_id="learner@example.com",
    session_id="s1",
    output_schema=ChallengeSpec,
)
print(response.content)  # Will be a ChallengeSpec instance
```

Verify you get a validated `ChallengeSpec` object back. Then try the same for assessments with `output_schema=AssessmentResult`.

**What you learn**: How custom tools integrate with the agent loop, how structured output validates responses, how `tool_call_limit` prevents loops, the context cost of tool definitions.

**Docs**: [/tools/overview](https://docs.agno.com/tools/overview), [/tools/tool-call-limit](https://docs.agno.com/tools/tool-call-limit), [/agents/running-agents](https://docs.agno.com/agents/running-agents) (Passing Output Schema)

---

### Phase 7 — Learned Knowledge & Context Compression

**Goal**: Add the final two layers — cross-learner insights (Learned Knowledge store) and context compression to manage tool result bloat over long sessions.

#### 7a — Learned Knowledge

**What you change**:

```python
from agno.learn import LearnedKnowledgeConfig, LearningMode

mentor_agent = Agent(
    model=default_model(),
    db=db,
    learning=LearningMachine(
        user_profile=UserProfileConfig(schema=LearnerProfile),
        user_memory=True,
        session_context=SessionContextConfig(enable_planning=True),
        learned_knowledge=LearnedKnowledgeConfig(   # ← New
            mode=LearningMode.AGENTIC,
        ),
        knowledge=domain_knowledge,                  # ← Shared knowledge instance
    ),
    ...
)
```

From [/examples/learning/quickstart/learned-knowledge](https://docs.agno.com/examples/learning/quickstart/learned-knowledge):
> *"Learned Knowledge stores insights that transfer across users. One person teaches the agent something. Another person benefits."*

In Agentic mode, the agent receives two new tools: `search_learnings` and `save_learning` ([/learning/learning-modes](https://docs.agno.com/learning/learning-modes)).

**Test checklist**:

- [ ] As learner A, have a conversation that produces a generalisable insight (e.g. "I find [concept X] much easier after understanding [concept Y] first")
- [ ] Verify the agent calls `save_learning` (visible in debug/stream events)
- [ ] As learner B (different `user_id`), ask a related question
- [ ] Verify the agent calls `search_learnings` and references the insight from learner A
- [ ] Inspect the learned knowledge store:

```python
lm = agent.learning_machine
lm.learned_knowledge_store.print(query="concept")
```

**Context cost note**: Learned Knowledge in Agentic mode adds 2 tool definitions (~300 tokens). Justified for cross-learner value.

#### 7b — Context Compression

**What you change**:

```python
from agno.compression.manager import CompressionManager

compression_manager = CompressionManager(
    model=default_model(),  # Reuse the project's default model for compression
    compress_tool_results_limit=5,             # Compress after 5 uncompressed tool results
)

mentor_agent = Agent(
    ...,
    compress_tool_results=True,                 # ← New
    compression_manager=compression_manager,    # ← New
)
```

From [/compression/overview](https://docs.agno.com/compression/overview):
> *"Context compression summarizes tool results after a threshold... Dramatically reduced token costs, Stay within context window limits, Preserve critical facts and data."*

> *"Use a faster, cheaper model like gpt-4o-mini for compression to reduce latency and cost."* ([/compression/overview](https://docs.agno.com/compression/overview))

**Test checklist**:

- [ ] Have a long conversation with many knowledge searches (6+ tool calls)
- [ ] Check debug output — after the 5th uncompressed tool result, compression should trigger
- [ ] Verify compressed results are shorter but retain key facts
- [ ] Compare token usage with and without compression (check `response.metrics`)

**Experiment**: Set `compress_tool_results_limit=2` (more aggressive) and have the same conversation. Compare context quality — does the agent lose important details with more aggressive compression?

**What you learn**: How compression works, the tradeoff between context fidelity and token cost, how a cheaper model can handle compression while the main model handles conversation.

**Docs**: [/compression/overview](https://docs.agno.com/compression/overview), [/learning/stores/learned-knowledge](https://docs.agno.com/learning/stores/learned-knowledge), [/learning/learning-modes](https://docs.agno.com/learning/learning-modes)

---

## Phase Summary

| Phase | What you add | Lines changed | New context cost | Independently testable |
|---|---|---|---|---|
| 0 | DB + history + basic agent | ~15 | ~1,500 tokens (history) | ✅ |
| 1 | `learning=True` | 1 line | ~400 tokens (profile + memory) | ✅ |
| 2 | Custom `LearnerProfile` schema | ~30 lines | ~150 tokens (profile, smaller than raw memories) | ✅ |
| 3 | Session Context with planning | 2 lines | ~200 tokens (`<session_context>`) | ✅ |
| 4 | Knowledge base + Agentic RAG | ~15 lines | ~450 tokens (tool + filter instructions) | ✅ |
| 5 | Dynamic instructions | ~30 lines | Net zero (replaces static instructions) | ✅ |
| 6 | Custom challenge tools + limits | ~80 lines | ~600 tokens (4 tool definitions) | ✅ |
| 7a | Learned Knowledge store | 3 lines | ~300 tokens (2 tools) | ✅ |
| 7b | Context compression | 5 lines | Saves tokens (net negative) | ✅ |
| **Total** | **Full mentor agent** | **~180 lines** | **~3,900 tokens (~3% of 128k)** | |

---

## After Phase 7 — Optional Future Enhancements

These are deliberately deferred. Add them only when you've validated the core flow and have a specific need:

| Enhancement | When to add | Source |
|---|---|---|
| **Entity Memory** | When you want to track skills/concepts as entities with relationships (e.g. "concept X depends_on concept Y") | [/learning/stores/entity-memory](https://docs.agno.com/learning/stores/entity-memory) |
| **Decision Log** | When you need to audit why the agent recommended certain challenges or pathways | [/learning/stores/decision-log](https://docs.agno.com/learning/stores/decision-log) |
| **Memory curation/pruning** | When learners have 100+ memories and costs grow | [/learning/stores/user-memory](https://docs.agno.com/learning/stores/user-memory) — `lm.curator.prune()` and `lm.curator.deduplicate()` |
| **File upload for CVs** | When you build the onboarding UI | [/agents/running-agents](https://docs.agno.com/agents/running-agents) — `files=[File(url=...)]` |
| **Session history search** | When learners return after long breaks and need deeper recall | [/context/agent/overview](https://docs.agno.com/context/agent/overview) — `search_session_history=True` |
| **Switch to PostgresDb** | When you move from development to production or need shared state across agents | Set `DB_BACKEND=postgres` + `DB_*` env vars — see [`db/session.py`](../db/session.py) |
| **Token-based compression** | When tool results vary widely in size | [/compression/overview](https://docs.agno.com/compression/overview) — `compress_token_limit=5000` |
| **Team of agents** | When you need separate agents for tutoring vs. assessment vs. pathway planning | [/teams/overview](https://docs.agno.com/teams/overview) — with shared learning machine |
| **Propose mode for Learned Knowledge** | When you want learners to confirm insights before they're shared cross-learner | [/learning/learning-modes](https://docs.agno.com/learning/learning-modes) |

---

**Sources used:**

- [https://docs.agno.com/learning/overview](https://docs.agno.com/learning/overview)
- [https://docs.agno.com/learning/quickstart](https://docs.agno.com/learning/quickstart)
- [https://docs.agno.com/learning/learning-modes](https://docs.agno.com/learning/learning-modes)
- [https://docs.agno.com/learning/custom-schemas](https://docs.agno.com/learning/custom-schemas)
- [https://docs.agno.com/learning/stores/intro](https://docs.agno.com/learning/stores/intro)
- [https://docs.agno.com/learning/stores/user-profile](https://docs.agno.com/learning/stores/user-profile)
- [https://docs.agno.com/learning/stores/user-memory](https://docs.agno.com/learning/stores/user-memory)
- [https://docs.agno.com/learning/stores/session-context](https://docs.agno.com/learning/stores/session-context)
- [https://docs.agno.com/learning/stores/entity-memory](https://docs.agno.com/learning/stores/entity-memory)
- [https://docs.agno.com/learning/stores/decision-log](https://docs.agno.com/learning/stores/decision-log)
- [https://docs.agno.com/examples/learning/quickstart/always-learn](https://docs.agno.com/examples/learning/quickstart/always-learn)
- [https://docs.agno.com/examples/learning/quickstart/agentic-learn](https://docs.agno.com/examples/learning/quickstart/agentic-learn)
- [https://docs.agno.com/examples/learning/quickstart/learned-knowledge](https://docs.agno.com/examples/learning/quickstart/learned-knowledge)
- [https://docs.agno.com/knowledge/overview](https://docs.agno.com/knowledge/overview)
- [https://docs.agno.com/knowledge/agents](https://docs.agno.com/knowledge/agents)
- [https://docs.agno.com/compression/overview](https://docs.agno.com/compression/overview)
- [https://docs.agno.com/agents/building-agents](https://docs.agno.com/agents/building-agents)
- [https://docs.agno.com/agents/running-agents](https://docs.agno.com/agents/running-agents)
- [https://docs.agno.com/agents/usage/agent-with-storage](https://docs.agno.com/agents/usage/agent-with-storage)
- [https://docs.agno.com/context/agent/overview](https://docs.agno.com/context/agent/overview)
- [https://docs.agno.com/tools/overview](https://docs.agno.com/tools/overview)
- [https://docs.agno.com/tools/tool-call-limit](https://docs.agno.com/tools/tool-call-limit)
