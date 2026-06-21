# Structure Guide: Progressive Disclosure and Directory Layout

How to structure a skill for efficient context loading.

## The three-level loading system

Agents load skills progressively, pulling in more detail only as a task
calls for it:

| Level | What loads | When | Token budget |
|---|---|---|---|
| 1. Metadata | `name` + `description` from frontmatter | At startup, for all installed skills | ~100 tokens per skill |
| 2. Instructions | Full `SKILL.md` body | When the skill is activated | < 5,000 tokens recommended |
| 3. Resources | Files in scripts/, references/, assets/ | Only when referenced in instructions | As needed |

This means you can install many skills without consuming context. The
agent sees only metadata for all skills, loads full instructions for the
one it activates, and reads resource files only when instructed to.

## Directory structure

```
skill-name/
├── SKILL.md          # Required: metadata + core instructions (< 500 lines)
├── scripts/          # Optional: executable code
│   └── validate.py
├── references/       # Optional: detailed documentation
│   ├── api-errors.md
│   └── schema.yaml
├── assets/           # Optional: templates, static resources
│   └── report-template.md
└── evals/            # Optional: test cases
    └── evals.json
```

### scripts/

Executable code that agents can run. Scripts should:

- Be self-contained or clearly document dependencies
- Include helpful error messages
- Handle edge cases gracefully

Supported languages depend on the agent implementation. Common options:
Python, Bash, JavaScript.

Reference in SKILL.md:

```markdown
Run validation: `scripts/validate.py output/`
```

### references/

Additional documentation that agents read when needed. Keep individual
reference files focused — agents load these on demand, so smaller files
mean less context consumed per load.

### assets/

Static resources: templates, images, data files (lookup tables, schemas).

## File reference rules

### All additional files MUST be referenced in SKILL.md

Files in scripts/, references/, and assets/ that are NOT referenced in
SKILL.md will NOT be loaded by the agent. Always use Markdown link syntax
with relative paths:

```markdown
See [the reference guide](references/REFERENCE.md) for details.
Run the extraction script: `scripts/extract.py`
```

### Keep references one level deep

Avoid deeply nested reference chains. Don't have a reference file that
references another reference file that references another — the agent
may not follow the chain reliably.

### Use conditional loading instructions

Tell the agent WHEN to load each file rather than pointing generically:

```markdown
# Good — specific trigger
Read [references/api-errors.md](references/api-errors.md) if the API
returns a non-200 status code.

# Good — step-gated
1. Parse input
2. Validate against [schema](references/schema.yaml)
3. If validation fails, check [troubleshooting](references/troubleshooting.md)

# Bad — generic, agent won't know when to load it
See references/ for more details.
```

## Line and token budgets

| Component | Budget | Rationale |
|---|---|---|
| SKILL.md body | < 500 lines, < 5,000 tokens | Loads in full on activation; competes with all other context |
| Each reference file | As small as focused | Loads on demand; smaller = less context per load |
| Frontmatter description | < 1,024 chars | Loads at startup for every skill; carries triggering burden |
| Frontmatter name | < 64 chars | Loads at startup for every skill |

## When to use context: fork

For skills that do heavy investigation:

```yaml
---
name: review-pr
description: Review a pull request for code quality, style, and correctness
context: fork
---
```

Forked context runs the skill in a dedicated subagent. Only the final
result returns to the parent agent. Use for skills that:

- Read many files or run lengthy investigations
- Produce a focused result (summary, report, small set of edits)
- Should not influence the parent agent beyond final output

Requires `github.copilot.chat.skillTool.enabled` in VS Code settings.

## VS Code skill locations

| Scope | Locations |
|---|---|
| Project skills | `.github/skills/`, `.claude/skills/`, `.agents/skills/` |
| Personal skills | `~/.copilot/skills/`, `~/.claude/skills/`, `~/.agents/skills/` |

Configure additional locations via `chat.agentSkillsLocations` setting.
In monorepos, enable `chat.useCustomizationsInParentRepositories` for
parent repository discovery.
