"""
Run Evals
==============

python -m evals                # run all cases
python -m evals --case <name>  # run one case

Each case runs the agent once, then optionally checks the response with
`AgentAsJudgeEval` (when `criteria` is set) and `ReliabilityEval` (when
`expected_tool_calls` is set).

Both log to Postgres through `eval_db`. Connect your AgentOS at os.agno.com to see history.

Exit 0 on all-pass, non-zero on any failure or error.
"""

# Hydrate os.environ from .env before any module that reads env at import time
# (db_url, model factories, etc.). Pre-existing shell vars take precedence.
from evals.dotenv import load_dotenv

load_dotenv()

import asyncio  # noqa: E402
from dataclasses import dataclass  # noqa: E402

import typer  # noqa: E402
from agno.eval import AgentAsJudgeEval, ReliabilityEval  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from evals.cases import CASES, Case, eval_db  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=False, pretty_exceptions_show_locals=False)
console = Console()


@dataclass
class CaseOutcome:
    name: str
    judge_passed: bool | None = None
    reliability_passed: bool | None = None
    error: str | None = None

    @property
    def passed(self) -> bool:
        if self.error:
            return False
        checks = [c for c in (self.judge_passed, self.reliability_passed) if c is not None]
        return bool(checks) and all(checks)


async def _run_case_async(case: Case, *, verbose: bool) -> CaseOutcome:
    judge_passed: bool | None = None
    rel_passed: bool | None = None
    judge_err: str | None = None
    rel_err: str | None = None

    # One agent run per case — feeds both checks.
    try:
        response = await case.agent.arun(input=case.input, stream=False)
    except Exception as exc:
        return CaseOutcome(name=case.name, error=f"agent.arun: {type(exc).__name__}: {exc}")

    output_str = str(response.content) if response.content else ""

    if verbose:
        _print_agent_run(case, response, output_str)

    if case.criteria is not None:
        try:
            judge = await AgentAsJudgeEval(
                name=case.name,
                criteria=case.criteria,
                scoring_strategy="binary",
                db=eval_db,
            ).arun(input=case.input, output=output_str, print_results=True)
        except Exception as exc:
            judge_err = f"judge: {type(exc).__name__}: {exc}"
        else:
            if judge and judge.results:
                judge_passed = judge.results[0].passed
            else:
                judge_err = "judge: returned no result"

    if case.expected_tool_calls is not None:
        try:
            rel = ReliabilityEval(
                name=case.name,
                agent_response=response,
                expected_tool_calls=list(case.expected_tool_calls),
                allow_additional_tool_calls=case.allow_additional_tool_calls,
                db=eval_db,
            ).run(print_results=True)
        except Exception as exc:
            rel_err = f"reliability: {type(exc).__name__}: {exc}"
        else:
            if rel is None:
                rel_err = "reliability: returned no result"
            else:
                rel_passed = rel.eval_status == "PASSED"

    return CaseOutcome(
        name=case.name,
        judge_passed=judge_passed,
        reliability_passed=rel_passed,
        error="; ".join(e for e in (judge_err, rel_err) if e) or None,
    )


def run_case(case: Case, *, verbose: bool) -> CaseOutcome:
    return asyncio.run(_run_case_async(case, verbose=verbose))


def _check_cell(passed: bool | None) -> str:
    if passed is None:
        return "[dim]—[/dim]"
    style = "green" if passed else "red"
    tag = "PASS" if passed else "FAIL"
    return f"[{style}]{tag}[/{style}]"


def _print_agent_run(case: Case, response: object, output_str: str) -> None:
    """Print the full agent response + tool calls. Verbose-mode default."""
    console.print(f"[bold]Input[/bold]\n{case.input}")
    console.print(f"\n[bold]Response[/bold]\n{output_str or '[dim](empty)[/dim]'}")

    tools = getattr(response, "tools", None) or []
    if tools:
        console.print("\n[bold]Tool calls[/bold]")
        for t in tools:
            args_repr = repr(t.tool_args) if t.tool_args else ""
            line = f"  • {t.tool_name}({args_repr})" if args_repr else f"  • {t.tool_name}()"
            console.print(line)
    else:
        console.print("\n[bold]Tool calls[/bold]  [dim](none)[/dim]")
    console.print()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    case: str = typer.Option(None, "--case", help="Run only this case by name"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Hide the per-case agent response and tool-call list"),
) -> None:
    """Run the eval suite, or one case with --case <name>."""
    if ctx.invoked_subcommand is not None:
        return

    cases = list(CASES)
    if case:
        cases = [c for c in cases if c.name == case]
        if not cases:
            console.print(f"[red]no case named[/red] {case!r}")
            console.print(f"  [dim]available:[/dim] {', '.join(c.name for c in CASES)}")
            raise typer.Exit(2)

    outcomes: list[CaseOutcome] = []
    for i, c in enumerate(cases, 1):
        console.rule(f"[bold]{c.name}[/bold]  [dim]{c.agent.id} · {i}/{len(cases)}[/dim]")
        outcomes.append(run_case(c, verbose=not quiet))

    table = Table(title="Eval Summary", title_style="bold sky_blue1", show_header=True, header_style="bold")
    table.add_column("Case", overflow="fold")
    table.add_column("Judge")
    table.add_column("Reliability")
    table.add_column("Status")
    for o in outcomes:
        status = "[green]PASS[/green]" if o.passed else "[red]FAIL[/red]"
        table.add_row(o.name, _check_cell(o.judge_passed), _check_cell(o.reliability_passed), status)

    console.print()
    console.print(table)

    passed = sum(1 for o in outcomes if o.passed)
    failed = len(outcomes) - passed
    summary = f"[green]{passed}/{len(outcomes)} passed[/green]"
    if failed:
        summary += f", [red]{failed} failed[/red]"
    console.print(f"\n{summary}")

    for o in outcomes:
        if o.error:
            console.print(f"  [dim]{o.name}:[/dim] [red]{o.error}[/red]")

    raise typer.Exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    app()
