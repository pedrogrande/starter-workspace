# Custom Agent Frontmatter Reference

Complete field reference for `.agent.md` YAML frontmatter. VS Code custom
agents live at `.github/agents/*.agent.md` (workspace) or
`<profile>/agents/*.agent.md` (user).

## Required fields

### `description`

- String. One sentence on what the agent **produces**, not who it is.
- For subagent-only agents, this is the discovery surface — the parent
  agent matches it against the task. Include specific trigger keywords.
- Appears as placeholder text in the chat input.

```yaml
description: "Author a single well-scoped code change with tests"
```

## Optional fields

### `name`

- String. Defaults to filename (without `.agent.md`).
- Short, verb-noun. Avoids role-play language.

```yaml
name: "Change Author"
```

### `tools`

- List of tool aliases, specific tools, MCP servers (`<server>/*`), or
  extension tools.
- `[]` = no tools (conversational only). Omit = all default tools.
- **Most important field.** Every tool increases the decision space.

| Alias | Purpose |
|-------|---------|
| `execute` | Run shell commands |
| `read` | Read file contents |
| `edit` | Edit files |
| `search` | Search files or text |
| `agent` | Invoke custom agents as subagents |
| `web` | Fetch URLs and web search |
| `todo` | Manage task lists |
| `problems` | Read diagnostics (errors, warnings) |

Common patterns:

```yaml
tools: [read, search]             # Read-only research
tools: [read, edit, search, execute, problems]  # Full code author
tools: [myserver/*]               # MCP server only
tools: [agent]                    # Orchestrator (routes only)
tools: []                         # Conversational only
```

### `model`

- String or ordered list. First available model is used (graceful
  degradation).
- Use the `(copilot)` provider suffix.

```yaml
model: ["Claude Sonnet 4.5 (copilot)", "GPT-4.1 (copilot)"]
```

### `argument-hint`

- String. Guides the user toward the right input shape.

```yaml
argument-hint: "Describe the change you want made"
```

### `agents`

- List of allowed subagent names. Include the `agent` tool in `tools`
  when this is set.
- Omit = all agents allowed. `[]` = none. `*` = all (explicit).

```yaml
agents: ["Researcher", "Change Author", "Reviewer"]
```

### `user-invocable`

- Boolean. Default `true`. Set `false` for subagent-only workers (hidden
  from the agent picker dropdown).

### `disable-model-invocation`

- Boolean. Default `false`. Set `true` to prevent other agents from
  invoking this one as a subagent (appears in picker but never delegated
  to).

### `handoffs`

- List of user-gated transitions to other agents.

```yaml
handoffs:
  - label: "Review Changes"       # Button text
    agent: "reviewer"             # Must match another agent's name
    prompt: "Review the changes just made."
    send: false                   # false = pre-fill prompt, true = auto-submit
    # model: "Claude Opus 4.5 (copilot)"  # Optional: force a model
```

### `hooks`

- Inline hooks scoped to this agent. See [hooks reference](hooks.md).

```yaml
hooks:
  PreToolUse:
    - type: "command"
      command: "./scripts/hooks/block-outside-src.sh"
      timeout: 5
  PostToolUse:
    - type: "command"
      command: "./scripts/hooks/format.sh"
```

### `target`

- String. Default `vscode`. Set `github-copilot` for GitHub Copilot
  cloud agent support. When set, `mcp-servers` can be configured inline.

### `mcp-servers` (GitHub Copilot target only)

- For VS Code local agents, configure MCP servers in `.vscode/mcp.json`
  instead. This field is only for `target: github-copilot`.

```yaml
mcp-servers:
  docs:
    type: "local"
    command: "npx"
    args: ["@modelcontextprotocol/server-memory"]
    tools: ["*"]
```

## Invocation control summary

| Configuration | Picker | Subagent | Use case |
|---|---|---|---|
| Default (both omitted) | Yes | Yes | General-purpose |
| `user-invocable: false` | No | Yes | Subagent-only worker |
| `disable-model-invocation: true` | Yes | No | Manual invocation only |
| `user-invocable: false` + `disable-model-invocation: true` | No | No | Effectively hidden (rare) |
