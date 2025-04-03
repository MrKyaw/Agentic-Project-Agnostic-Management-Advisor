"""Validation, JSON loading, and dependency-graph integrity checks."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from project_advisor.exceptions import InputError, ValidationError
from project_advisor.models import Issue, Project, project_from_dict
from project_advisor.schedule import topological_sort


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """The complete outcome of validating a project.

    Attributes:
        issues: Every problem found, in deterministic discovery order.
    """

    issues: tuple[Issue, ...] = ()

    @property
    def ok(self) -> bool:
        """Return ``True`` when no validation issues remain."""
        return not self.issues

    def raise_for_errors(self) -> None:
        """Raise :class:`ValidationError` if any issue was recorded."""
        if self.issues:
            raise ValidationError(self.issues)


def validate_project(project: Project) -> ValidationReport:
    """Validate planning invariants without mutating the project.

    Checks include empty names, impossible deadlines, duplicate task/member/
    risk identifiers, unknown owners, malformed estimates and priorities,
    invalid capacities and risk scales, unknown dependencies, and cycles.

    Args:
        project: Project to inspect.

    Returns:
        A :class:`ValidationReport`; call :meth:`ValidationReport.raise_for_errors`
        to convert findings into an exception.
    """
    issues: list[Issue] = []
    if not project.name.strip():
        issues.append(Issue("empty_project_name", "Project name must not be empty."))
    if project.sprint_days <= 0:
        issues.append(Issue("invalid_sprint_days", "sprint_days must be greater than zero."))
    if project.deadline is not None and project.deadline < project.start_date:
        issues.append(
            Issue(
                "impossible_deadline",
                f"deadline {project.deadline.isoformat()} is before start_date "
                f"{project.start_date.isoformat()}.",
            )
        )

    member_ids: set[str] = set()
    for member in project.team:
        if member.id in member_ids:
            issues.append(Issue("duplicate_member_id", f"Duplicate team member id {member.id!r}.", member.id))
        if not member.id.strip():
            issues.append(Issue("empty_member_id", "Team member id must not be empty."))
        if not member.name.strip():
            issues.append(Issue("empty_member_name", f"Team member {member.id!r} has an empty name.", member.id))
        if member.capacity <= 0 or not math.isfinite(member.capacity):
            issues.append(
                Issue(
                    "invalid_capacity",
                    f"Team member {member.id!r} capacity must be a positive finite number.",
                    member.id,
                )
            )
        member_ids.add(member.id)

    task_ids: set[str] = set()
    duplicate_task = False
    for task in project.tasks:
        if task.id in task_ids:
            issues.append(Issue("duplicate_task_id", f"Duplicate task id {task.id!r}.", task.id))
            duplicate_task = True
        if not task.id.strip():
            issues.append(Issue("empty_task_id", "Task id must not be empty."))
        if not task.name.strip():
            issues.append(Issue("empty_task_name", f"Task {task.id!r} has an empty name.", task.id))
        if task.priority < 1 or task.priority > 5:
            issues.append(Issue("invalid_priority", f"Task {task.id!r} priority must be between 1 and 5.", task.id))
        estimates = (task.estimate.optimistic, task.estimate.most_likely, task.estimate.pessimistic)
        if any(not math.isfinite(value) for value in estimates):
            issues.append(Issue("non_finite_estimate", f"Task {task.id!r} has a non-finite estimate.", task.id))
        elif any(value < 0 for value in estimates):
            issues.append(Issue("negative_estimate", f"Task {task.id!r} has a negative estimate.", task.id))
        elif not (task.estimate.optimistic <= task.estimate.most_likely <= task.estimate.pessimistic):
            issues.append(
                Issue(
                    "estimate_order",
                    f"Task {task.id!r} must satisfy optimistic <= most_likely <= pessimistic.",
                    task.id,
                )
            )
        if task.owner is not None and task.owner not in member_ids:
            issues.append(Issue("unknown_owner", f"Task {task.id!r} owner {task.owner!r} is not on the team.", task.id))
        task_ids.add(task.id)

    if not duplicate_task:
        try:
            topological_sort(project.tasks)
        except ValidationError as exc:
            issues.extend(exc.issues)

    risk_ids: set[str] = set()
    for risk in project.risks:
        if risk.id in risk_ids:
            issues.append(Issue("duplicate_risk_id", f"Duplicate risk id {risk.id!r}.", risk.id))
        if not 1 <= risk.probability <= 5:
            issues.append(Issue("invalid_probability", f"Risk {risk.id!r} probability must be between 1 and 5.", risk.id))
        if not 1 <= risk.impact <= 5:
            issues.append(Issue("invalid_impact", f"Risk {risk.id!r} impact must be between 1 and 5.", risk.id))
        if risk.owner is not None and risk.owner not in member_ids:
            issues.append(Issue("unknown_risk_owner", f"Risk {risk.id!r} owner {risk.owner!r} is not on the team.", risk.id))
        risk_ids.add(risk.id)

    return ValidationReport(tuple(issues))


def load_project(path: str | Path) -> Project:
    """Read and parse a JSON project document.

    Args:
        path: Filesystem path to a UTF-8 JSON document.

    Returns:
        The parsed project. Structural validation is left to
        :func:`validate_project`.

    Raises:
        InputError: If the document is not valid JSON or has the wrong shape.
        OSError: If the file cannot be read.
    """
    text = Path(path).read_text(encoding="utf-8")
    try:
        raw = json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InputError(f"{path}: invalid JSON ({exc})") from exc
    return project_from_dict(raw)
