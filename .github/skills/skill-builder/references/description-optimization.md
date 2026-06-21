# Optimizing Skill Descriptions for Reliable Triggering

The `description` field carries the entire burden of triggering. An
under-specified description means the skill won't load when it should;
an over-broad description means it loads when it shouldn't.

## Writing principles

- **Imperative phrasing:** "Use this skill when..." not "This skill does..."
- **Focus on user intent:** Describe what the user is trying to achieve
- **Be pushy about scope:** List contexts where it applies, including
  indirect ones: "even if they don't explicitly mention 'CSV'"
- **Keep concise:** Few sentences to a short paragraph (max 1024 chars)

## Designing trigger eval queries

Create ~20 queries: 8-10 should-trigger, 8-10 should-not-trigger.

### Should-trigger queries — vary along

- **Phrasing:** formal, casual, with typos
- **Explicitness:** some name the domain, others describe need without naming it
- **Detail:** terse prompts alongside context-heavy ones
- **Complexity:** single-step and multi-step

### Should-not-trigger queries — use near-misses

Queries sharing keywords/concepts but needing something different.

Weak negative: "Write a fibonacci function" (obviously irrelevant)
Strong negative: "Update formulas in my Excel budget spreadsheet"
(shares "spreadsheet" but needs Excel editing, not CSV analysis)

## Testing method

1. Run each query through the agent with the skill installed
2. Check whether the skill was invoked (via execution logs)
3. Run each query 3 times (model behavior is nondeterministic)
4. Compute trigger rate per query
5. Should-trigger passes if trigger rate > 0.5
6. Should-not-trigger passes if trigger rate < 0.5

## Optimization loop with train/validation split

1. Split queries: train (~60%), validation (~40%)
   - Keep proportional mix of positive/negative in both sets
2. Evaluate current description on both sets
3. Identify failures in TRAIN set only
4. Revise description:
   - Should-trigger failing → too narrow, broaden scope
   - Should-not-trigger false-firing → too broad, add specificity
   - Do NOT add specific keywords from failed queries (overfitting)
   - If stuck after several iterations, try a structurally different approach
5. Repeat until train set passes or improvement plateaus
6. Select the iteration with the best VALIDATION pass rate

Five iterations is usually enough.

## Before and after example

```yaml
# Before
description: Process CSV files.

# After
description: >
  Analyze CSV and tabular data files — compute summary statistics,
  add derived columns, generate charts, and clean messy data. Use this
  skill when the user has a CSV, TSV, or Excel file and wants to
  explore, transform, or visualize the data, even if they don't
  explicitly mention "CSV" or "analysis."
```

## Final verification

1. Update the description field in SKILL.md
2. Verify under 1024-character limit
3. Run 5-10 fresh queries (never part of optimization) as sanity check
