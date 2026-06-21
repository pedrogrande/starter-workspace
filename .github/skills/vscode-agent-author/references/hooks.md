# Hooks Reference for Custom Agents

Deterministic lifecycle automation scoped to a single agent. Hooks enforce
what instructions can only suggest.

## When to use hooks vs instructions

| Need | Use |
|---|---|
| Guide agent behavior (non-deterministic) | Instructions in the body |
| Guarantee a rule (deterministic) | Hook |
| Block a tool from touching certain files | `PreToolUse` hook |
| Auto-format after every edit | `PostToolUse` hook |
| Inject runtime context at session start | `SessionStart` hook |

**Defense in depth:** Always pair a hook-enforced rule with a written
`MUST NOT` rule in the body. If the hook silently no-ops (setting off,
preview feature removed), the instruction is the fallback.

## Supported events

| Event | Trigger |
|---|---|
| `SessionStart` | First prompt of a new agent session |
| `UserPromptSubmit` | User submits a prompt |
| `PreToolUse` | Before tool invocation |
| `PostToolUse` | After successful tool invocation |
| `PreCompact` | Before context compaction |
| `SubagentStart` | Subagent starts |
| `SubagentStop` | Subagent ends |
| `Stop` | Agent session ends |

## Inline hook format (in agent frontmatter)

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

Each hook command supports:

- `type` (must be `command`)
- `command` (default platform)
- `windows`, `linux`, `osx` (platform overrides)
- `cwd`, `env`, `timeout` (seconds)

## Input / output contract

Hooks receive JSON on **stdin** and return JSON on **stdout**.

### PreToolUse output

Permissions are read from `hookSpecificOutput.permissionDecision`:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "File outside allowed scope. Only src/ is permitted."
  }
}
```

`permissionDecision` values: `allow` | `ask` | `deny`.

### PostToolUse output

Can block further processing:

```json
{
  "decision": "block",
  "stopReason": "Formatter failed. Fix and retry."
}
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success (non-blocking) |
| `2` | Blocking error |
| Other | Non-blocking warning |

## Standalone vs inline hooks

| Scope | Location | Applies to |
|---|---|---|
| Agent-scoped | Inline in `.agent.md` frontmatter | That agent only |
| Workspace-wide | `.github/hooks/*.json` | All agents in the workspace |

Use inline hooks for agent-specific enforcement (e.g., Code Scaffolder
can't edit vendored source). Use standalone `.json` hooks for workspace
policy (e.g., block commits to `main`).

## Prerequisites and gotchas

- **Preview feature.** Requires `chat.useCustomAgentHooks=true` in VS
  Code settings. Without it, hooks silently don't run.
- **Scripts must be executable.** `chmod +x scripts/hooks/*.sh` and
  commit them to the repo.
- **Keep hooks fast.** They run on every matching tool call. Set a
  `timeout` to prevent hangs.
- **Don't hardcode secrets.** Hook scripts are committed to the repo.
  Use env vars for any credentials.
- **Validate hook input.** Don't assume the JSON schema — parse
  defensively with `jq` and handle missing fields.
