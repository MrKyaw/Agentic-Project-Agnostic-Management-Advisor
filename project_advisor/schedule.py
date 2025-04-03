"""Dependency ordering and Critical Path Method (CPM) analysis."""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Mapping, Sequence

from project_advisor.exceptions import ValidationError
from project_advisor.models import Issue, Task

_EPSILON = 1e-9


@dataclass(frozen=True, slots=True)
class TaskTiming:
    """CPM timing values for one task, in person-days from project start.

    Args:
        task_id: Task identifier.
        earliest_start: Earliest possible start.
        earliest_finish: Earliest possible finish.
        latest_start: Latest start that does not delay the project.
        latest_finish: Latest finish that does not delay the project.
        slack: ``latest_start - earliest_start``; zero on the critical path.
        critical: Whether the task has (near) zero slack.
    """

    task_id: str
    earliest_start: float
    earliest_finish: float
    latest_start: float
    latest_finish: float
    slack: float
    critical: bool


@dataclass(frozen=True, slots=True)
class SchedulePlan:
    """Result of topological ordering plus CPM.

    Args:
        order: Deterministic topological order.
        timings: CPM timings in topological order.
        duration: Expected project duration in person-days.
        critical_path: One deterministic longest path through the network.
    """

    order: tuple[str, ...]
    timings: tuple[TaskTiming, ...]
    duration: float
    critical_path: tuple[str, ...]

    @property
    def critical_tasks(self) -> tuple[str, ...]:
        """Return every task with zero float, in topological order."""
        return tuple(timing.task_id for timing in self.timings if timing.critical)


def _build_index(tasks: Sequence[Task]) -> dict[str, Task]:
    index: dict[str, Task] = {}
    issues: list[Issue] = []
    for task in tasks:
        if task.id in index:
            issues.append(Issue("duplicate_task_id", f"Duplicate task id {task.id!r}.", task.id))
        else:
            index[task.id] = task
    if issues:
        raise ValidationError(issues)
    return index


def _successors(tasks: Sequence[Task], index: Mapping[str, Task]) -> dict[str, list[str]]:
    successors: dict[str, list[str]] = {task.id: [] for task in tasks}
    for task in tasks:
        for dependency in sorted(set(task.dependencies)):
            successors[dependency].append(task.id)
    for children in successors.values():
        children.sort()
    return successors


def _unknown_dependency_issues(tasks: Sequence[Task], index: Mapping[str, Task]) -> list[Issue]:
    issues: list[Issue] = []
    for task in tasks:
        for dependency in sorted(set(task.dependencies)):
            if dependency not in index:
                issues.append(
                    Issue(
                        "unknown_dependency",
                        f"Task {task.id!r} depends on unknown task {dependency!r}.",
                        task.id,
                    )
                )
    return issues


def topological_sort(tasks: Sequence[Task]) -> tuple[str, ...]:
    """Return a deterministic Kahn topological order.

    Ties are broken by task ID, so identical inputs always produce identical
    plans. Duplicate IDs, unknown dependencies, and cycles raise
    :class:`~project_advisor.exceptions.ValidationError`.

    Args:
        tasks: Tasks to order.

    Returns:
        Task IDs in dependency-safe order.

    Raises:
        ValidationError: If the graph is not a valid DAG.
    """
    index = _build_index(tasks)
    issues = _unknown_dependency_issues(tasks, index)
    if issues:
        raise ValidationError(issues)
    successors = _successors(tasks, index)
    indegree = {task.id: len(set(task.dependencies)) for task in tasks}
    ready = [task_id for task_id, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    order: list[str] = []
    while ready:
        current = heapq.heappop(ready)
        order.append(current)
        for child in successors[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                heapq.heappush(ready, child)
    if len(order) != len(index):
        remaining = sorted(task_id for task_id, degree in indegree.items() if degree > 0)
        raise ValidationError(
            [Issue("cycle", f"Cycle detected among tasks: {', '.join(remaining)}.", remaining[0])]
        )
    return tuple(order)


def dependency_successors(tasks: Sequence[Task]) -> dict[str, list[str]]:
    """Return a sorted adjacency map for a valid task graph.

    Args:
        tasks: Tasks in any order.

    Returns:
        Mapping of task ID to the IDs that depend on it.
    """
    return _successors(tasks, _build_index(tasks))


def critical_path(tasks: Sequence[Task]) -> SchedulePlan:
    """Run the Critical Path Method using PERT expected task effort.

    The method performs a forward pass for earliest start/finish and a
    backward pass for latest start/finish, then reports slack. The returned
    critical path is one deterministic longest path (ties broken by ID).

    Args:
        tasks: Tasks forming a DAG.

    Returns:
        A :class:`SchedulePlan` with timings and expected duration.

    Raises:
        ValidationError: If the graph is invalid.
    """
    order = topological_sort(tasks)
    if not order:
        return SchedulePlan(order=(), timings=(), duration=0.0, critical_path=())
    index = dict(_build_index(tasks))
    successors = _successors(tasks, index)

    earliest_start: dict[str, float] = {}
    earliest_finish: dict[str, float] = {}
    for task_id in order:
        task = index[task_id]
        start = max((earliest_finish[dependency] for dependency in task.dependencies), default=0.0)
        earliest_start[task_id] = start
        earliest_finish[task_id] = start + task.estimate.expected

    total = max(earliest_finish.values())
    latest_start: dict[str, float] = {}
    latest_finish: dict[str, float] = {}
    for task_id in reversed(order):
        children = successors[task_id]
        finish = min((latest_start[child] for child in children), default=total)
        latest_finish[task_id] = finish
        latest_start[task_id] = finish - index[task_id].estimate.expected

    timings = tuple(
        TaskTiming(
            task_id=task_id,
            earliest_start=earliest_start[task_id],
            earliest_finish=earliest_finish[task_id],
            latest_start=latest_start[task_id],
            latest_finish=latest_finish[task_id],
            slack=latest_start[task_id] - earliest_start[task_id],
            critical=abs(latest_start[task_id] - earliest_start[task_id]) <= _EPSILON,
        )
        for task_id in order
    )
    critical_ids = {timing.task_id for timing in timings if timing.critical}
    end = max(critical_ids, key=lambda task_id: (earliest_finish[task_id], task_id))
    path = [end]
    current = end
    while True:
        predecessors = [
            dependency
            for dependency in index[current].dependencies
            if dependency in critical_ids and abs(earliest_finish[dependency] - earliest_start[current]) <= _EPSILON
        ]
        if not predecessors:
            break
        current = min(predecessors)
        path.append(current)
    path.reverse()
    return SchedulePlan(
        order=order,
        timings=timings,
        duration=earliest_finish[end],
        critical_path=tuple(path),
    )
