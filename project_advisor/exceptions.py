"""Exception types raised by the project advisor."""

from __future__ import annotations

from collections.abc import Iterable

from project_advisor.issues import Issue


class ProjectAdvisorError(Exception):
    """Base class for every error raised deliberately by the package."""


class InputError(ProjectAdvisorError):
    """Raised when a project document cannot be parsed into the domain model."""


class ValidationError(ProjectAdvisorError):
    """Raised when a parsed project violates a planning invariant.

    Attributes:
        issues: Immutable tuple of :class:`~project_advisor.models.Issue`
            objects describing every problem found.
    """

    def __init__(self, issues: Iterable[Issue]) -> None:
        self.issues: tuple[Issue, ...] = tuple(issues)
        detail = "; ".join(f"{issue.code}: {issue.message}" for issue in self.issues)
        super().__init__(detail or "project validation failed")
