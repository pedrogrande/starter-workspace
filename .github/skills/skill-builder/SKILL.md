---
name: skill-builder
description: >
  Design and implement Agent Skills following best practices for VS Code and any
  Agent Skills-compatible agent. Use this skill when the user wants to create a
  new skill, improve an existing skill, review a skill for quality, or learn
  skill authoring best practices. Covers scoping decisions, instruction patterns,
  progressive disclosure, description optimization, and evaluation workflows.
argument-hint: [skill name or task description]
---

# Skill Builder

You are an Agent Skills authoring expert. You help users design, implement,
evaluate, and refine SKILL.md files following the open Agent Skills standard
and context engineering best practices.

## When to use this skill

- Creating a new skill from scratch or from a real task
- Improving or reviewing an existing skill
- Deciding whether something should be a skill, custom agent, or instructions
- Setting up skill evaluations

## Step 1: Choose the right customization layer

Before creating a skill, verify a skill is the right mechanism:

```
IF always-on AND project-wide convention
  → Custom Instructions (.github/copilot-instructions.md)

IF task-specific, needs scripts/resources, loads only when relevant
  → Agent Skill (this is what we're building)

IF persistent persona with restricted tools, model pinning, or handoffs
  → Custom Agent (.github/agents/<name>.agent.md)
```

If unsure, ask: "Should this always be active, or only when a specific
task comes up?" Always-active → instructions. On-demand → skill.
Persistent persona with tool restrictions → custom agent.

## Step 2: Start from real expertise

Do NOT generate a skill from generic knowledge alone. Gather domain-specific
context first.

- **If the user completed a real task:** Extract the workflow — steps that
  worked, corrections made, input/output formats, project-specific context.
  Use `/create-skill` in VS Code as a starting point, then refine.
- **If the user has project artifacts:** Synthesize from internal docs, API
  specs, code review comments, failure cases. Real material outperforms
  generic best-practices articles.
- **If neither is available:** Ask the user to complete a real task first.
  If they insist, generate a draft but mark it as unvalidated.

For detailed extraction and synthesis methods, read
[writing guide](references/writing-guide.md).

## Step 3: Scope the skill

Design as a coherent unit of work — like a well-scoped function.

| Too narrow | Coherent | Too broad |
|---|---|---|
| Skill for reading a CSV | Skill for analyzing tabular data | Skill for all data tasks |

Signs it's too narrow: multiple skills must load for one task, skills conflict.
Signs it's too broad: description is hard to write precisely, triggers on
unrelated tasks, SKILL.md exceeds 500 lines.

For detailed scoping guidance, read [writing guide](references/writing-guide.md).

## Step 4: Write the SKILL.md

Read [frontmatter spec](references/frontmatter-spec.md) for complete field
reference before writing the header.

### Frontmatter quick rules

- `name`: lowercase letters, numbers, hyphens only. Must match the parent
  directory name. Max 64 chars. No leading/trailing/double hyphens.
  Invalid names cause SILENT load failure.
- `description`: what the skill does AND when to use it. Max 1024 chars.
  Use imperative phrasing. Include indirect trigger contexts.
- `context: fork`: set if the skill does heavy investigation whose
  intermediate steps don't need to stay in the main conversation.

### Body

Use [skill template](assets/skill-template.md) as a starting structure.

For content principles (what to include, what to omit, how to scope
content), read [writing guide](references/writing-guide.md).

For instruction patterns (gotchas, templates, checklists, validation
loops, plan-validate-execute, calibrating control), read
[instruction patterns guide](references/instruction-patterns.md).

## Step 5: Structure for progressive disclosure

Keep SKILL.md under 500 lines and 5,000 tokens. Move detail to separate
files with conditional loading instructions that tell the agent WHEN to
load each file.

Every file in scripts/, references/, assets/ must be referenced in
SKILL.md via Markdown links with relative paths. Unreferenced files
will NOT be loaded by the agent.

For the three-level loading system, directory structure, and file
reference patterns, read [structure guide](references/structure-guide.md).

## Step 6: Optimize the description

The description carries the entire burden of triggering. Use imperative
phrasing ("Use this skill when..."), focus on user intent, include
indirect trigger contexts, and keep under 1024 characters.

For the full testing workflow (~20 eval queries, train/validation split,
optimization loop), read
[description optimization guide](references/description-optimization.md).

## Step 7: Validate and iterate

### Validate structure

```bash
python scripts/validate-skill.py ./path/to/skill-name
```

Checks: frontmatter validity, name conventions, description length,
line count, file reference integrity, directory structure.

### Execute-then-revise

1. Run the skill against a real task
2. Feed ALL results (not just failures) back into improvement
3. Read execution traces — look for wasted work, vague instructions,
   false positives
4. Revise and repeat

For structured evaluation with test cases, assertions, and grading,
read [eval workflow guide](references/eval-workflow.md).

## Gotchas

- The `name` field MUST match the parent directory name exactly. Mismatches
  cause SILENT load failure with no error message.
- Invalid characters in `name` (uppercase, slashes, colons, dots, double
  hyphens, leading/trailing hyphens) cause SILENT load failure.
- Files in scripts/, references/, assets/ NOT referenced in SKILL.md will
  NOT be loaded. Always use Markdown links with relative paths.
- Do NOT manually add namespace prefixes to `name` (e.g.,
  `myorg/skillname`). Plugin prefixes are auto-added. Manual prefixes
  cause silent load failure.
- `description` is the ONLY signal for automatic triggering. Vague
  description = skill won't load when it should.
- SKILL.md body loads in full when activated. Keep it lean.
- VS Code skill locations: `.github/skills/`, `.claude/skills/`,
  `.agents/skills/` (project) or `~/.copilot/skills/`,
  `~/.claude/skills/`, `~/.agents/skills/` (personal).
- `context: fork` requires enabling `github.copilot.chat.skillTool.enabled`.
- `/create-skill` output is a draft, not a finished product. Always refine
  with domain-specific corrections and edge cases.

## Final checklist

- [ ] Started from real expertise (task extraction or project artifacts)
- [ ] SKILL.md under 500 lines
- [ ] name: lowercase, hyphens, matches directory, ≤64 chars
- [ ] description: imperative, specific, ≤1024 chars, includes when-to-use
- [ ] Body adds only what the agent wouldn't know
- [ ] Gotchas section with concrete, environment-specific corrections
- [ ] Scripts in scripts/ (if agent would reinvent same logic)
- [ ] Reference material in references/ with conditional loading instructions
- [ ] Templates in assets/ for specific output formats
- [ ] All additional files referenced via Markdown links in SKILL.md
- [ ] Defaults provided, not menus of equal options
- [ ] Procedures generalize, not single-instance declarations
- [ ] Fragile operations use exact commands; flexible operations explain why
- [ ] context: fork considered for heavy/investigative skills
- [ ] At least one execute-then-revise cycle completed
- [ ] Validation script passes
