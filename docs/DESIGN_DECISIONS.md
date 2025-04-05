# Design decisions

This document records the main trade-offs behind the deterministic advisor.
Each entry is an Architecture Decision Record in miniature: context, decision,
and consequences.

## ADR-001 — Ship a deterministic engine beside the agentic prototype

**Context.** The repository's original value is its CrewAI crews and FastAPI
prototype. Those paths depend on Ollama, Trello, Postgres, and credentials, which
makes them hard to evaluate quickly and impossible to test offline.

**Decision.** Keep every original artefact and add `project_advisor/` as a
dependency-free decision engine. The engine implements planning algorithms
directly; the prototype remains the research layer.

**Consequences.**

- Reviewers can run the core value proposition with a stock Python interpreter.
- CI can enforce 100% coverage without mocks or services.
- There are two layers to explain, but the boundary is explicit: the engine
  imports nothing from `src/`.

## ADR-002 — Standard library only

**Context.** A portfolio project that needs a 300 MB environment is hard to
verify. Pandas/NumPy would make Monte Carlo shorter but add heavy dependencies.

**Decision.** Implement parsing, statistics, scheduling, and reporting with the
standard library. `pyproject.toml` declares `dependencies = []`.

**Consequences.**

- Install-free CLI and tests; fast CI.
- No vectorised simulation or dataframe export; acceptable at project-plan scale.
- Custom code must be tested, which is why coverage is exhaustive.

## ADR-003 — Frozen dataclasses and aggregate validation

**Context.** Mutable models invite partial updates and make deterministic output
harder to reason about.

**Decision.** Core models are frozen, slotted dataclasses. Parsing checks JSON
shape; `validate_project` checks planning invariants and returns **all** issues
rather than raising on the first.

**Consequences.**

- Plans are value objects and safe to share.
- Users see every problem in one pass, with stable issue codes.
- Invalid graphs suppress duplicate cascades: duplicate task IDs skip graph
  checks.

## ADR-004 — Deterministic tie-breaking everywhere

**Context.** Sets and dict iteration can vary across runs; random forecasts can
be irreproducible.

**Decision.** Use explicit sort keys:

- tasks: `(priority, id)`;
- topological ready queue: ID heap;
- member choice: owner preference, then remaining capacity, then ID;
- risks: score descending, then ID;
- Monte Carlo: one local `random.Random(seed)`.

**Consequences.** Identical input produces identical output, which enables JSON
diffing and stable snapshot tests. The cost is a small amount of deliberate
arbitrariness when two options are equally good.

## ADR-005 — CPM and capacity allocation are separate views

**Context.** CPM assumes unlimited resources. Sprint allocation is constrained by
people and skills. Merging them produces a model that is hard to explain.

**Decision.** `critical_path` answers "how long is the dependency chain under
PERT effort?" and `schedule_sprints` answers "who does what, when?". The report
presents both.

**Consequences.**

- Clear diagnostics: float is a graph property; overload/spillover is a capacity
  property.
- The capacity timeline can be longer than the CPM duration; that is a feature,
  not a contradiction.
- Both views share the same validated task graph.

## ADR-006 — One owner per task, tasks may span sprints

**Context.** The demo contains a 13.5-day task and a 9-day team capacity. Requiring
a task to fit a single sprint makes realistic projects unschedulable. Splitting a
task across owners destroys accountability.

**Decision.** A task receives exactly one owner and consumes that owner's capacity
across as many sprints as needed.

**Consequences.**

- Realistic allocation with clear accountability.
- No parallel execution within a task, so estimates are conservative.
- Completion is tracked at sprint granularity.

## ADR-007 — Greedy scheduler, not an optimiser

**Context.** An ILP/CP-SAT scheduler would find better plans but adds dependencies
and obscures the algorithm in a portfolio repository.

**Decision.** Use an explainable greedy scheduler with priority ordering and
explicit signals: blocked tasks, overloaded sprints, skill gaps, spillover, and
unscheduled work.

**Consequences.**

- Every assignment can be justified in one sentence.
- Plans may be worse than optimal; the limitation is documented in the README.
- The `CapacityPlan` shape is stable enough to swap in an optimiser later.

## ADR-008 — PERT plus triangular Monte Carlo

**Context.** Three-point estimates support both a closed-form PERT result and a
sampling forecast.

**Decision.** Compute PERT expected duration and critical-path variance, and run
seeded Monte Carlo with triangular draws for empirical percentiles and deadline
probability.

**Consequences.**

- Fast closed-form sanity check plus an uncertainty distribution.
- The two means differ slightly because triangular and PERT weights differ; this
  is documented rather than hidden.
- Task independence is assumed; correlated risks need a custom model.

## ADR-009 — Stable JSON as a contract

**Context.** Reports that change key order or float precision create noisy diffs
and brittle integrations.

**Decision.** `plan_to_dict` builds an explicit dictionary in domain order and
rounds values to six decimals. The CLI serialises with `sort_keys=True`.

**Consequences.** Plans can be committed or diffed. Consumers get a stable shape,
but must tolerate additive fields in future minor versions.

## ADR-010 — Validation and CLI errors are data, not tracebacks

**Context.** Reviewers and users will try malformed files.

**Decision.** Distinguish `InputError` (shape/parameter) from `ValidationError`
(planning invariant). Both produce `error: ...` on stderr and exit code `2`.
Argparse errors also exit `2`.

**Consequences.** Predictable automation behaviour. Internal bugs still raise
tracebacks, which is desirable.

## ADR-011 — Dates skip weekends only

**Context.** A holiday-aware calendar requires a jurisdiction and maintenance.

**Decision.** Working-day helpers skip Saturday/Sunday. Capacity is expressed in
person-days, so non-working days do not consume capacity.

**Consequences.** Simple, predictable forecasts. Users in holiday-heavy periods
should adjust the deadline or capacity manually; the limitation is explicit.

## ADR-012 — 100% line and branch coverage with no exclusions

**Context.** A small engine can afford exhaustive tests; coverage theatre with
pragmas undermines the signal.

**Decision.** Enforce `fail_under = 100` for both statements and branches. Test
the module entry point and every CLI error path. Allow no `# pragma: no cover`.

**Consequences.**

- The suite doubles as executable specification.
- Some tests are defensive (for example unreachable-looking scheduler states),
  but the branch they pin documents real policy.
- Any new branch requires a new test, which keeps design pressure honest.
