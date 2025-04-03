"""Capacity-constrained, priority-driven sprint allocation."""

from __future__ import annotations

import math
from dataclasses import dataclass

from project_advisor.exceptions import InputError
from project_advisor.models import Project, Task, TeamMember
from project_advisor.validation import validate_project


@dataclass(frozen=True, slots=True)
class Assignment:
    """One task scheduled into one sprint for one team member.

    Args:
        sprint: One-based sprint number.
        task_id: Scheduled task.
        member_id: Accountable team member.
        effort: Person-days consumed in that sprint.
    """

    sprint: int
    task_id: str
    member_id: str
    effort: float


@dataclass(frozen=True, slots=True)
class SkillGap:
    """A task that no single team member can own because skills are missing.

    Args:
        task_id: Blocked task.
        missing_skills: Skills absent from the entire team.
    """

    task_id: str
    missing_skills: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SprintPlan:
    """Capacity consumption for one sprint.

    Args:
        number: One-based sprint number.
        assignments: Work placed in the sprint.
        blocked_task_ids: Ready tasks that could not be placed.
        capacity_used: Person-days assigned.
        capacity_total: Person-days available.
    """

    number: int
    assignments: tuple[Assignment, ...]
    blocked_task_ids: tuple[str, ...]
    capacity_used: float
    capacity_total: float


@dataclass(frozen=True, slots=True)
class MemberLoad:
    """Utilisation summary for one team member.

    Args:
        member_id: Team member identifier.
        assigned: Total person-days assigned.
        capacity: Total person-days available across scheduled sprints.
        utilization: ``assigned / capacity`` in the range 0-1, or 0 when no
            sprint was scheduled.
    """

    member_id: str
    assigned: float
    capacity: float
    utilization: float


@dataclass(frozen=True, slots=True)
class CapacityPlan:
    """Outcome of greedy sprint allocation.

    Args:
        sprints: Non-empty sprint plans in order.
        assignments: Flattened assignments in sprint order.
        unscheduled: Tasks that never fit before the horizon.
        skill_gaps: Tasks blocked by missing skills.
        overloaded_sprints: Sprints where ready work was blocked by capacity.
        spillover: Tasks that started later than their dependency earliest.
        member_loads: Per-member utilisation.
        feasible: Whether every task was assigned and no skill gap exists.
    """

    sprints: tuple[SprintPlan, ...]
    assignments: tuple[Assignment, ...]
    unscheduled: tuple[str, ...]
    skill_gaps: tuple[SkillGap, ...]
    overloaded_sprints: tuple[int, ...]
    spillover: tuple[str, ...]
    member_loads: tuple[MemberLoad, ...]
    feasible: bool


def _missing_skills(task: Task, team: tuple[TeamMember, ...]) -> tuple[str, ...]:
    return tuple(
        sorted(skill for skill in set(task.skills) if not any(skill in member.skills for member in team))
    )


