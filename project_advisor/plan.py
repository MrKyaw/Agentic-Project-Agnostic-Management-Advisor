"""Composition of the complete advisory plan and its stable JSON form."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from project_advisor.capacity import CapacityPlan, schedule_sprints
from project_advisor.forecast import ForecastResult, PertEstimate, monte_carlo_forecast, pert_estimate
from project_advisor.models import Project
from project_advisor.risk import RiskAnalysis, analyze_risks
from project_advisor.schedule import SchedulePlan, critical_path
from project_advisor.validation import validate_project


@dataclass(frozen=True, slots=True)
class ProjectPlan:
    """All analyses produced for one project.

    Args:
        project: Validated input project.
        schedule: Critical-path analysis.
        capacity: Sprint allocation.
        risks: Risk-register analysis.
        pert: PERT estimate.
        forecast: Monte Carlo forecast.
        simulations: Simulation count used in the forecast.
        seed: Reproducibility seed.
    """

    project: Project
    schedule: SchedulePlan
    capacity: CapacityPlan
    risks: RiskAnalysis
    pert: PertEstimate
    forecast: ForecastResult
    simulations: int
    seed: int


def build_plan(
    project: Project,
    simulations: int = 1000,
    seed: int = 42,
    max_sprints: int | None = None,
) -> ProjectPlan:
    """Validate a project and run every analysis in a deterministic order.

    Args:
        project: Project description.
        simulations: Monte Carlo sample count.
        seed: Random seed for the forecast.
        max_sprints: Capacity-planning horizon. Defaults to one per task.

    Returns:
        A complete :class:`ProjectPlan`.

    Raises:
        ValidationError: If the project violates a planning invariant.
        InputError: If a simulation or sprint parameter is invalid.
    """
    validate_project(project).raise_for_errors()
    return ProjectPlan(
        project=project,
        schedule=critical_path(project.tasks),
        capacity=schedule_sprints(project, max_sprints=max_sprints),
        risks=analyze_risks(project.risks),
        pert=pert_estimate(project),
        forecast=monte_carlo_forecast(project, simulations=simulations, seed=seed),
        simulations=simulations,
        seed=seed,
    )


def _rounded(value: float) -> float:
    return round(value, 6)


def plan_to_dict(plan: ProjectPlan) -> dict[str, Any]:
    """Serialise a plan to a stable, JSON-safe dictionary.

    Lists follow deterministic domain order, never set or hash order, so two
    runs with the same inputs and seed produce identical JSON.
    """
    project = plan.project
    timings = {timing.task_id: timing for timing in plan.schedule.timings}
    return {
        "project": {
            "name": project.name,
            "start_date": project.start_date.isoformat(),
            "deadline": project.deadline.isoformat() if project.deadline is not None else None,
            "sprint_days": project.sprint_days,
            "task_count": len(project.tasks),
            "team_size": len(project.team),
        },
        "summary": {
            "expected_duration_days": _rounded(plan.schedule.duration),
            "critical_path": list(plan.schedule.critical_path),
            "sprints_used": len(plan.capacity.sprints),
            "unscheduled_tasks": list(plan.capacity.unscheduled),
            "risk_exposure": plan.risks.exposure,
            "highest_risk_bucket": plan.risks.highest_bucket,
            "forecast_p50_days": _rounded(plan.forecast.percentiles[50]),
            "forecast_p80_days": _rounded(plan.forecast.percentiles[80]),
            "on_time_probability": (
                _rounded(plan.forecast.on_time_probability)
                if plan.forecast.on_time_probability is not None
                else None
            ),
        },
        "tasks": [
            {
                "id": task.id,
                "name": task.name,
                "owner": task.owner,
                "priority": task.priority,
                "dependencies": list(task.dependencies),
                "skills": list(task.skills),
                "expected_days": _rounded(task.estimate.expected),
                "optimistic_days": _rounded(task.estimate.optimistic),
                "most_likely_days": _rounded(task.estimate.most_likely),
                "pessimistic_days": _rounded(task.estimate.pessimistic),
                "earliest_start": _rounded(timings[task.id].earliest_start),
                "earliest_finish": _rounded(timings[task.id].earliest_finish),
                "slack_days": _rounded(timings[task.id].slack),
                "critical": timings[task.id].critical,
            }
            for task in project.tasks
        ],
        "capacity": {
            "feasible": plan.capacity.feasible,
            "overloaded_sprints": list(plan.capacity.overloaded_sprints),
            "spillover_tasks": list(plan.capacity.spillover),
            "skill_gaps": [
                {"task_id": gap.task_id, "missing_skills": list(gap.missing_skills)}
                for gap in plan.capacity.skill_gaps
            ],
            "sprints": [
                {
                    "number": sprint.number,
                    "capacity_used": _rounded(sprint.capacity_used),
                    "capacity_total": _rounded(sprint.capacity_total),
                    "blocked_tasks": list(sprint.blocked_task_ids),
                    "assignments": [
                        {
                            "task_id": assignment.task_id,
                            "member_id": assignment.member_id,
                            "effort_days": _rounded(assignment.effort),
                        }
                        for assignment in sprint.assignments
                    ],
                }
                for sprint in plan.capacity.sprints
            ],
            "member_loads": [
                {
                    "member_id": load.member_id,
                    "assigned_days": _rounded(load.assigned),
                    "capacity_days": _rounded(load.capacity),
                    "utilization": _rounded(load.utilization),
                }
                for load in plan.capacity.member_loads
            ],
        },
        "risks": {
            "exposure": plan.risks.exposure,
            "counts": dict(plan.risks.counts),
            "items": [
                {
                    "id": assessment.risk_id,
                    "title": assessment.title,
                    "score": assessment.score,
                    "bucket": assessment.bucket,
                    "owner": assessment.owner,
                    "mitigation": assessment.mitigation,
                }
                for assessment in plan.risks.assessments
            ],
        },
        "pert": {
            "expected_duration_days": _rounded(plan.pert.expected_duration),
            "optimistic_duration_days": _rounded(plan.pert.optimistic_duration),
            "pessimistic_duration_days": _rounded(plan.pert.pessimistic_duration),
            "variance": _rounded(plan.pert.variance),
            "standard_deviation": _rounded(plan.pert.standard_deviation),
            "critical_path": list(plan.pert.critical_path),
        },
        "forecast": {
            "simulations": plan.forecast.simulations,
            "seed": plan.forecast.seed,
            "mean_days": _rounded(plan.forecast.mean),
            "standard_deviation": _rounded(plan.forecast.standard_deviation),
            "percentiles": {str(key): _rounded(value) for key, value in plan.forecast.percentiles.items()},
            "on_time_probability": (
                _rounded(plan.forecast.on_time_probability)
                if plan.forecast.on_time_probability is not None
                else None
            ),
        },
    }


__all__ = ["ProjectPlan", "build_plan", "plan_to_dict"]
