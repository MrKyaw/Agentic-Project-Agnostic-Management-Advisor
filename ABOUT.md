# About APAMA

**Agentic Project Agnostic Management Advisor** — a deterministic,
dependency-free project-management decision engine, with the original CrewAI
research prototype preserved alongside it.

## One-line summary

Turns a JSON work breakdown into a validated plan with critical-path analysis,
capacity-constrained sprint allocation, risk scoring, PERT and seeded Monte Carlo
forecasts, and executive Markdown/JSON output.

## Topics and keywords

`project-management` · `technical-program-management` · `project-planning` ·
`work-breakdown-structure` · `critical-path-method` · `cpm` · `pert` ·
`monte-carlo` · `forecast` · `capacity-planning` · `sprint-planning` ·
`resource-allocation` · `risk-register` · `risk-analysis` · `decision-engine` ·
`python` · `standard-library` · `dataclasses` · `cli` · `deterministic` ·
`test-coverage` · `pytest` · `crewai` · `agentic-ai` · `fastapi` · `portfolio`

## What is in the repository

- `project_advisor/` — the new, offline, stdlib-only planning engine and CLI.
- `tests/` — 142 tests with 100% line and branch coverage of the new package.
- `src/` — the original agentic prototype: CrewAI planning/estimation/
  resource-allocation crews, Trello analysis notebooks, FastAPI + Postgres app,
  and inventory/sales forecasting experiments.
- `data/`, `research/` — original supporting artefacts.

## Audience

Reviewers and hiring managers evaluating project/programme management,
technical program management, platform engineering, or applied-AI engineering
work; engineers who want a small, auditable planning library; and anyone tired
of unverifiable AI-generated project plans.

## Technical shape

- Python 3.10+ runtime
- Zero third-party runtime dependencies
- Dataclasses, type hints, docstrings, custom exceptions
- Deterministic ID-based tie-breaking and seeded simulation
- MIT license

## Author

Kyaw Kyaw Oo — kyaw.tech@gmail.com — github.com/MrKyaw

## License

MIT. See [license.txt](license.txt).
