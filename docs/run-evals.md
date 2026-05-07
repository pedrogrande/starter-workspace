# Run Evals

> Claude Code prompt. Open Claude Code in this repo and paste:
> `Run docs/run-evals.md`

You're running the agent platform's eval suite, diagnosing every failure, fixing what's in scope, and stopping when all cases pass. Surface area is two files: [`evals/cases.py`](../evals/cases.py) (declares cases) and [`evals/__main__.py`](../evals/__main__.py) (runner). Each case uses agno's built-in [`AccuracyEval`](https://docs.agno.com/evals/accuracy) (LLM judge against `expected_output`) and/or [`ReliabilityEval`](https://docs.agno.com/evals/reliability) (asserts which tools fired) — no custom DSL.

## 0. Preconditions

- Postgres up: `docker compose ps` shows `agentos-db`. If not, `docker compose up -d agentos-db`.
- `OPENAI_API_KEY` exported (and `PARALLEL_API_KEY` if you have one — the runner pins the expected web-search tool name based on it).
- Venv active: `source .venv/bin/activate`. `evals/cases.py` imports the agents directly from `agents/`, so no AgentOS server has to be running.

If the user hasn't loaded their env into the shell, run:

```bash
set -a && source .env && set +a
```

## 1. Run the suite

```bash
python -m evals
```

Output ends with a summary block. Exit code is 0 on all-pass, non-zero on any failure or error.

To re-run a single case while iterating:

```bash
python -m evals --case <name>
```

## 2. Diagnose each failure

For every failed case, decide which kind of failure it is and fix at the appropriate layer:

| Symptom | Likely cause | Where to fix |
|---|---|---|
| Judge scores 5-7, says "answer is right but missing X" | Agent's instructions don't push for X | `agents/<slug>.py` — tighten the rule |
| Judge scores low, response is fabricated | Agent hallucinated when it should have said it didn't know | Add a "if you can't find a real source, say so plainly" rule to the agent's instructions |
| Reliability fails: "missing tool X" | Agent didn't call the expected tool on this prompt | (a) Strengthen the routing rule in instructions, OR (b) the case is too narrow — broaden `expected_tool_calls` or drop the assertion |
| Reliability fails: "additional tool Y called" with `allow_additional_tool_calls=False` | Agent fanned out beyond the case's expectation | Tighten the agent's instructions OR set `allow_additional_tool_calls=True` |
| Many cases fail at once | Broad regression — model swap, MCP server down, tool removed | Diagnose the root cause first; do NOT paper over with prompt edits |
| `eval_db` write errors | Postgres down or migration missing | Bring DB up; check `docker logs agentos-db` |

**Rule:** never weaken a case to make it green. Edit a case only when the assertion was wrong (overspecified rubric, wrong tool name, mismatch with how the agent's tools are named today). Catching a real regression is the whole point.

## 3. Fix scope

In scope from this prompt:

- `agents/<slug>.py` — instructions, tools, model.
- `evals/cases.py` — when an assertion was genuinely wrong.
- One-line config flips in `app/main.py` if a case requires it (rare).

Out of scope (flag for the user, don't do):

- Removing cases.
- Editing `db/` or `app/` to make a case pass.
- Editing agno itself.

For agent quality issues that need fast iteration against a live container (cURL probes, instruction tweaks), hand off to [`docs/improve-agent.md`](improve-agent.md). That loop is faster than running the full eval suite per change.

## 4. Re-run and stop

After each fix, re-run the failing case:

```bash
python -m evals --case <name>
```

When all targeted cases pass, run the full suite once more to confirm nothing regressed:

```bash
python -m evals
```

Stop when `python -m evals` exits 0.

## 5. Add a new case (if needed)

If diagnosing a failure reveals a missing assertion, add it to [`evals/cases.py`](../evals/cases.py):

```python
Case(
    name="<short_id>",
    agent=<the_agent>,
    input="<prompt>",
    # Either or both of:
    expected_output="<rubric describing a correct response>",
    expected_tool_calls=("<tool_name>",),
)
```

Run `python -m evals --case <name>` to confirm it passes against the current agent. Commit the new case alongside any fixes.

## 6. Track regressions over time

Every case logs to Postgres via `db=eval_db`. Connect your AgentOS at [os.agno.com](https://os.agno.com) and view eval history — useful for catching slow drift on a weekly cron.

To run on a schedule, register the eval suite as a scheduled task on the AgentOS scheduler — see [agno scheduler docs](https://docs.agno.com/agent-os/scheduler).

---

## Reference: Case shape

```python
@dataclass(frozen=True)
class Case:
    name: str
    agent: Agent
    input: str

    # Accuracy (LLM judge): set both to enable.
    expected_output: str | None = None
    accuracy_threshold: int = 7

    # Reliability (tool-call assertion): set to enable.
    expected_tool_calls: tuple[str, ...] | None = None
    allow_additional_tool_calls: bool = True
```

A case with both checks set runs the agent twice (once for accuracy, once for reliability) — accept the cost or split into two cases if it bites.
