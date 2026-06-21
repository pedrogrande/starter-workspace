---
name: {{skill-name}}
description: >
  {{Describe what the skill does AND when to use it. Use imperative
  phrasing. Include specific keywords and indirect trigger contexts.
  Max 1024 characters.}}
argument-hint: {{[optional argument hint]}}
# context: fork  # Uncomment for heavy/investigative skills
---

# {{Skill Title}}

{{One-sentence summary of what this skill helps accomplish.}}

## When to use this skill

- {{Specific trigger condition 1}}
- {{Specific trigger condition 2}}
- {{Indirect trigger context — tasks that need this but don't name it}}

## {{Core workflow section}}

1. {{Step 1}}
2. {{Step 2 — reference scripts as: Run `scripts/do-thing.py`}}
3. {{Step 3 — reference files as: Check [reference](references/detail.md)}}

## Gotchas

- {{Concrete, environment-specific correction the agent would get wrong}}
- {{Non-obvious fact that defies reasonable assumptions}}
- {{ naming mismatch, soft delete, endpoint quirk, etc. }}

## {{Optional: Output template}}

Use this template for {{output type}}:

\```{{format}}
{{template content}}
\```

## {{Optional: Validation loop}}

1. {{Do the work}}
2. Run validation: `{{validation command}}`
3. If validation fails, fix and re-run
4. Only proceed when validation passes

## {{Optional: Checklist}}

Progress:

- [ ] {{Step 1}}
- [ ] {{Step 2}}
- [ ] {{Step 3}}
