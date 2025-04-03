"""Shared validation finding type."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Issue:
    """A single validation finding.

    Attributes:
        code: Stable machine-readable identifier, for example ``cycle``.
        message: Human-readable explanation suitable for a CLI or report.
        subject: Optional task, member, risk, or project identifier.
    """

    code: str
    message: str
    subject: str | None = None
