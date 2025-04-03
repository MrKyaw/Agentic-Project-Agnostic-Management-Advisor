"""Command-line interface for the project advisor."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from project_advisor import __version__
from project_advisor.demo import demo_project
from project_advisor.exceptions import InputError, ValidationError
from project_advisor.plan import build_plan, plan_to_dict
from project_advisor.report import render_markdown
from project_advisor.validation import load_project


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="project_advisor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Validate a project, compute the critical path, allocate sprints, "
            "score risks, and forecast completion -- entirely offline."
        ),
        epilog=(
            "Example: python -m project_advisor --demo\n"
            "         python -m project_advisor plan.json --json --sprints 8 --seed 7"
        ),
    )
    parser.add_argument("project", nargs="?", help="path to a JSON project document")
    parser.add_argument("--demo", action="store_true", help="run the built-in Atlas demo project")
    parser.add_argument("--json", action="store_true", dest="json_output", help="emit stable JSON instead of Markdown")
    parser.add_argument("--sprints", type=int, default=None, metavar="N", help="capacity planning horizon")
    parser.add_argument("--seed", type=int, default=42, help="Monte Carlo seed (default: 42)")
    parser.add_argument(
        "--simulations",
        type=int,
        default=1000,
        metavar="N",
        help="Monte Carlo sample count (default: 1000)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface.

    Args:
        argv: Arguments excluding the program name; defaults to ``sys.argv[1:]``.

    Returns:
        Process exit code: 0 on success, 2 for input or validation failures.
    """
    parser = _parser()
    args = parser.parse_args(argv)
    if args.demo and args.project is not None:
        parser.error("provide either PROJECT or --demo, not both")
    if not args.demo and args.project is None:
        parser.error("provide a PROJECT path or use --demo")
    try:
        project = demo_project() if args.demo else load_project(args.project)
        plan = build_plan(
            project,
            simulations=args.simulations,
            seed=args.seed,
            max_sprints=args.sprints,
        )
    except (InputError, ValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: cannot read project: {exc}", file=sys.stderr)
        return 2
    if args.json_output:
        print(json.dumps(plan_to_dict(plan), indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(render_markdown(plan))
    return 0
