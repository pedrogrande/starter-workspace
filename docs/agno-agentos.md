# Agno's AgentOS

**AgentOS** is Agno's production runtime for multi-agent systems — essentially the infrastructure layer that turns agent prototypes built with the Agno SDK into scalable, production-ready services. Here's a comprehensive breakdown:

---

## What Is AgentOS?

AgentOS is a **pre-built FastAPI application** for running agentic systems at scale. It handles the "missing runtime layer" that most teams end up building from scratch: large-scale orchestration, persistent state, secure tool access, session management, and built-in observability. It lets teams go from a single agent to thousands of concurrent sessions without reinventing infrastructure.

> *"Every team building agents eventually hits the same wall: there is no runtime layer. So they waste six months building one from scratch. We built the missing runtime, so you can stop building infrastructure and start shipping products."*

---

## Framework vs. AgentOS: What's the Difference?

| **Agno Framework** | **AgentOS** |
|---|---|
| Build agent *logic* (prompts, memory, knowledge, integrations) | Run and scale agents in *production* |
| Python SDK for defining agents, teams, workflows | FastAPI-based REST API server |
| Prototype and iterate quickly | Conversation management, long-running state, enterprise monitoring |

They work together: you define agents with the SDK, then deploy and operate them via AgentOS.

---

## Key Features

### 🔌 APIs Out of the Box

- Runs, sessions, memory, knowledge, and traces are available via **50+ API endpoints** the moment you connect an agent
- Supports SSE (Server-Sent Events) and OpenAPI

### 🏗️ Production-Grade Patterns

- **Stateless runtime** with **per-session isolation**
- **JWT-based RBAC** (Role-Based Access Control)
- **Structured tracing** for debugging and observability
- Built on **FastAPI** — battle-tested for high concurrency and predictable performance
- Horizontally scalable

### 🛡️ Governance & Security

- **Guardrails**, **Human-in-the-Loop (HITL)**, and admin approval flows built into the runtime
- **Audit logs** and post-execution hooks
- **Private by default**: AgentOS runs inside your own cloud/data center (AWS, GCP, Railway, or air-gapped). All data — conversations, memories, traces, logs — stays within your infrastructure. Nothing is sent to external services.

### 🔗 Multi-Model & Tool Support

- Works with **23-30+ LLM providers** (OpenAI, Anthropic Claude, Google Gemini, open-source models)
- **100+ pre-built integrations**
- Supports **Model Context Protocol (MCP)** for standardized tool discovery and execution
- AgentOS also **doubles as an MCP server**, enabling other agents and systems to connect directly — turning isolated agents into a collaborative ecosystem

### 📊 Control Plane

A web-based dashboard at [os.agno.com](https://os.agno.com) provides:

- **Chat interface** — interact with agents, teams, and workflows
- **Session monitoring** — real-time insight into every live interaction
- **Memory manager** — edit, organize, and label user memories
- **Knowledge manager** — add, update, and manage knowledge bases
- **Evaluations** — track agent performance across accuracy, reliability, and performance dimensions

The control plane connects directly from your browser to your AgentOS runtime — **no data is sent to Agno**.

---

## Three-Layer Architecture

AgentOS operates within Agno's broader three-layer architecture:

1. **Framework Layer** — Build agents, teams, and workflows with memory, knowledge, guardrails, and 100+ integrations
2. **Runtime Layer (AgentOS)** — Serve your system in production with a stateless, session-scoped FastAPI backend
3. **Control Plane Layer** — Test, monitor, and manage your system via the AgentOS UI

---

## Deployment

- Deploy as a **Docker container** wherever you like
- Supports **AWS, GCP, Railway**, or completely **air-gapped** environments
- "BYOC" (Bring Your Own Cloud) philosophy

---

## Who Uses It?

- **Product teams** — building in-product agents and chat copilots
- **ML teams** — data labeling, extraction, classification
- **AI teams** — synthetic data generation, document processing, eval automation
- **Data science teams** — data enrichment and segmentation
- **Data engineering teams** — automating data quality audits and reporting

---

## Sources

- [Agno AgentOS Product Page](https://www.agno.com/agentos)
- [Agno Documentation](https://docs.agno.com/)
- [AgentOS Control Plane Docs](https://docs.agno.com/agent-os/control-plane)
- [AgentOS API Overview](https://docs.agno.com/reference-api/overview)
- [ChatForest Review](https://chatforest.com/reviews/agno-python-agent-framework)
