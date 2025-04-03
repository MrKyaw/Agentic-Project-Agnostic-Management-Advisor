# Testing

## Philosophy

The deterministic engine is small enough to test exhaustively, so it is. The
suite prioritises:

- **Domain correctness** — hand-checked CPM numbers, float, PERT variance,
  capacity spillover, risk bucket boundaries.
- **Failure behaviour** — malformed JSON, invalid projects, cycles, missing
  files, and CLI exit codes are first-class tests, not afterthoughts.
- **Determinism** — seeded forecasts must compare equal; JSON must be stable.
- **No network** — no test opens a socket, starts a service, or reads a secret.

## Commands

```bash
# Fast feedback
python3 -m pytest -q

# Full coverage gate (100% line + branch for project_advisor)
python3 -m pytest --cov=project_advisor --cov-branch --cov-report=term-missing

# HTML coverage (open htmlcov/index.html)
python3 -m pytest --cov=project_advisor --cov-branch --cov-report=html

# CLI smoke tests
python3 -m project_advisor --help
python3 -m project_advisor --demo
python3 -m project_advisor --demo --json > /tmp/plan.json
```

`make test`, `make coverage`, and `make demo` wrap the same commands.

## Measured results

Environment: Python 3.12.8, macOS, 2026-10-22, offline.

```console
$ python3 -m pytest -q
142 passed in 0.33s

$ python3 -m pytest --cov=project_advisor --cov-branch --cov-report=term-missing
TOTAL  743 statements  0 missed  192 branches  0 partial  100.00%
142 passed in 0.68s
```

Per-module coverage is published in the README. The gate is configured in
`pyproject.toml`:

```toml
[tool.coverage.run]
source = ["project_advisor"]
branch = true

[tool.coverage.report]
fail_under = 100
```

There are no `# pragma: no cover` directives and no coverage omissions in the
runtime package. `project_advisor/__main__.py` is covered by importing it with a
patched `sys.argv` and asserting the resulting `SystemExit`.

## Test map

| Area | Representative tests |
| --- | --- |
| Dataclasses and properties | `test_estimate_properties`, `test_issue_defaults_and_exception_messages` |
| JSON deserialisation | `test_project_document_round_trip`, `test_project_document_shape_errors`, `test_task_shape_errors`, `test_member_shape_errors`, `test_risk_shape_errors` |
| Validation | `test_validation_collects_domain_issues`, `test_validation_estimate_order_and_finite`, `test_validation_unknown_dependency`, `test_validation_cycle`, `test_validation_duplicate_tasks_skip_graph_checks` |
| Topological sort | empty, single, parallel, duplicate-dependency, duplicate-ID, unknown-dependency, cycle tests |
| CPM | `test_critical_path_empty`, `test_critical_path_single_task`, `test_critical_path_parallel_paths_and_slack`, `test_critical_path_disconnected_nodes` |
| Capacity | spans sprints, dependency wait, overload, spillover, owner preference/fallback, skill gaps, zero effort, horizon limits |
| Risk | bucket boundaries, empty register, top-five truncation, tie ordering, explicit vs suggested mitigation |
| PERT / dates | `test_pert_estimate_parallel_paths`, `test_add_working_days`, `test_finish_date`, `test_working_days_available` |
| Monte Carlo | same-seed equality, different-seed divergence, deadline probability 0/1, empty project, zero variance, invalid sample count |
| Plan and JSON | `test_build_plan_and_plan_to_dict`, `test_plan_to_dict_without_deadline` |
| Markdown | full demo, empty project, skill gaps, escaped table cells, owner fallbacks |
| CLI | help, version, demo, JSON, file input, default `sys.argv`, missing file, invalid JSON, validation error, bad sprint/simulation counts, `__main__` |
| Loading | round trip, invalid JSON, missing file `OSError` |

## Determinism checks

- `test_monte_carlo_is_deterministic` asserts two runs with seed 7 are identical
  and a seed-8 run differs at P80.
- `test_topological_sort_parallel_deterministic` asserts ID-based tie-breaking.
- `test_schedule_tie_breaks_by_member_id` asserts member ID tie-breaking.
- `test_critical_path_multiple_predecessors_and_zero_duration` pins the
  zero-duration path choice.
- `test_cli_json` parses the CLI output and checks the seed/horizon survive.

Tests never assert wall-clock time or locale formatting, so they are stable on CI.

## Coverage policy

The package must remain at **100% line and branch coverage**. When adding code:

1. Add the smallest scenario that reaches each new branch, including failure
   paths.
2. Prefer public API tests; import private helpers only when they encode a
   distinct policy (for example `dependency_successors`).
3. Do not lower `fail_under`, add pragmas, or exclude modules.
4. Run the coverage command locally before opening a pull request.

## CI

`.github/workflows/ci.yml` runs on every push and pull request:

- Python 3.10, 3.11, and 3.12 matrix
- editable install with `.[dev]`
- `python -m pytest -q`
- `python -m pytest --cov=project_advisor --cov-branch --cov-report=term-missing`
- CLI smoke test (`--demo`)

The coverage gate is enforced by `pyproject.toml`, so a coverage regression fails
the job on every matrix entry.

## What is intentionally not tested

The optional prototype paths in `src/` are not exercised: CrewAI crews, Ollama
calls, Trello APIs, FastAPI/Postgres endpoints, and notebooks require external
services and credentials. They are preserved as research artefacts, not part of
the deterministic engine's contract.
