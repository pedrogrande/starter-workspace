"""
Auto-Improve Agent
==================

Hill-climbing loop that uses the eval suite as the verifier:

    python -m evals.auto_improve --agent web-search --max-iters 5

Each iteration:
  1. run target agent's eval cases → identify failures
  2. ask an improver agent for new INSTRUCTIONS given the current ones + failure traces
  3. apply in-memory, re-run cases
  4. if strictly better (no regressions, ≥1 new pass) — persist to file
     otherwise — revert in-memory and stop / try again

Refuses to start when ``agents/<slug>.py`` has uncommitted changes, so any
accepted edit is easy to review with ``git diff`` and revert with
``git checkout``.
"""

from __future__ import annotations

import ast
import asyncio
import difflib
import subprocess
from dataclasses import dataclass
from pathlib import Path

import typer
from agno.agent import Agent
from rich.console import Console

from app.settings import default_model
from evals.__main__ import CaseOutcome, run_case
from evals.cases import CASES, Case

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "agents"

console = Console()
app = typer.Typer(add_completion=False, no_args_is_help=False, pretty_exceptions_show_locals=False)


IMPROVER_INSTRUCTIONS = """\
You improve an Agno agent's INSTRUCTIONS string. You receive the current
INSTRUCTIONS plus one or more failing eval cases (input, expected, actual,
accuracy score, reliability check).

Output a NEW INSTRUCTIONS string that fixes the failures.

Rules:
- Edit surgically. Pick ONE lever (wording, ordering, emphasis).
- Prefer narrowing ("on recent-events questions, follow up with at least
  one fetch") over forbidding ("never search without fetching").
- Keep changes short. If you'd add more than ~3 lines, back up and try
  removing or rewording instead.
- Don't bolt onto the end. Integrate into the existing structure.
- Output ONLY the new INSTRUCTIONS string verbatim. No preamble, no
  markdown fences, no explanation. The output is written into the agent
  file as-is.
"""


def _build_improver() -> Agent:
    return Agent(
        id="auto-improver",
        name="AutoImprover",
        model=default_model(),
        instructions=IMPROVER_INSTRUCTIONS,
        markdown=False,
    )


@dataclass
class FailureTrace:
    name: str
    input: str
    expected_output: str | None
    expected_tool_calls: tuple[str, ...] | None
    accuracy_score: float | None
    reliability_passed: bool | None
    actual_response: str


# --------------------------------------------------------------------------
# git + filesystem helpers
# --------------------------------------------------------------------------
def _has_uncommitted_changes(file_path: Path) -> bool:
    result = subprocess.run(
        ["git", "diff", "--quiet", "--", str(file_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
    )
    return result.returncode != 0


def _file_for_slug(slug: str) -> Path:
    path = AGENTS_DIR / f"{slug.replace('-', '_')}.py"
    if not path.exists():
        raise typer.BadParameter(f"agent file not found: {path}")
    return path


def _agent_for_slug(slug: str) -> Agent:
    for case in CASES:
        if case.agent.id == slug:
            return case.agent
    raise typer.BadParameter(f"no agent with id {slug!r} in evals/cases.py")


def _cases_for(slug: str) -> list[Case]:
    return [c for c in CASES if c.agent.id == slug]


# --------------------------------------------------------------------------
# AST-based read/write of the *_INSTRUCTIONS string literal
# --------------------------------------------------------------------------
def _find_instructions_node(source: str) -> ast.Assign:
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not target.id.endswith("_INSTRUCTIONS"):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            continue
        return node
    raise RuntimeError("no `*_INSTRUCTIONS = '...'` assignment found")


def _read_instructions(file_path: Path) -> str:
    node = _find_instructions_node(file_path.read_text())
    return node.value.value  # type: ignore[attr-defined,no-any-return]


def _write_instructions(file_path: Path, new_value: str) -> None:
    if '"""' in new_value:
        raise RuntimeError("proposed instructions contain a triple-quote; refusing to write")
    source = file_path.read_text()
    node = _find_instructions_node(source)
    if not new_value.endswith("\n"):
        new_value += "\n"
    var_name = node.targets[0].id  # type: ignore[attr-defined]
    replacement = f'{var_name} = """\\\n{new_value}"""'
    lines = source.splitlines(keepends=True)
    before = "".join(lines[: node.lineno - 1])
    after = "".join(lines[node.end_lineno :])
    file_path.write_text(before + replacement + "\n" + after)


# --------------------------------------------------------------------------
# eval orchestration + failure trace capture
# --------------------------------------------------------------------------
def _run_cases(cases: list[Case]) -> list[CaseOutcome]:
    outcomes: list[CaseOutcome] = []
    for c in cases:
        outcome = run_case(c)
        outcomes.append(outcome)
        status = "[green]PASS[/green]" if outcome.passed else "[red]FAIL[/red]"
        score = f" {outcome.accuracy_score:.1f}/10" if outcome.accuracy_score is not None else ""
        console.print(f"  {status} {c.name}{score}")
    return outcomes


def _build_failure_traces(failures: list[tuple[Case, CaseOutcome]]) -> list[FailureTrace]:
    async def _all() -> list[FailureTrace]:
        traces: list[FailureTrace] = []
        for case, outcome in failures:
            response = await case.agent.arun(input=case.input, stream=False)
            traces.append(
                FailureTrace(
                    name=case.name,
                    input=case.input,
                    expected_output=case.expected_output,
                    expected_tool_calls=case.expected_tool_calls,
                    accuracy_score=outcome.accuracy_score,
                    reliability_passed=outcome.reliability_passed,
                    actual_response=response.content or "",
                )
            )
        return traces

    return asyncio.run(_all())


def _build_improver_prompt(slug: str, instructions: str, traces: list[FailureTrace]) -> str:
    parts = [
        f"Agent: {slug}",
        "",
        "## Current INSTRUCTIONS",
        "",
        instructions.strip(),
        "",
        f"## Failing cases ({len(traces)})",
    ]
    for t in traces:
        parts += ["", f"### {t.name}", f"Input: {t.input}"]
        if t.expected_output:
            parts.append(f"Expected behavior: {t.expected_output}")
        if t.expected_tool_calls:
            parts.append(f"Expected tool calls: {list(t.expected_tool_calls)}")
        if t.accuracy_score is not None:
            parts.append(f"Accuracy score: {t.accuracy_score:.1f}/10 (need >= 7)")
        if t.reliability_passed is False:
            parts.append("Reliability check: FAILED (wrong tools fired)")
        parts.append(f"Actual response:\n{t.actual_response}")
    parts += ["", "Output the new INSTRUCTIONS string now."]
    return "\n".join(parts)


def _strictly_better(new: list[CaseOutcome], old: list[CaseOutcome]) -> bool:
    new_pass = {o.name for o in new if o.passed}
    old_pass = {o.name for o in old if o.passed}
    return bool(new_pass - old_pass) and not (old_pass - new_pass)


def _print_diff(old: str, new: str) -> None:
    diff = "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile="before",
            tofile="after",
        )
    )
    if diff:
        # rich would interpret rule-style brackets in the diff body; print plain.
        console.print(diff, style="dim", highlight=False, markup=False)


