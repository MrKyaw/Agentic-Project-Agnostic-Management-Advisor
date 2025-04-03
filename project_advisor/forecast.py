"""PERT estimation and deterministic Monte Carlo completion forecasting."""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Mapping, Sequence

from project_advisor.exceptions import InputError
from project_advisor.models import Project, Task
from project_advisor.schedule import critical_path, topological_sort
from project_advisor.validation import validate_project

PERCENTILES: tuple[int, ...] = (50, 80, 90, 95)


@dataclass(frozen=True, slots=True)
class PertEstimate:
    """Program Evaluation and Review Technique summary.

    Args:
        expected_duration: Longest path using PERT expected effort.
        variance: Sum of critical-path task variances (independence assumed).
        standard_deviation: Square root of ``variance``.
        optimistic_duration: Longest path using optimistic effort.
        pessimistic_duration: Longest path using pessimistic effort.
        critical_path: Tasks driving the expected duration.
    """

    expected_duration: float
    variance: float
    standard_deviation: float
    optimistic_duration: float
    pessimistic_duration: float
    critical_path: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ForecastResult:
    """Monte Carlo completion forecast.

    Args:
        simulations: Number of sampled schedules.
        seed: Seed used for reproducibility.
        mean: Mean sampled project duration in person-days.
        standard_deviation: Population standard deviation of sampled durations.
        percentiles: Completion-duration percentiles keyed by percentage.
        on_time_probability: Probability of meeting the project deadline, or
            ``None`` when no deadline is supplied.
    """

    simulations: int
    seed: int
    mean: float
    standard_deviation: float
    percentiles: Mapping[int, float]
    on_time_probability: float | None


def _longest_duration(tasks: Sequence[Task], durations: Mapping[str, float]) -> float:
    order = topological_sort(tasks)
    finish: dict[str, float] = {}
    for task_id in order:
        task = next(item for item in tasks if item.id == task_id)
        start = max((finish[dependency] for dependency in task.dependencies), default=0.0)
        finish[task_id] = start + durations[task_id]
    return max(finish.values(), default=0.0)


def add_working_days(start: date, days: float) -> date:
    """Add whole working days (Monday-Friday) to a calendar date.

    Args:
        start: Starting date.
        days: Duration in working days; fractional days round up.

    Returns:
        The resulting date. Non-positive durations return ``start``.
    """
    if days <= 0:
        return start
    remaining = math.ceil(days)
    current = start
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def finish_date(start: date, duration_days: float) -> date:
    """Return the working-day finish date for a duration starting on ``start``.

    ``start`` counts as the first working day: a one-day task finishes on the
    start date, and a five-day task starting Monday finishes on Friday.

    Args:
        start: Starting date.
        duration_days: Duration in working days; fractional days round up.

    Returns:
        The inclusive finish date.
    """
    if duration_days <= 0:
        return start
    return add_working_days(start, math.ceil(duration_days) - 1)


def working_days_available(start: date, deadline: date) -> int:
    """Count weekdays from ``start`` through ``deadline``, inclusive.

    Args:
        start: Project start date.
        deadline: Target date.

    Returns:
        Number of available weekdays, or zero if the deadline precedes the
        start date.
    """
    if deadline < start:
        return 0
    total = 0
    current = start
    while current <= deadline:
        if current.weekday() < 5:
            total += 1
        current += timedelta(days=1)
    return total


def pert_estimate(project: Project) -> PertEstimate:
    """Compute a PERT estimate over the project's critical path.

    Args:
        project: Valid project description.

    Returns:
        A :class:`PertEstimate` in person-days.

    Raises:
        ValidationError: If the project is invalid.
    """
    validate_project(project).raise_for_errors()
    schedule = critical_path(project.tasks)
    index = {task.id: task for task in project.tasks}
    variance = sum(index[task_id].estimate.variance for task_id in schedule.critical_path)
    return PertEstimate(
        expected_duration=schedule.duration,
        variance=variance,
        standard_deviation=math.sqrt(variance),
        optimistic_duration=_longest_duration(
            project.tasks, {task.id: task.estimate.optimistic for task in project.tasks}
        ),
        pessimistic_duration=_longest_duration(
            project.tasks, {task.id: task.estimate.pessimistic for task in project.tasks}
        ),
        critical_path=schedule.critical_path,
    )


def _percentile(values: Sequence[float], percentage: int) -> float:
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, math.ceil(percentage / 100.0 * len(ordered)) - 1))
    return ordered[rank]


def monte_carlo_forecast(
    project: Project,
    simulations: int = 1000,
    seed: int = 42,
) -> ForecastResult:
    """Sample task durations and report a distribution of completion times.

    Each task duration is drawn independently from a triangular distribution
    ``(optimistic, pessimistic, most_likely)``. The project duration for each
    sample is the longest path through the dependency network, preserving the
    effect of parallelism. A fixed seed makes results byte-for-byte stable.

    Args:
        project: Valid project description.
        simulations: Number of sampled schedules; must be at least one.
        seed: Random seed for reproducibility.

    Returns:
        A :class:`ForecastResult` with percentiles and deadline probability.

    Raises:
        ValidationError: If the project is invalid.
        InputError: If ``simulations`` is less than one.
    """
    validate_project(project).raise_for_errors()
    if simulations < 1:
        raise InputError("simulations must be at least 1")
    order = topological_sort(project.tasks)
    index = {task.id: task for task in project.tasks}
    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(simulations):
        durations = {
            task_id: rng.triangular(
                index[task_id].estimate.optimistic,
                index[task_id].estimate.pessimistic,
                index[task_id].estimate.most_likely,
            )
            for task_id in order
        }
        finish: dict[str, float] = {}
        for task_id in order:
            start = max(
                (finish[dependency] for dependency in index[task_id].dependencies),
                default=0.0,
            )
            finish[task_id] = start + durations[task_id]
        samples.append(max(finish.values(), default=0.0))
    on_time: float | None = None
    if project.deadline is not None:
        available = working_days_available(project.start_date, project.deadline)
        on_time = sum(sample <= available for sample in samples) / simulations
    return ForecastResult(
        simulations=simulations,
        seed=seed,
        mean=statistics.fmean(samples),
        standard_deviation=statistics.pstdev(samples),
        percentiles={percentage: _percentile(samples, percentage) for percentage in PERCENTILES},
        on_time_probability=on_time,
    )


__all__ = [
    "ForecastResult",
    "PertEstimate",
    "add_working_days",
    "finish_date",
    "monte_carlo_forecast",
    "pert_estimate",
    "working_days_available",
]
