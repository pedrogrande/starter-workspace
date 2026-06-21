# Eval Workflow for Custom Agents

How to evaluate a `.agent.md` before relying on it. The goal is to catch
over-reaching (using tools it shouldn't), under-performing (missing a
needed tool), and hook failures (rules not enforced).

## Test cases

Write 3-5 test prompts per agent. Each test has:

| Field | Example |
|---|---|
| `prompt` | "Add a prompt injection guardrail to the support agent" |
| `expected_tools` | `["read", "edit", "execute"]` |
| `forbidden_tools` | `["web"]` |
| `expected_files_touched` | `["agents/agno_support.py"]` |
| `forbidden_files_touched` | `["agno/source/agno/"]` |
| `expected_handoff` | `"reviewer"` (or none) |
| `pass_criteria` | "Guardrail import added, pre_hooks set, ruff format ran" |

## Run and observe

1. Invoke the agent with the test prompt.
2. Observe: which tools did it use? Which files did it touch? Did hooks
   fire? Did it hand off?
3. Record actual vs expected.

## Common failure modes and fixes

| Failure | Likely cause | Fix |
|---|---|---|
| Agent used a tool not in its `tools` list | Impossible by design — if this happens, the `tools` field is malformed | Check YAML syntax |
| Agent didn't use a tool it should have | Tool omitted from `tools`, or Process step doesn't reference it | Add the tool, add explicit `:tool-name` in Process |
| Agent edited a forbidden file | Hook didn't fire (setting off) or hook script has a bug | Verify `chat.useCustomAgentHooks=true`, test hook script standalone |
| Agent didn't hand off when expected | Handoff `agent` name doesn't match target, or `send: false` and user didn't click | Verify name match; document the handoff button for users |
| Subagent never invoked by orchestrator | `agents` list missing the subagent, or `agent` tool not in `tools` | Add subagent to `agents`, add `agent` to `tools` |
| Agent gave a prose role description instead of following body format | Body was written as prose, not structured sections | Rewrite body using the five-section template |

## Execute-then-revise loop

1. Run all test cases.
2. For each failure, apply the fix from the table above.
3. Re-run. Feed ALL results (not just failures) back — successes reveal
   where the agent over-specified or did unnecessary work.
4. Revise the agent file. Re-run.
5. Stop when all test cases pass and the agent does no extraneous work.