def _clean_improver_output(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        body = text.split("\n", 1)[1] if "\n" in text else ""
        if body.endswith("```"):
            body = body[:-3]
        text = body.strip()
    return text


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    slug: str = typer.Option(..., "--agent", help="Agent id (e.g. web-search)"),
    max_iters: int = typer.Option(5, "--max-iters", help="Max improvement iterations"),
) -> None:
    """Hill-climb on an agent's INSTRUCTIONS using the eval suite as verifier."""
    if ctx.invoked_subcommand is not None:
        return

    file_path = _file_for_slug(slug)
    cases = _cases_for(slug)
    if not cases:
        console.print(f"[red]no eval cases for agent {slug!r}[/red]")
        raise typer.Exit(2)
    if _has_uncommitted_changes(file_path):
        console.print(f"[red]{file_path} has uncommitted changes — commit or stash first.[/red]")
        raise typer.Exit(2)

    agent = _agent_for_slug(slug)
    improver = _build_improver()
    current_instructions = _read_instructions(file_path)

    console.rule("[bold]baseline[/bold]")
    current_outcomes = _run_cases(cases)
    if all(o.passed for o in current_outcomes):
        console.print("\n[green]all cases already pass — nothing to do.[/green]")
        return

    last_proposal: str | None = None

    for i in range(1, max_iters + 1):
        console.rule(f"[bold]iter {i}/{max_iters}[/bold]")
        failures = [(c, o) for c, o in zip(cases, current_outcomes) if not o.passed]
        if not failures:
            console.print("[green]all cases pass — done.[/green]")
            break

        traces = _build_failure_traces(failures)
        prompt = _build_improver_prompt(slug, current_instructions, traces)
        response = asyncio.run(improver.arun(input=prompt, stream=False))
        proposed = _clean_improver_output(response.content or "")

        if not proposed:
            console.print("[yellow]improver returned empty output — stopping.[/yellow]")
            break
        if proposed == current_instructions.strip():
            console.print("[yellow]improver returned identical instructions — stopping.[/yellow]")
            break
        if proposed == last_proposal:
            console.print("[yellow]improver repeated previous proposal — stopping.[/yellow]")
            break
        last_proposal = proposed

        _print_diff(current_instructions.rstrip() + "\n", proposed + "\n")

        agent.instructions = proposed
        new_outcomes = _run_cases(cases)

        if _strictly_better(new_outcomes, current_outcomes):
            console.print("[green]✓ accepted (strict improvement) — persisting to file[/green]")
            _write_instructions(file_path, proposed)
            current_instructions = _read_instructions(file_path)
            current_outcomes = new_outcomes
        else:
            console.print("[red]✗ rejected (no improvement or regression) — reverting in memory[/red]")
            agent.instructions = current_instructions

    console.rule("[bold]final[/bold]")
    passed = sum(1 for o in current_outcomes if o.passed)
    total = len(current_outcomes)
    style = "green" if passed == total else "yellow"
    console.print(f"[{style}]{passed}/{total} cases passing[/{style}]")
    if passed < total:
        console.print("[dim]review changes with `git diff`. revert with `git checkout -- agents/`[/dim]")
    raise typer.Exit(0 if passed == total else 1)


if __name__ == "__main__":
    app()
