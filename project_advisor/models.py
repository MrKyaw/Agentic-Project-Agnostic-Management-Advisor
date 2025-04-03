"""Domain model and JSON deserialisation for project plans.

All durations and capacities are expressed in **person-days**. A task's
three-point estimate describes effort for one person; the critical path and
forecasts treat the most likely effort as the task duration once assigned.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from project_advisor.exceptions import InputError
from project_advisor.issues import Issue

__all__ = [
    "Estimate",
    "Issue",
    "Project",
    "Risk",
    "Task",
    "TeamMember",
    "project_from_dict",
    "risk_from_dict",
    "task_from_dict",
    "team_member_from_dict",
]


@dataclass(frozen=True, slots=True)
class Estimate:
    """Three-point effort estimate in person-days.

    Args:
        optimistic: Best-case effort.
        most_likely: Most probable effort.
        pessimistic: Worst-case effort.

    The ordering ``optimistic <= most_likely <= pessimistic`` and
    non-negativity are enforced by :func:`validate_project` rather than by
    the constructor so that malformed documents can be reported together.
    """

    optimistic: float
    most_likely: float
    pessimistic: float

    @property
    def expected(self) -> float:
        """Return the PERT expected effort ``(o + 4m + p) / 6``."""
        return (self.optimistic + 4.0 * self.most_likely + self.pessimistic) / 6.0

    @property
    def variance(self) -> float:
        """Return the PERT variance ``((p - o) / 6) ** 2``."""
        return ((self.pessimistic - self.optimistic) / 6.0) ** 2

    @property
    def standard_deviation(self) -> float:
        """Return the standard deviation implied by the three-point estimate."""
        return math.sqrt(self.variance)


@dataclass(frozen=True, slots=True)
class Task:
    """A work-breakdown-structure task.

    Args:
        id: Unique identifier used by dependencies and reports.
        name: Short deliverable-oriented name.
        estimate: Three-point effort estimate in person-days.
        dependencies: IDs that must finish before this task starts.
        skills: Every skill a team member must have to own the task.
        owner: Optional preferred team-member ID.
        priority: 1 (highest) through 5 (lowest); used by the scheduler.
        description: Optional acceptance-criteria or scope note.
    """

    id: str
    name: str
    estimate: Estimate
    dependencies: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    owner: str | None = None
    priority: int = 3
    description: str = ""


@dataclass(frozen=True, slots=True)
class TeamMember:
    """A person or role available to the project.

    Args:
        id: Unique identifier, referenced by task owners and assignments.
        name: Display name.
        skills: Skills the member can apply.
        capacity: Person-days available per sprint.
    """

    id: str
    name: str
    skills: tuple[str, ...] = ()
    capacity: float = 10.0


@dataclass(frozen=True, slots=True)
class Risk:
    """An entry in the project risk register.

    Args:
        id: Unique identifier.
        title: Concise risk statement.
        probability: Likelihood on a 1-5 scale.
        impact: Impact on a 1-5 scale.
        category: Used to select a default mitigation strategy.
        owner: Optional accountable person or role.
        mitigation: Optional explicit mitigation that overrides the default.
    """

    id: str
    title: str
    probability: int
    impact: int
    category: str = "technical"
    owner: str | None = None
    mitigation: str | None = None


@dataclass(frozen=True, slots=True)
class Project:
    """A complete, self-contained project description.

    Args:
        name: Project name.
        start_date: Calendar date on which delivery starts.
        tasks: Work-breakdown-structure tasks.
        team: Available team members. May be empty for planning-only use.
        risks: Risk register entries.
        deadline: Optional contractual or target deadline.
        sprint_days: Length of one sprint in calendar working days.
    """

    name: str
    start_date: date
    tasks: tuple[Task, ...] = ()
    team: tuple[TeamMember, ...] = ()
    risks: tuple[Risk, ...] = ()
    deadline: date | None = None
    sprint_days: int = 10
    metadata: Mapping[str, Any] = field(default_factory=dict)


def _mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InputError(f"{where} must be a JSON object")
    return value


def _sequence(value: Any, where: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise InputError(f"{where} must be a JSON array")
    return value


def _required(data: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in data:
        raise InputError(f"missing required field {key!r} in {where}")
    return data[key]


def _string(value: Any, where: str) -> str:
    if not isinstance(value, str):
        raise InputError(f"{where} must be a string")
    return value


def _optional_string(value: Any, where: str) -> str | None:
    if value is None:
        return None
    return _string(value, where)


def _number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{where} must be a number")
    return float(value)


def _integer(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InputError(f"{where} must be an integer")
    return value


def _date(value: Any, where: str) -> date:
    if not isinstance(value, str):
        raise InputError(f"{where} must be an ISO-8601 date string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InputError(f"{where} must be an ISO-8601 date string") from exc


def _string_tuple(value: Any, where: str) -> tuple[str, ...]:
    return tuple(_string(item, f"{where}[{index}]") for index, item in enumerate(_sequence(value, where)))


def task_from_dict(raw: Any, index: int) -> Task:
    """Build a :class:`Task` from one JSON object.

    Args:
        raw: Decoded JSON value.
        index: Position in the task array, used in error messages.

    Raises:
        InputError: If any field is missing or has the wrong type.
    """
    where = f"tasks[{index}]"
    data = _mapping(raw, where)
    estimate_data = _mapping(_required(data, "estimate", where), f"{where}.estimate")
    estimate = Estimate(
        optimistic=_number(_required(estimate_data, "optimistic", f"{where}.estimate"), f"{where}.estimate.optimistic"),
        most_likely=_number(_required(estimate_data, "most_likely", f"{where}.estimate"), f"{where}.estimate.most_likely"),
        pessimistic=_number(_required(estimate_data, "pessimistic", f"{where}.estimate"), f"{where}.estimate.pessimistic"),
    )
    return Task(
        id=_string(_required(data, "id", where), f"{where}.id"),
        name=_string(_required(data, "name", where), f"{where}.name"),
        estimate=estimate,
        dependencies=_string_tuple(data.get("dependencies", []), f"{where}.dependencies"),
        skills=_string_tuple(data.get("skills", []), f"{where}.skills"),
        owner=_optional_string(data.get("owner"), f"{where}.owner"),
        priority=_integer(data.get("priority", 3), f"{where}.priority"),
        description=_string(data.get("description", ""), f"{where}.description"),
    )


def team_member_from_dict(raw: Any, index: int) -> TeamMember:
    """Build a :class:`TeamMember` from one JSON object.

    Args:
        raw: Decoded JSON value.
        index: Position in the team array, used in error messages.

    Raises:
        InputError: If any field is missing or has the wrong type.
    """
    where = f"team[{index}]"
    data = _mapping(raw, where)
    return TeamMember(
        id=_string(_required(data, "id", where), f"{where}.id"),
        name=_string(_required(data, "name", where), f"{where}.name"),
        skills=_string_tuple(data.get("skills", []), f"{where}.skills"),
        capacity=_number(data.get("capacity", 10.0), f"{where}.capacity"),
    )


def risk_from_dict(raw: Any, index: int) -> Risk:
    """Build a :class:`Risk` from one JSON object.

    Args:
        raw: Decoded JSON value.
        index: Position in the risk array, used in error messages.

    Raises:
        InputError: If any field is missing or has the wrong type.
    """
    where = f"risks[{index}]"
    data = _mapping(raw, where)
    return Risk(
        id=_string(_required(data, "id", where), f"{where}.id"),
        title=_string(_required(data, "title", where), f"{where}.title"),
        probability=_integer(_required(data, "probability", where), f"{where}.probability"),
        impact=_integer(_required(data, "impact", where), f"{where}.impact"),
        category=_string(data.get("category", "technical"), f"{where}.category"),
        owner=_optional_string(data.get("owner"), f"{where}.owner"),
        mitigation=_optional_string(data.get("mitigation"), f"{where}.mitigation"),
    )


def project_from_dict(raw: Any) -> Project:
    """Parse a decoded JSON document into a :class:`Project`.

    The parser checks JSON shape and field types only. Planning invariants
    (cycles, duplicate IDs, impossible dates) are handled by
    :func:`project_advisor.validation.validate_project`.

    Args:
        raw: Decoded JSON object.

    Raises:
        InputError: If the document is structurally invalid.
    """
    data = _mapping(raw, "project")
    tasks = tuple(
        task_from_dict(item, index)
        for index, item in enumerate(_sequence(_required(data, "tasks", "project"), "project.tasks"))
    )
    team = tuple(
        team_member_from_dict(item, index)
        for index, item in enumerate(_sequence(data.get("team", []), "project.team"))
    )
    risks = tuple(
        risk_from_dict(item, index)
        for index, item in enumerate(_sequence(data.get("risks", []), "project.risks"))
    )
    deadline_raw = data.get("deadline")
    deadline = None if deadline_raw is None else _date(deadline_raw, "project.deadline")
    metadata = _mapping(data.get("metadata", {}), "project.metadata")
    return Project(
        name=_string(_required(data, "name", "project"), "project.name"),
        start_date=_date(_required(data, "start_date", "project"), "project.start_date"),
        tasks=tasks,
        team=team,
        risks=risks,
        deadline=deadline,
        sprint_days=_integer(data.get("sprint_days", 10), "project.sprint_days"),
        metadata=metadata,
    )
