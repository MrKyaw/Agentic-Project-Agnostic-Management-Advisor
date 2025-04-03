# Contributing

Thanks for taking a look. This repository is a portfolio project, but it is run
like production code: small, typed, deterministic, and fully tested.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Runtime code uses only the Python standard library. `pytest` and `pytest-cov` are
development-only dependencies.

## Before opening a pull request

```bash
python3 -m pytest -q
python3 -m pytest --cov=project_advisor --cov-branch --cov-report=term-missing
python3 -m project_advisor --demo > /dev/null
python3 -m project_advisor --help > /dev/null
```

All commands must pass. The coverage gate requires **100% line and branch
coverage** of `project_advisor`; do not lower `fail_under` or add
`# pragma: no cover`.

## Engineering conventions

- **Python 3.10+.** Use `from __future__ import annotations`, built-in generics,
  and `X | None`.
- **Dataclasses for domain values.** Keep them frozen and slotted unless there is
  a measured reason not to.
- **Type hints on public functions.** Document arguments, returns, and raised
  exceptions in docstrings.
- **Determinism.** Sort by explicit keys (ID last), use a local seeded RNG, and
  never depend on wall-clock time or set iteration order.
- **No new runtime dependencies.** If a dependency feels necessary, open an issue
  explaining the trade-off first.
- **No network in tests.** Use fixtures, `tmp_path`, `capsys`, and `monkeypatch`.
- **Preserve the prototype.** Do not delete or refactor `src/`, notebooks, data,
  or CrewAI configs as part of engine work.

## Adding a feature

1. Extend the domain model only if the concept is genuinely new.
2. Add validation for new invariants and a stable issue code.
3. Implement the algorithm as a pure function returning a frozen result object.
4. Wire it into `build_plan` and `plan_to_dict` only if it belongs in the plan.
5. Add tests that cover success paths, failure paths, and branch boundaries.
6. Update the README capability table and `ARCHITECTURE.md` if the data flow
   changes.

## Commit and review style

- Keep commits focused; one logical change per commit.
- Explain **why** in the message, not just what changed.
- Include the test/coverage commands you ran in the pull request description.
- Flag any change that intentionally alters JSON output shape.

## Reporting a bug

Include:

- the smallest JSON project that reproduces the issue (redact sensitive data);
- the command you ran;
- the expected and actual result;
- Python version and OS.

## Security

The deterministic engine performs no network, filesystem discovery, or code
execution beyond reading the JSON path supplied on the command line. Do not add
features that execute project-supplied code. Report security concerns privately
to kyaw.tech@gmail.com.

## License

By contributing, you agree that your contribution is licensed under the MIT
license in [license.txt](license.txt).
