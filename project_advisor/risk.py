"""Risk-register scoring, heat-map bucketing, and mitigation guidance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from project_advisor.models import Risk

BUCKETS: tuple[str, ...] = ("low", "medium", "high", "critical")

_DEFAULT_MITIGATIONS: dict[str, str] = {
    "technical": "Prototype the risky component early; add contract tests and a fallback design.",
    "schedule": "Add schedule buffer, split the work, and review progress at every sprint boundary.",
    "resource": "Cross-train a second owner and confirm availability before the sprint starts.",
    "scope": "Freeze the baseline, require change control, and re-estimate before accepting scope.",
    "quality": "Define acceptance criteria up front and automate regression checks in CI.",
    "external": "Agree milestones and escalation contacts with the vendor or dependency owner.",
}
_GENERIC_MITIGATION = "Assign an owner, define a trigger, and review this risk weekly."


def risk_score(risk: Risk) -> int:
    """Return the multiplicative probability-times-impact score (1-25)."""
    return risk.probability * risk.impact


def risk_bucket(score: int) -> str:
    """Map a 1-25 risk score to ``low``, ``medium``, ``high``, or ``critical``.

    Bands are ``<=4`` low, ``<=9`` medium, ``<=15`` high, and above 15
    critical. These correspond to common 5x5 probability-impact matrices.
    """
    if score <= 4:
        return "low"
    if score <= 9:
        return "medium"
    if score <= 15:
        return "high"
    return "critical"


def mitigation_suggestion(category: str) -> str:
    """Return a practical default mitigation for a risk category."""
    return _DEFAULT_MITIGATIONS.get(category.lower(), _GENERIC_MITIGATION)


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Scored view of one risk-register entry.

    Args:
        risk_id: Risk identifier.
        title: Risk statement.
        score: ``probability * impact``.
        bucket: Heat-map band.
        mitigation: Explicit mitigation or a category-based suggestion.
        owner: Accountable person, if supplied.
    """

    risk_id: str
    title: str
    score: int
    bucket: str
    mitigation: str
    owner: str | None


@dataclass(frozen=True, slots=True)
class RiskAnalysis:
    """Aggregated risk posture.

    Args:
        assessments: All risks, ordered from highest to lowest score.
        exposure: Sum of probability-times-impact scores.
        counts: Count per heat-map bucket.
        top_risks: Up to five highest-scored risks.
    """

    assessments: tuple[RiskAssessment, ...]
    exposure: int
    counts: dict[str, int]
    top_risks: tuple[RiskAssessment, ...]

    @property
    def highest_bucket(self) -> str:
        """Return the worst bucket present, or ``none`` for an empty register."""
        for bucket in reversed(BUCKETS):
            if self.counts[bucket]:
                return bucket
        return "none"


def analyze_risks(risks: Iterable[Risk]) -> RiskAnalysis:
    """Score, rank, and aggregate a risk register.

    Args:
        risks: Risk entries in any order.

    Returns:
        A :class:`RiskAnalysis` with deterministic ordering (score descending,
        then risk ID) and bucket counts for every band.
    """
    assessments = tuple(
        RiskAssessment(
            risk_id=risk.id,
            title=risk.title,
            score=risk_score(risk),
            bucket=risk_bucket(risk_score(risk)),
            mitigation=risk.mitigation if risk.mitigation is not None else mitigation_suggestion(risk.category),
            owner=risk.owner,
        )
        for risk in risks
    )
    ordered = tuple(sorted(assessments, key=lambda item: (-item.score, item.risk_id)))
    counts = {bucket: 0 for bucket in BUCKETS}
    for assessment in ordered:
        counts[assessment.bucket] += 1
    return RiskAnalysis(
        assessments=ordered,
        exposure=sum(assessment.score for assessment in ordered),
        counts=counts,
        top_risks=ordered[:5],
    )
