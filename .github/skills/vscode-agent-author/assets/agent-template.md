# Custom Agent Body Template

Copy this structure for a new `.agent.md` body. The five sections are
ordered by attention priority — do not reorder for narrative flow.

```markdown
---
description: "{What this agent produces — one sentence, trigger keywords}"
argument-hint: "{Input guidance for the user}"
tools: [{minimal set of tool aliases}]
model: ["Claude Sonnet 4.5 (copilot)", "GPT-4.1 (copilot)"]
# agents: ["SubagentName"]   # Uncomment + include `agent` in tools
# user-invocable: false      # Uncomment for subagent-only workers
# handoffs:                  # Uncomment for follow-up transitions
#   - label: "Review Changes"
#     agent: "reviewer"
#     prompt: "Review the changes just made."
#     send: false
# hooks:                     # Uncomment for hard enforcement
#   PreToolUse:
#     - type: "command"
#       command: "./scripts/hooks/block-outside-scope.sh"
#       timeout: 5
#   PostToolUse:
#     - type: "command"
#       command: "./scripts/hooks/auto-format.sh"
---

# Rules

MUST {the most important constraint}.
MUST {the second most important constraint}.
MUST NOT {thing this agent must never do — back with a hook if possible}.
NEVER {irreversible action this agent must never take}.

# Scope

READS:  {what this agent reads — files, inputs, context}
WRITES: {what this agent writes — files, outputs, formats}
FORMAT: {output shape — one change per invocation, structured report, etc.}

# Process

1. {Step 1 — reference the tool explicitly: Run :terminal, Read :read}
2. {Step 2 — reference skill files for detail: Load [skill](path/to/SKILL.md)}
3. {Step 3}
4. {Step 4}
5. Summarize: {what to report back to the user or calling agent}

# References

- {Reference name}: [link](path/to/reference.md)
- {Skill name}: [link](path/to/SKILL.md)

# Boundaries

- This agent does not {out-of-scope task}. Use {other agent} and hand off here.
- This agent does not {another out-of-scope task}. Use {handoff or agent}.
```

## Section format rules

| Section | Format | Why |
|---|---|---|
| Rules | `MUST` / `MUST NOT` / `NEVER` — modal verbs, no hedging | Reduces ambiguity; hard constraints at top of context window |
| Scope | `READS` / `WRITES` / `FORMAT` — machine-parseable | Input/output contract, not narrative |
| Process | Numbered steps with `:tool-name` references | Explicit tool calls reduce decision space |
| References | Markdown links to skill/reference files | Progressive disclosure — detail loads on demand |
| Boundaries | Pointers to other agents | Negative constraints at end where attention spikes |

## Variations

### Orchestrator (thin router)

```markdown
---
description: "Orchestrate a feature from research through implementation"
tools: ["agent"]
agents: ["Researcher", "Change Author", "Reviewer"]
model: ["Claude Opus 4.5 (copilot)"]
handoffs:
  - label: "Start Over"
    agent: "feature-lead"
    prompt: "Start a new feature with a different approach."
    send: false
---

# Process

1. Invoke the Researcher agent to gather context.
2. Review the research summary. Confirm understanding before proceeding.
3. Invoke the Change Author agent to implement each change.
4. After all changes, hand off to the Reviewer.

# Boundaries

- This agent does not write code directly. It routes.
- This agent does not review code. It delegates to the Reviewer.
```

The orchestrator has `tools: ["agent"]` only — it cannot edit, search,
or run commands. All intelligence lives in the executor agents.

### Subagent-only worker (hidden from dropdown)

```markdown
---
description: "Audit package dependencies for vulnerabilities"
tools: ["execute", "search", "read"]
user-invocable: false
hooks:
  PreToolUse:
    - type: "command"
      command: "./scripts/hooks/allow-read-only-audit.sh"
      timeout: 5
---

# Rules

MUST NOT install, update, or remove packages.
MUST NOT edit any file.
MUST NOT run commands that modify node_modules or lock files.

# Scope

READS: package.json, package-lock.json, audit output
WRITES: nothing (report only)
FORMAT: vulnerability table with severity, package, and suggested version

# Process

1. Run `:terminal npm audit --json` to get the full audit report.
2. Run `:terminal npm outdated --json` to identify outdated dependencies.
3. Read `:read package.json` for current dependency versions.
4. Produce a structured report. Do not make changes.

# Boundaries

- This agent cannot make changes. It only reports.
- For remediation, invoke the Change Author agent.
```

`user-invocable: false` hides it from the dropdown. Only accessible when
another agent delegates to it.
