# Writing Guide: Content Principles and Expertise Sourcing

How to write skill content that adds value without wasting context.

## Add what the agent lacks, omit what it knows

Before adding each piece of content, ask:

```
Would the agent get this wrong without this instruction?
  → YES: Keep it
  → NO:  Cut it
  → UNSURE: Test it (run with and without, compare results)
```

You don't need to explain what a database migration is, but you do need
to specify that your project uses a specific migration tool with a
specific flag order. If the agent already handles the entire task well
without the skill, the skill may not be adding value.

### Example

**Too verbose** — the agent already knows this:

```markdown
## Deploy the service

Docker is a containerization platform that packages applications
and their dependencies into a standardized unit. To deploy, you
need to build an image and run it.
```

**Better** — jumps to what the agent wouldn't know:

```markdown
## Deploy the service

Build and deploy in one step:

```bash
./scripts/deploy.sh --env staging --verify-health
```

The `--verify-health` flag polls `/ready` (not `/health`) until
it returns 200 or times out after 60 seconds.

```

## Aim for moderate detail

Concise, stepwise guidance with one working example outperforms
exhaustive documentation. The agent has strong general capabilities.
Your skill adds the specific layer it lacks, not re-documentation of
everything.

Overly comprehensive skills can hurt: the agent struggles to extract
what's relevant and may pursue unproductive paths triggered by
instructions that don't apply to the current task.

## Design coherent units

Scope a skill like a function: encapsulate a coherent unit of work
that composes well with other skills.

| Too narrow | Coherent | Too broad |
|---|---|---|
| Skill for reading a CSV | Skill for analyzing tabular data (read, transform, visualize) | Skill for all data tasks (analysis + pipeline admin + ML) |
| Skill for running one linter | Skill for code quality checks (lint + format + type-check) | Skill for all CI/CD tasks |
| Skill for writing a commit message | Skill for git operations (commit, branch, PR) | Skill for all version control + deployment |

### Scoping questions

- Does this compose well with other skills?
- Would multiple skills need to load simultaneously for a single task? → too narrow
- Is the description hard to write precisely? → too broad
- Would it trigger on too many unrelated tasks? → too broad
- Does the SKILL.md exceed 500 lines? → probably too broad, split it

## Start from real expertise

### Extract from a hands-on task

Complete a real task with an agent, providing corrections and context.
Then extract the reusable pattern.

| Signal | What to look for | Where it goes in SKILL.md |
|---|---|---|
| Steps that worked | The sequence that led to success | Step-by-step instructions |
| Corrections you made | Where you steered the agent away from a wrong approach | Gotchas section |
| Input/output formats | What data looked like going in and coming out | Templates or examples |
| Context you provided | Project-specific facts the agent didn't know | Instructions body or references/ |

In VS Code, type `/create-skill` after completing a task, or ask
"create a skill from how we just solved that" to extract the workflow.

### Synthesize from existing project artifacts

Feed real source material into the LLM to synthesize a skill:

- **Internal docs, runbooks, style guides** → reference material
- **API specs, schemas, config files** → references/ directory
- **Code review comments, issue trackers** → gotchas and constraints
- **Version control history** (patches and fixes) → edge case patterns
- **Real-world failure cases and resolutions** → gotchas section

A skill synthesized from your team's actual incident reports will
outperform one synthesized from a generic "best practices" article
because it captures your schemas, failure modes, and recovery procedures.

The key is project-specific material, not generic references.

## Conditional loading instructions

When moving content to reference files, tell the agent WHEN to load
each file. This is how progressive disclosure works in practice.

**Good** — specific trigger:
```markdown
Read [references/api-errors.md](references/api-errors.md) if the API
returns a non-200 status code.
```

**Bad** — generic pointer:

```markdown
See references/ for details.
```

**Good** — step-gated:

```markdown
1. Parse the input file
2. Validate against [schema](references/schema.yaml)
3. If validation fails, check [troubleshooting](references/troubleshooting.md)
4. Generate output using [template](assets/output-template.md)
```

Each reference loads only when the agent reaches that step. If the task
doesn't need troubleshooting, that file never enters context.