def schedule_sprints(project: Project, max_sprints: int | None = None) -> CapacityPlan:
    """Allocate whole tasks to sprints under skill and capacity constraints.

    The scheduler is deliberately greedy and explainable: at each sprint it
    considers dependency-ready tasks ordered by ``(priority, id)``, prefers a
    task's named owner when that person has capacity, and otherwise picks the
    eligible member with the most remaining capacity. A task has exactly one
    owner and may span several sprints, but work is never split across people.
    Work that cannot fit is marked as blocked, overloaded, spilled over, or
    unscheduled rather than silently ignored.

    Args:
        project: Valid project description.
        max_sprints: Planning horizon. Defaults to a capacity-aware bound:
            enough sprints to cover total effort plus one per task.

    Returns:
        A deterministic :class:`CapacityPlan`.

    Raises:
        ValidationError: If the project is invalid.
        InputError: If ``max_sprints`` is less than one.
    """
    validate_project(project).raise_for_errors()
    total_capacity = sum(member.capacity for member in project.team)
    if max_sprints is None:
        effort = sum(task.estimate.expected for task in project.tasks)
        capacity_sprints = math.ceil(effort / total_capacity) if total_capacity > 0 else 0
        horizon = max(1, len(project.tasks), capacity_sprints + len(project.tasks))
    else:
        horizon = max_sprints
    if horizon < 1:
        raise InputError("max_sprints must be at least 1")

    members = {member.id: member for member in project.team}
    completed: set[str] = set()
    starts: dict[str, int] = {}
    finishes: dict[str, int] = {}
    remaining_effort = {task.id: task.estimate.expected for task in project.tasks}
    owners: dict[str, str] = {}
    gaps: dict[str, SkillGap] = {}
    overloaded: set[int] = set()
    sprint_plans: list[SprintPlan] = []
    assignments: list[Assignment] = []

    for sprint in range(1, horizon + 1):
        if len(completed) == len(project.tasks):
            break
        ready = [
            task
            for task in project.tasks
            if task.id not in completed and set(task.dependencies).issubset(completed)
        ]
        ready.sort(key=lambda task: (task.priority, task.id))
        remaining = {member.id: member.capacity for member in project.team}
        sprint_assignments: list[Assignment] = []
        blocked: list[str] = []
        demand = sum(remaining_effort[task.id] for task in ready)
        supply = sum(remaining.values())
        if demand > supply + 1e-9:
            overloaded.add(sprint)

        for task in ready:
            effort_left = remaining_effort[task.id]
            owner_id = owners.get(task.id)
            if owner_id is not None:
                available = remaining[owner_id]
                if available <= 1e-9:
                    blocked.append(task.id)
                    overloaded.add(sprint)
                    continue
                chosen = members[owner_id]
            else:
                required = set(task.skills)
                eligible = [member for member in project.team if required.issubset(member.skills)]
                if not eligible:
                    blocked.append(task.id)
                    gaps.setdefault(task.id, SkillGap(task.id, _missing_skills(task, project.team)))
                    continue
                available_members = [member for member in eligible if remaining[member.id] > 1e-9]
                if not available_members:
                    blocked.append(task.id)
                    overloaded.add(sprint)
                    continue
                preferred = members.get(task.owner) if task.owner is not None else None
                if preferred is not None and preferred in available_members:
                    chosen = preferred
                else:
                    chosen = min(available_members, key=lambda member: (-remaining[member.id], member.id))
                owners[task.id] = chosen.id
                starts[task.id] = sprint
            effort = min(effort_left, remaining[chosen.id])
            assignment = Assignment(sprint, task.id, chosen.id, effort)
            sprint_assignments.append(assignment)
            assignments.append(assignment)
            remaining[chosen.id] -= effort
            remaining_effort[task.id] -= effort
            if remaining_effort[task.id] <= 1e-9:
                completed.add(task.id)
                finishes[task.id] = sprint

        sprint_plans.append(
            SprintPlan(
                number=sprint,
                assignments=tuple(sprint_assignments),
                blocked_task_ids=tuple(blocked),
                capacity_used=sum(assignment.effort for assignment in sprint_assignments),
                capacity_total=sum(member.capacity for member in project.team),
            )
        )
        if not sprint_assignments:
            break

    unscheduled = tuple(task.id for task in project.tasks if task.id not in completed)
    spillover = tuple(
        task.id
        for task in project.tasks
        if task.id in starts
        and starts[task.id]
        > 1 + max((finishes[dependency] for dependency in task.dependencies), default=0)
    )
    horizon_used = len(sprint_plans)
    member_loads = tuple(
        MemberLoad(
            member_id=member.id,
            assigned=sum(
                assignment.effort for assignment in assignments if assignment.member_id == member.id
            ),
            capacity=member.capacity * horizon_used,
            utilization=(
                sum(assignment.effort for assignment in assignments if assignment.member_id == member.id)
                / (member.capacity * horizon_used)
                if horizon_used
                else 0.0
            ),
        )
        for member in project.team
    )
    return CapacityPlan(
        sprints=tuple(sprint_plans),
        assignments=tuple(assignments),
        unscheduled=unscheduled,
        skill_gaps=tuple(gaps[task_id] for task_id in sorted(gaps)),
        overloaded_sprints=tuple(sorted(overloaded)),
        spillover=spillover,
        member_loads=member_loads,
        feasible=not unscheduled and not gaps,
    )


__all__ = [
    "Assignment",
    "CapacityPlan",
    "MemberLoad",
    "SkillGap",
    "SprintPlan",
    "schedule_sprints",
]
