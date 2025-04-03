"""Executive Markdown report renderer."""

from __future__ import annotations

from collections.abc import Sequence

from project_advisor.forecast import PERCENTILES, add_working_days, finish_date, working_days_available
from project_advisor.plan import ProjectPlan


def _number(value: float) -> str:
    if abs(value) < 0.05:
        value = 0.0
    return f"{value:.1f}"


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def render_markdown(plan: ProjectPlan) -> str:
    """Render a complete executive report as GitHub-flavoured Markdown.

    The output is deterministic and contains no live-data or network claims.

    Args:
        plan: Plan produced by :func:`project_advisor.plan.build_plan`.

    Returns:
        Markdown text suitable for a CLI, pull request, or wiki page.
    """
    project = plan.project
    timings = {timing.task_id: timing for timing in plan.schedule.timings}
    lines: list[str] = [
        f"# Executive delivery plan: {project.name}",
        "",
        "_Generated offline by `project_advisor`. Durations are person-days; calendar "
        "dates assume Monday-Friday working days with no public holidays._",
        "",
        "## At a glance",
        "",
    ]
    deadline = project.deadline.isoformat() if project.deadline is not None else "not set"
    on_time = (
        f"{plan.forecast.on_time_probability:.0%}"
        if plan.forecast.on_time_probability is not None
        else "not calculated (no deadline)"
    )
    capacity_status = "feasible" if plan.capacity.feasible else "needs attention"
    lines.extend(
        _table(
            ("Metric", "Value"),
            (
                ("Start date", project.start_date.isoformat()),
                ("Target deadline", deadline),
                ("Validated tasks", str(len(project.tasks))),
                ("Team members", str(len(project.team))),
                ("Sprint length", f"{project.sprint_days} working days"),
                ("Expected duration (CPM)", f"{_number(plan.schedule.duration)} person-days"),
                ("Monte Carlo P50 / P80", f"{_number(plan.forecast.percentiles[50])} / {_number(plan.forecast.percentiles[80])} days"),
                ("On-time probability", on_time),
                ("Risk exposure", f"{plan.risks.exposure} (highest: {plan.risks.highest_bucket})"),
                ("Sprint capacity plan", capacity_status),
            ),
        )
    )
    lines.extend(["", "## Work breakdown structure", ""])
    if project.tasks:
        rows = []
        for task in project.tasks:
            timing = timings[task.id]
            rows.append(
                (
                    _cell(task.id),
                    _cell(task.name),
                    _cell(task.owner or "unassigned"),
                    str(task.priority),
                    _number(task.estimate.expected),
                    _number(timing.slack),
                    "yes" if timing.critical else "no",
                    _cell(", ".join(task.dependencies) or "-"),
                )
            )
        lines.extend(
            _table(
                ("ID", "Task", "Owner", "Priority", "Expected (d)", "Float (d)", "Critical", "Depends on"),
                rows,
            )
        )
    else:
        lines.append("_No tasks were provided._")
    lines.extend(["", "## Critical path", ""])
    if plan.schedule.critical_path:
        chain = " -> ".join(f"`{task_id}`" for task_id in plan.schedule.critical_path)
        lines.extend(
            [
                f"**Path:** {chain}",
                "",
                f"**Expected duration:** {_number(plan.schedule.duration)} person-days. "
                f"**PERT standard deviation:** {_number(plan.pert.standard_deviation)} days.",
            ]
        )
    else:
        lines.append("_The project has no tasks, so there is no critical path._")
    lines.extend(["", "## Sprint allocation", ""])
    if plan.capacity.assignments:
        rows = [
            (
                str(assignment.sprint),
                _cell(assignment.task_id),
                _cell(assignment.member_id),
                _number(assignment.effort),
            )
            for assignment in plan.capacity.assignments
        ]
        lines.extend(_table(("Sprint", "Task", "Member", "Effort (d)"), rows))
    else:
        lines.append("_No capacity-constrained assignments were produced._")
    lines.extend(["", "### Capacity signals", ""])
    if plan.capacity.overloaded_sprints:
        sprints = ", ".join(str(number) for number in plan.capacity.overloaded_sprints)
        lines.append(f"- **Overloaded sprints:** {sprints}. Ready work could not fit and was deferred.")
    else:
        lines.append("- **Overloaded sprints:** none detected.")
    if plan.capacity.spillover:
        lines.append(
            "- **Spillover:** "
            + ", ".join(f"`{task_id}`" for task_id in plan.capacity.spillover)
            + " started later than dependency-ready because of capacity."
        )
    else:
        lines.append("- **Spillover:** none.")
    if plan.capacity.skill_gaps:
        for gap in plan.capacity.skill_gaps:
            missing = ", ".join(gap.missing_skills) if gap.missing_skills else "no available team member"
            lines.append(f"- **Skill gap:** `{gap.task_id}` requires {missing}.")
    else:
        lines.append("- **Skill gaps:** none.")
    if plan.capacity.unscheduled:
        lines.append(
            "- **Unscheduled:** " + ", ".join(f"`{task_id}`" for task_id in plan.capacity.unscheduled) + "."
        )
    else:
        lines.append("- **Unscheduled:** none.")
    lines.extend(["", "## Risk register", ""])
    if plan.risks.assessments:
        counts = " | ".join(f"{bucket}: {count}" for bucket, count in plan.risks.counts.items())
        lines.extend([f"**Heat map:** {counts}. **Exposure:** {plan.risks.exposure}.", ""])
        rows = [
            (
                _cell(item.risk_id),
                _cell(item.title),
                str(item.score),
                item.bucket,
                _cell(item.owner or "unassigned"),
                _cell(item.mitigation),
            )
            for item in plan.risks.assessments
        ]
        lines.extend(_table(("ID", "Risk", "Score", "Bucket", "Owner", "Mitigation"), rows))
    else:
        lines.append("_No risks were registered._")
    lines.extend(["", "## Completion forecast", ""])
    lines.extend(
        _table(
            ("Measure", "Duration (working days)", "Indicative finish"),
            (
                ("Optimistic (CPM)", _number(plan.pert.optimistic_duration), finish_date(project.start_date, plan.pert.optimistic_duration).isoformat()),
                ("Expected (CPM/PERT)", _number(plan.pert.expected_duration), finish_date(project.start_date, plan.pert.expected_duration).isoformat()),
                ("Pessimistic (CPM)", _number(plan.pert.pessimistic_duration), finish_date(project.start_date, plan.pert.pessimistic_duration).isoformat()),
                *(
                    (
                        f"Monte Carlo P{percentage}",
                        _number(plan.forecast.percentiles[percentage]),
                        finish_date(project.start_date, plan.forecast.percentiles[percentage]).isoformat(),
                    )
                    for percentage in PERCENTILES
                ),
            ),
        )
    )
    lines.extend(
        [
            "",
            f"**Stochastic forecast:** {plan.forecast.simulations} simulations, seed "
            f"`{plan.forecast.seed}`, mean {_number(plan.forecast.mean)} days, "
            f"standard deviation {_number(plan.forecast.standard_deviation)} days.",
            "",
        ]
    )
    if project.deadline is not None:
        lines.append(
            f"**Deadline:** {project.deadline.isoformat()} leaves "
            f"{working_days_available(project.start_date, project.deadline)} working days; "
            f"the simulated on-time probability is {on_time}."
        )
    else:
        lines.append("_No deadline supplied, so on-time probability was not calculated._")
    lines.extend(
        [
            "",
            "## Assumptions and limitations",
            "",
            "- Estimates and capacities are in person-days and are treated as independent.",
            "- Tasks have one owner and one effort estimate; large tasks can span sprints.",
            "- The capacity scheduler is greedy and explainable, not a mathematically optimal solver.",
            "- PERT variance sums only critical-path task variances; Monte Carlo uses triangular draws.",
            "- Calendar dates skip weekends but not holidays; re-plan when real availability changes.",
            "",
        ]
    )
    return "\n".join(lines)
