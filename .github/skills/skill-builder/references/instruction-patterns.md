# Instruction Patterns for Effective Skills

Reusable techniques for structuring skill content. Not every skill needs
all of them — use the ones that fit your task.

## Gotchas sections

The highest-value content in many skills. Environment-specific facts that
defy reasonable assumptions — concrete corrections to mistakes the agent
WILL make without being told.

```markdown
## Gotchas

- The `users` table uses soft deletes. Queries MUST include
  `WHERE deleted_at IS NULL` or results include deactivated accounts.
- User ID is `user_id` in the DB, `uid` in the auth service, and
  `accountId` in the billing API. All three refer to the same value.
- The `/health` endpoint returns 200 even if the DB is down.
  Use `/ready` to check full service health.
```

Keep gotchas in SKILL.md where the agent reads them BEFORE encountering
the situation. Add corrections here whenever you catch the agent making
a mistake during real execution.

## Templates for output format

Agents pattern-match well against concrete structures. Provide a template
when you need specific output formatting.

```markdown
## Report structure

\```markdown
# [Analysis Title]

## Executive summary
[One-paragraph overview of key findings]

## Key findings
- Finding 1 with supporting data

## Recommendations
1. Specific actionable recommendation
\```
```

Short templates inline in SKILL.md. Longer templates or conditional
templates in `assets/`:

```markdown
For detailed reports, use the [full report template](assets/report-template.md).
```

## Checklists for multi-step workflows

Help the agent track progress and avoid skipping steps.

```markdown
## Deployment workflow

Progress:
- [ ] Step 1: Run tests (`npm test -- --coverage`)
- [ ] Step 2: Build bundle (`npm run build`)
- [ ] Step 3: Verify bundle size (`scripts/check-bundle-size.sh`)
- [ ] Step 4: Deploy to staging (`scripts/deploy.sh --env staging`)
- [ ] Step 5: Verify health (`scripts/health-check.sh staging`)
```

## Validation loops

Instruct the agent to validate its own work before proceeding.

```markdown
## Editing workflow

1. Make your edits
2. Run validation: `python scripts/validate.py output/`
3. If validation fails:
   - Review the error message
   - Fix the issues
   - Run validation again
4. Only proceed when validation passes
```

### READS/WRITES/NEVER permission framework

For skills with security-sensitive operations:

```markdown
## Permissions

READS:
  - All source files in src/
  - Test files in tests/

WRITES:
  - Output files in output/
  - Test results in test-results/

NEVER:
  - Modify source files during validation
  - Skip the validation step
  - Proceed if validation has any failures
```

## Plan-validate-execute

For batch or destructive operations: create an intermediate plan, validate
it against a source of truth, then execute.

```markdown
## Form processing

1. Extract form fields: `scripts/analyze_form.py input.pdf` → `form_fields.json`
2. Create `field_values.json` mapping each field to its intended value
3. Validate: `scripts/validate_fields.py form_fields.json field_values.json`
4. If validation fails, revise and re-validate
5. Fill: `scripts/fill_form.py input.pdf field_values.json output.pdf`
```

The key ingredient is step 3: a validation step checking the plan against
a source of truth. Error messages should give the agent enough information
to self-correct.

## Bundling reusable scripts

When iterating, watch for the agent independently reinventing the same
logic each run. That's a signal to write a tested script once and bundle
it in `scripts/`.

Scripts should:

- Be self-contained or clearly document dependencies
- Include helpful error messages
- Handle edge cases gracefully

Reference in SKILL.md:

```markdown
Run validation: `scripts/validate.py output/`
```

## Calibrating control

### Fragility spectrum

```
FLEXIBLE ←────────────────────────────→ FRAGILE
  Give freedom              Be prescriptive
  Explain why               Give exact commands
  Accept variation          Require exact sequence
```

### When to be flexible

Multiple valid approaches, task tolerates variation:

- Explain WHY, not just WHAT
- Let the agent make context-dependent decisions
- Example: code review guidelines (what to look for, not exact steps)

### When to be prescriptive

Fragile operations, consistency matters, specific sequence:

- Give exact commands
- Say "Do not modify" or "Do not add additional flags"
- Example: database migration commands

### Provide defaults, not menus

```markdown
<!-- Wrong: too many equal options -->
You can use pypdf, pdfplumber, PyMuPDF, or pdf2image...

<!-- Right: clear default with escape hatch -->
Use pdfplumber for text extraction. For scanned PDFs requiring OCR,
use pdf2image with pytesseract instead.
```

### Favor procedures over declarations

```markdown
<!-- Wrong: specific answer for one instance -->
Join orders to customers on customer_id, filter region = 'EMEA',
sum the amount column.

<!-- Right: reusable method -->
1. Read the schema from [references/schema.yaml](references/schema.yaml)
2. Join tables using the `_id` foreign key convention
3. Apply filters from the user's request as WHERE clauses
4. Aggregate numeric columns and format as a markdown table
```
