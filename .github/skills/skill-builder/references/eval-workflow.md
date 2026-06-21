# Evaluating Skill Output Quality

Structured evaluation gives you a feedback loop for improving skills
systematically.

## Designing test cases

Store in `evals/evals.json`:

```json
{
  "skill_name": "my-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "Realistic user message with file paths and context",
      "expected_output": "Human-readable description of success",
      "files": ["evals/files/input.csv"],
      "assertions": [
        "The output file is valid JSON",
        "The chart has labeled axes",
        "At least 3 recommendations included"
      ]
    }
  ]
}
```

Tips:

- Start with 2-3 test cases. Expand later.
- Vary phrasing, detail, formality.
- Include edge cases (malformed input, unusual requests).
- Use realistic context (file paths, column names, personal context).
- Add assertions AFTER the first run — you don't know "good" until you see output.

## Running evals

Run each test case twice: with skill and without skill (baseline).

### In VS Code

- Use separate chat sessions for each run (clean context)
- Or use subagents for automatic context isolation
- Save outputs to structured directories:

```
my-skill-workspace/
└── iteration-1/
    ├── eval-1/
    │   ├── with_skill/
    │   │   ├── outputs/
    │   │   └── grading.json
    │   └── without_skill/
    │       ├── outputs/
    │       └── grading.json
    └── benchmark.json
```

## Writing assertions

Good assertions are specific, observable, and verifiable:

- "The output file is valid JSON" — programmatically checkable
- "The bar chart has labeled axes" — specific and observable
- "The report includes at least 3 recommendations" — countable

Weak assertions:

- "The output is good" — too vague
- "Uses exactly the phrase 'Total Revenue: $X'" — too brittle

Not everything needs an assertion. Writing style, visual design, and
"feels right" qualities are better caught during human review.

## Grading

Evaluate each assertion: PASS or FAIL with concrete evidence.

- Require concrete evidence for PASS (don't give benefit of the doubt)
- Use verification scripts for mechanical checks (valid JSON, row count)
- Use LLM judge for qualitative checks
- For comparing versions: blind comparison (don't reveal which is which)

## Analyzing patterns

| Pattern | Action |
|---|---|
| Always pass in both configs | Remove — not testing skill value |
| Always fail in both configs | Fix assertion or test case |
| Pass with skill, fail without | Study — this is skill value |
| High variance across runs | Add examples, reduce ambiguity |

## Iteration loop

1. Collect signals: failed assertions + human feedback + execution transcripts
2. Give all signals + current SKILL.md to an LLM → propose improvements
3. Guidelines for the LLM:
   - Generalize from feedback (don't patch specific examples)
   - Keep the skill lean (fewer, better instructions > exhaustive rules)
   - Explain the WHY (reasoning-based > rigid directives)
   - Bundle repeated work into scripts
4. Apply changes → rerun in new iteration-N/ directory
5. Compare benchmark.json across iterations
6. Stop when: satisfied / feedback empty / no meaningful improvement
