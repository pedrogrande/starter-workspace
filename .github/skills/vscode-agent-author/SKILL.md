---
name: vscode-agent-author
description: >
  Design and write VS Code custom agent files (.agent.md) following the
  minimum-sufficient-context spec: scoped tools, structured instructions,
  hard-enforcement hooks, and handoffs. Use this skill when creating a
  new custom agent, reviewing an existing .agent.md for quality, deciding
  an agent's tool set, writing agent body instructions, adding PreToolUse
  or PostToolUse hooks to an agent, designing an orchestrator-with-subagents
  team, or adapting the reference spec to a specific project. Covers
  frontmatter fields, body section ordering, hook input/output contracts,
  model fallback chains, and the orchestrator/subagent/handoff patterns.
argument-hint: "[agent name or task description]"
---

# VS Code Custom Agent Author

Design and write `.agent.md` files that follow the minimum-sufficient-context
principle: every agent does one thing, holds only the tools it needs, and
enforces its hard rules programmatically.

## When to use this skill

- Creating a new `.agent.md` from scratch
- Reviewing or refining an existing custom agent
- Deciding an agent's tool set, model, or subagent list
- Writing PreToolUse / PostToolUse hooks for an agent
- Designing an orchestrator + subagent team with handoffs
- Adapting the reference spec to a project-specific domain

## Step 1 — Confirm a custom agent is the right layer

A custom agent is for a **persistent persona with restricted tools, model
pinning, or handoffs**. Before writing one, verify:

```
IF always-on AND project-wide convention
  → Custom Instructions (.github/copilot-instructions.md)

IF task-specific, needs scripts/resources, loads only when relevant
  → Agent Skill (.github/skills/<name>/SKILL.md)

IF persistent persona with restricted tools, model pinning, or handoffs
  → Custom Agent (.github/agents/<name>.agent.md)  ← this skill
```

If the task needs context isolation (subagent returns one output) or
different tool restrictions per stage, a custom agent is correct. If all
steps share the same capabilities, a skill is lighter.

## Step 2 — Scope the agent

Design the agent as a single-capability unit. Before writing frontmatter,
answer:

| Question | Answer determines |
|---|---|
| What is the ONE thing this agent produces? | `description`, body Scope |
| Which tools does it NEED (not "might use")? | `tools` field |
| What must it NEVER do? | Body Rules + `hooks` |
| Does it hand off to another agent after finishing? | `handoffs` |
| Is it user-invocable or subagent-only? | `user-invocable` |
| Which models, in fallback order? | `model` |

**Tool scoping rule:** Every tool you add increases the decision space.
If the agent doesn't need `web`, don't include it. Hard enforcement —
the model *cannot* use tools not in the list.

## Step 3 — Write the frontmatter

Use the [frontmatter reference](references/frontmatter.md) for the complete
field list. Key rules:

- `description`: required. One sentence on what the agent produces, not
  who it is. Include trigger keywords for subagent discovery.
- `tools`: list only what the agent needs. `[]` = no tools, omit = defaults.
- `model`: ordered list for graceful degradation. Use the `(copilot)`
  provider suffix: `"Claude Sonnet 4.5 (copilot)"`.
- `agents`: explicit list of allowed subagents. `*` = all, `[]` = none.
  Include the `agent` tool in `tools` when this is set.
- `user-invocable: false` for subagent-only workers.
- `hooks`: inline hooks scoped to this agent. See Step 5.

## Step 4 — Write the body (five sections, in order)

The body is structured, not prose. No "You are a helpful…" language.
Order by attention priority:

```
1. Rules        ← Most important. First thing the model reads.
2. Scope        ← Input/output contract.
3. Process      ← Sequential workflow with explicit tool references.
4. References   ← Links to skill files (progressive disclosure).
5. Boundaries   ← What this agent does NOT do. Last section.
```

### Format per section

- **Rules**: `MUST`, `MUST NOT`, `NEVER` — modal verbs, no hedging.
- **Scope**: `READS` / `WRITES` / `FORMAT` — machine-parseable contracts.
- **Process**: Numbered steps with `:tool-name` references (e.g.,
  `Run :terminal npm test`). Explicit tool calls reduce decision space.
- **References**: Markdown links to skill files. Detail lives there,
  not in the agent file.
- **Boundaries**: Pointers to other agents for out-of-scope work.

Use the [agent body template](assets/agent-template.md) as a starting
structure. It has the five sections pre-labeled with format guidance.

## Step 5 — Add hooks for hard enforcement

If a rule says `MUST NOT`, back it with a `PreToolUse` hook. If a step
says "format after editing," back it with a `PostToolUse` hook.
Instructions are suggestions; hooks are deterministic.

### Hook input/output contract

Hooks receive JSON on **stdin** and return JSON on **stdout**.

- `PreToolUse` permissions: `hookSpecificOutput.permissionDecision`
  (`allow` | `ask` | `deny`) + `permissionDecisionReason`.
- `PostToolUse` can block with `decision: block`.
- Exit code `0` = success, `2` = blocking error, other = non-blocking warning.

Read [the hooks reference](references/hooks.md) for the full contract,
supported events, and platform overrides. Use the
[block-edits hook template](assets/hook-scripts/block-edits-outside-scope.sh)
and [auto-format hook template](assets/hook-scripts/auto-format.sh) as
starting points — adapt the scope check and formatter command to the
project.

### Hook gotchas

- Hooks are **Preview**. Require `chat.useCustomAgentHooks=true` in
  VS Code settings. Without it, hooks silently don't run — the agent's
  `MUST NOT` rules become soft enforcement only.
- Hook scripts must be executable (`chmod +x`) and committed to the repo.
- Keep hooks small and fast — they run on every matching tool call.
  Set a `timeout` (seconds) to prevent hangs.

## Step 6 — Add handoffs (not monoliths)

Each agent does one thing, then hands off. Handoffs are user-gated
buttons (`send: false` pre-fills the prompt; `send: true` auto-submits).

```yaml
handoffs:
  - label: "Review Changes"
    agent: "reviewer"
    prompt: "Review the changes just made for correctness and style."
    send: false
```

Rules:

- One handoff per follow-up action. Don't chain A → B → A (circular).
- The handoff `agent` name must match another `.agent.md` `name`.
- Handoffs appear after the agent finishes — they are not mid-task routing.

## Step 7 — Validate

Run the validation script to check structure and references:

```bash
python .github/skills/skill-builder/scripts/validate-skill.py .github/skills/vscode-agent-author
```

Then execute-then-revise:

1. Invoke the agent with a real task.
2. Check: did it stay in scope? Did it use only its listed tools? Did
   hooks fire correctly?
3. If the agent over-reached, tighten `tools` or add a hook.
4. If it under-performed, check whether a needed tool was omitted.
5. Revise and re-run. Feed ALL results (not just failures) back.

For the full evaluation workflow with test cases, read
[the eval guide](references/eval-workflow.md).

## Gotchas

- **`description` is the discovery surface.** For subagent-only agents
  (`user-invocable: false`), the parent agent finds them by matching
  the `description` against the task. Vague description = never invoked.
  Include specific trigger keywords.
- **Model provider suffix.** Use `(copilot)` not `(anthropic)` or
  `(openai)` — e.g., `"Claude Sonnet 4.5 (copilot)"`. The `(copilot)`
  suffix routes through the user's Copilot subscription. Other suffixes
  may fail to resolve.
- **`agents` list requires the `agent` tool.** If you set `agents:
  ["Reviewer"]` but omit `agent` from `tools`, the agent cannot invoke
  subagents. The frontmatter is not auto-corrected.
- **Hooks silently no-op without the setting.** `chat.useCustomAgentHooks=true`
  must be in VS Code settings. Without it, `MUST NOT` rules enforced only
  by hooks are unenforced. Always pair hook-enforced rules with a written
  rule too (defense in depth).
- **`tools: []` vs omitting `tools`.** `[]` = no tools (conversational
  only). Omitting `tools` = all default tools. These are different.
- **Handoff agent names must match exactly.** The `agent:` field in a
  handoff must match the `name:` field of another `.agent.md`. Case-
  sensitive. A mismatch silently breaks the handoff button.
- **Inline hooks are agent-scoped.** Hooks defined in an agent's
  frontmatter run only for that agent. For workspace-wide policy, use
  standalone `.github/hooks/*.json` files instead.
- **Body ordering matters.** Rules first (top of context window, strong
  attention), Boundaries last (end of context window, attention spike).
  Process in the middle. Don't reorder for narrative flow.
- **No prose role descriptions.** The body contains no "You are an
  expert…" language. Just rules, scope, process. The `name` and
  `description` are labels, not prompts.

## Checklist

Progress:

- [ ] Confirmed custom agent is the right layer (not instructions or skill)
- [ ] `description` is specific, trigger-keyword-rich, one sentence
- [ ] `tools` is minimal — every tool is necessary, no "might be useful"
- [ ] `model` is an ordered fallback list with `(copilot)` suffix
- [ ] `agents` list is explicit (no `*` unless intentional), `agent` tool included
- [ ] Body has five sections in order: Rules → Scope → Process → References → Boundaries
- [ ] Rules use `MUST` / `MUST NOT` / `NEVER` — no hedging
- [ ] Process steps reference tools explicitly (`:terminal`, `:read`)
- [ ] Every `MUST NOT` rule has a matching `PreToolUse` hook
- [ ] Hook scripts are executable, committed, and have a `timeout`
- [ ] `chat.useCustomAgentHooks=true` is in VS Code settings
- [ ] Handoffs point to agents that exist (name matches exactly)
- [ ] No prose role description in the body
- [ ] Agent file is under `.github/agents/` (workspace) or user profile
- [ ] Invoked the agent with a real task and revised based on results
