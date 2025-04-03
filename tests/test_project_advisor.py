"""Comprehensive tests for the deterministic project advisor package.

The suite exercises every public function and both sides of every decision
branch in ``project_advisor``. It uses no network, no external services, and
no wall-clock-dependent behaviour.
"""

from __future__ import annotations

import importlib
import json
import sys
from datetime import date
from pathlib import Path

import pytest

from project_advisor import (
    Estimate,
    InputError,
    Issue,
    Project,
    ProjectAdvisorError,
    Risk,
    Task,
    TeamMember,
    ValidationError,
    add_working_days,
    analyze_risks,
    build_plan,
    critical_path,
    demo_project,
    finish_date,
    load_project,
    mitigation_suggestion,
    monte_carlo_forecast,
    pert_estimate,
    plan_to_dict,
    project_from_dict,
    render_markdown,
    risk_bucket,
    risk_score,
    schedule_sprints,
    topological_sort,
    validate_project,
    working_days_available,
)
from project_advisor.cli import main
from project_advisor.plan import ProjectPlan
from project_advisor.risk import BUCKETS
from project_advisor.validation import ValidationReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def estimate(optimistic: float, most_likely: float | None = None, pessimistic: float | None = None) -> Estimate:
    if most_likely is None:
        most_likely = optimistic
    if pessimistic is None:
        pessimistic = optimistic
    return Estimate(float(optimistic), float(most_likely), float(pessimistic))


def make_task(
    task_id: str,
    effort: float = 2.0,
    dependencies: tuple[str, ...] = (),
    skills: tuple[str, ...] = (),
    owner: str | None = None,
    priority: int = 3,
    name: str | None = None,
) -> Task:
    return Task(
        id=task_id,
        name=name or f"Task {task_id}",
        estimate=estimate(effort),
        dependencies=dependencies,
        skills=skills,
        owner=owner,
        priority=priority,
    )


def make_member(member_id: str, skills: tuple[str, ...] = (), capacity: float = 10.0) -> TeamMember:
    return TeamMember(member_id, f"Member {member_id}", skills, capacity)


def make_project(
    tasks: tuple[Task, ...] = (),
    team: tuple[TeamMember, ...] = (),
    risks: tuple[Risk, ...] = (),
    deadline: date | None = None,
    start: date = date(2026, 1, 5),
    name: str = "Test Project",
    sprint_days: int = 10,
) -> Project:
    return Project(
        name=name,
        start_date=start,
        tasks=tasks,
        team=team,
        risks=risks,
        deadline=deadline,
        sprint_days=sprint_days,
    )


def project_document() -> dict:
    return {
        "name": "Documented Project",
        "start_date": "2026-02-02",
        "deadline": "2026-03-06",
        "sprint_days": 5,
        "metadata": {"industry": "fintech"},
        "tasks": [
            {
                "id": "A",
                "name": "Discover",
                "description": "Write the brief",
                "estimate": {"optimistic": 1, "most_likely": 2, "pessimistic": 4},
                "dependencies": [],
                "skills": ["product"],
                "owner": "pm",
                "priority": 1,
            },
            {
                "id": "B",
                "name": "Build",
                "estimate": {"optimistic": 2, "most_likely": 3, "pessimistic": 5},
                "dependencies": ["A"],
                "skills": ["backend"],
                "priority": 2,
            },
        ],
        "team": [
            {"id": "pm", "name": "Maya", "skills": ["product"], "capacity": 5},
            {"id": "be", "name": "Aisha", "skills": ["backend"], "capacity": 5},
        ],
        "risks": [
            {
                "id": "R1",
                "title": "Vendor delay",
                "probability": 3,
                "impact": 4,
                "category": "external",
                "owner": "pm",
                "mitigation": "Track the vendor milestone weekly.",
            }
        ],
    }


# ---------------------------------------------------------------------------
# Model and JSON parsing
# ---------------------------------------------------------------------------


def test_estimate_properties() -> None:
    item = Estimate(2.0, 4.0, 12.0)
    assert item.expected == pytest.approx((2 + 16 + 12) / 6)
    assert item.variance == pytest.approx(((12 - 2) / 6) ** 2)
    assert item.standard_deviation == pytest.approx((12 - 2) / 6)


def test_project_document_round_trip() -> None:
    project = project_from_dict(project_document())
    assert project.name == "Documented Project"
    assert project.start_date == date(2026, 2, 2)
    assert project.deadline == date(2026, 3, 6)
    assert project.sprint_days == 5
    assert project.metadata == {"industry": "fintech"}
    assert project.tasks[0].description == "Write the brief"
    assert project.tasks[0].owner == "pm"
    assert project.tasks[1].dependencies == ("A",)
    assert project.tasks[1].skills == ("backend",)
    assert project.team[1].capacity == 5.0
    assert project.risks[0].category == "external"
    assert project.risks[0].mitigation == "Track the vendor milestone weekly."


def test_project_document_minimal_defaults() -> None:
    project = project_from_dict({"name": "Minimal", "start_date": "2026-01-01", "tasks": []})
    assert project.team == ()
    assert project.risks == ()
    assert project.deadline is None
    assert project.sprint_days == 10
    assert project.metadata == {}


def test_project_document_optional_null_fields() -> None:
    document = project_document()
    document["deadline"] = None
    document["tasks"][0]["owner"] = None
    document["tasks"][0]["description"] = ""
    document["team"][0]["skills"] = []
    document["risks"][0]["owner"] = None
    document["risks"][0]["mitigation"] = None
    document["risks"][0].pop("category")
    project = project_from_dict(document)
    assert project.deadline is None
    assert project.tasks[0].owner is None
    assert project.team[0].skills == ()
    assert project.risks[0].owner is None
    assert project.risks[0].category == "technical"


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"start_date": "2026-01-01", "tasks": []},
        {"name": 7, "start_date": "2026-01-01", "tasks": []},
        {"name": "X", "tasks": []},
        {"name": "X", "start_date": 20260101, "tasks": []},
        {"name": "X", "start_date": "not-a-date", "tasks": []},
        {"name": "X", "start_date": "2026-01-01", "tasks": 1},
        {"name": "X", "start_date": "2026-01-01", "tasks": [], "team": 1},
        {"name": "X", "start_date": "2026-01-01", "tasks": [], "risks": 1},
        {"name": "X", "start_date": "2026-01-01", "tasks": [], "metadata": []},
        {"name": "X", "start_date": "2026-01-01", "tasks": [], "sprint_days": True},
        {"name": "X", "start_date": "2026-01-01", "tasks": [], "sprint_days": "10"},
        {"name": "X", "start_date": "2026-01-01", "tasks": [], "deadline": 4},
        {"name": "X", "start_date": "2026-01-01", "tasks": [], "deadline": "nope"},
    ],
)
def test_project_document_shape_errors(payload: object) -> None:
    with pytest.raises(InputError):
        project_from_dict(payload)


@pytest.mark.parametrize(
    "task",
    [
        "not-a-task",
        {"name": "No id", "estimate": {"optimistic": 1, "most_likely": 1, "pessimistic": 1}},
        {"id": 1, "name": "Bad id", "estimate": {"optimistic": 1, "most_likely": 1, "pessimistic": 1}},
        {"id": "A", "estimate": {"optimistic": 1, "most_likely": 1, "pessimistic": 1}},
        {"id": "A", "name": 3, "estimate": {"optimistic": 1, "most_likely": 1, "pessimistic": 1}},
        {"id": "A", "name": "No estimate"},
        {"id": "A", "name": "Bad estimate", "estimate": 4},
        {"id": "A", "name": "Missing o", "estimate": {"most_likely": 1, "pessimistic": 1}},
        {"id": "A", "name": "Missing m", "estimate": {"optimistic": 1, "pessimistic": 1}},
        {"id": "A", "name": "Missing p", "estimate": {"optimistic": 1, "most_likely": 1}},
        {"id": "A", "name": "Bool", "estimate": {"optimistic": True, "most_likely": 1, "pessimistic": 1}},
        {"id": "A", "name": "Text", "estimate": {"optimistic": "1", "most_likely": 1, "pessimistic": 1}},
        {
            "id": "A",
            "name": "Bad deps",
            "estimate": {"optimistic": 1, "most_likely": 1, "pessimistic": 1},
            "dependencies": "B",
        },
        {
            "id": "A",
            "name": "Bad dep item",
            "estimate": {"optimistic": 1, "most_likely": 1, "pessimistic": 1},
            "dependencies": [2],
        },
        {
            "id": "A",
            "name": "Bad skills",
            "estimate": {"optimistic": 1, "most_likely": 1, "pessimistic": 1},
            "skills": 4,
        },
        {
            "id": "A",
            "name": "Bad skill item",
            "estimate": {"optimistic": 1, "most_likely": 1, "pessimistic": 1},
            "skills": [4],
        },
        {
            "id": "A",
            "name": "Bad owner",
            "estimate": {"optimistic": 1, "most_likely": 1, "pessimistic": 1},
            "owner": 5,
        },
        {
            "id": "A",
            "name": "Bad priority",
            "estimate": {"optimistic": 1, "most_likely": 1, "pessimistic": 1},
            "priority": True,
        },
        {
            "id": "A",
            "name": "Bad priority type",
            "estimate": {"optimistic": 1, "most_likely": 1, "pessimistic": 1},
            "priority": "1",
        },
        {
            "id": "A",
            "name": "Bad description",
            "estimate": {"optimistic": 1, "most_likely": 1, "pessimistic": 1},
            "description": 4,
        },
    ],
)
def test_task_shape_errors(task: object) -> None:
    with pytest.raises(InputError):
        project_from_dict({"name": "X", "start_date": "2026-01-01", "tasks": [task]})


@pytest.mark.parametrize(
    "member",
    [
        "nope",
        {"name": "No id"},
        {"id": 1, "name": "Bad id"},
        {"id": "m"},
        {"id": "m", "name": 2},
        {"id": "m", "name": "M", "skills": 4},
        {"id": "m", "name": "M", "skills": [2]},
        {"id": "m", "name": "M", "capacity": True},
        {"id": "m", "name": "M", "capacity": "8"},
    ],
)
def test_member_shape_errors(member: object) -> None:
    with pytest.raises(InputError):
        project_from_dict({"name": "X", "start_date": "2026-01-01", "tasks": [], "team": [member]})


@pytest.mark.parametrize(
    "risk",
    [
        "nope",
        {"title": "No id", "probability": 1, "impact": 1},
        {"id": 1, "title": "Bad id", "probability": 1, "impact": 1},
        {"id": "R", "probability": 1, "impact": 1},
        {"id": "R", "title": 2, "probability": 1, "impact": 1},
        {"id": "R", "title": "No probability", "impact": 1},
        {"id": "R", "title": "No impact", "probability": 1},
        {"id": "R", "title": "Bool probability", "probability": True, "impact": 1},
        {"id": "R", "title": "Text probability", "probability": "1", "impact": 1},
        {"id": "R", "title": "Bool impact", "probability": 1, "impact": True},
        {"id": "R", "title": "Text impact", "probability": 1, "impact": "1"},
        {"id": "R", "title": "Bad category", "probability": 1, "impact": 1, "category": 4},
        {"id": "R", "title": "Bad owner", "probability": 1, "impact": 1, "owner": 4},
        {"id": "R", "title": "Bad mitigation", "probability": 1, "impact": 1, "mitigation": 4},
    ],
)
def test_risk_shape_errors(risk: object) -> None:
    with pytest.raises(InputError):
        project_from_dict({"name": "X", "start_date": "2026-01-01", "tasks": [], "risks": [risk]})


def test_issue_defaults_and_exception_messages() -> None:
    issue = Issue("code", "message")
    assert issue.subject is None
    error = ValidationError([issue])
    assert "code: message" in str(error)
    assert isinstance(error, ProjectAdvisorError)
    assert "project validation failed" in str(ValidationError([]))
    assert isinstance(InputError("bad"), ProjectAdvisorError)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_valid_demo_project() -> None:
    report = validate_project(demo_project())
    assert report.ok
    assert report.issues == ()
    report.raise_for_errors()


def test_validation_report_raises() -> None:
    report = ValidationReport((Issue("x", "broken"),))
    assert not report.ok
    with pytest.raises(ValidationError):
        report.raise_for_errors()


def test_validation_collects_domain_issues() -> None:
    project = Project(
        name="   ",
        start_date=date(2026, 1, 10),
        deadline=date(2026, 1, 1),
        sprint_days=0,
        tasks=(
            Task("A", "A", Estimate(-1, 2, 3), owner="ghost", priority=0),
            Task("A", "", Estimate(3, 2, 1)),
            Task("", "", Estimate(1, 1, float("inf")), priority=6),
        ),
        team=(
            TeamMember("m", "", (), 0),
            TeamMember("m", "", (), float("inf")),
            TeamMember("", "", (), 5),
        ),
        risks=(
            Risk("R", "low", 0, 1, owner="ghost"),
            Risk("R", "high", 6, 6),
        ),
    )
    report = validate_project(project)
    codes = [issue.code for issue in report.issues]
    for code in (
        "empty_project_name",
        "invalid_sprint_days",
        "impossible_deadline",
        "duplicate_member_id",
        "empty_member_name",
        "invalid_capacity",
        "empty_member_id",
        "duplicate_task_id",
        "empty_task_id",
        "empty_task_name",
        "negative_estimate",
        "invalid_priority",
        "non_finite_estimate",
        "estimate_order",
        "unknown_owner",
        "duplicate_risk_id",
        "invalid_probability",
        "invalid_impact",
        "unknown_risk_owner",
    ):
        assert code in codes
    assert not report.ok


def test_validation_estimate_order_and_finite() -> None:
    project = make_project(tasks=(Task("A", "A", Estimate(3, 2, 1)),))
    report = validate_project(project)
    assert [issue.code for issue in report.issues] == ["estimate_order"]


def test_validation_unknown_dependency() -> None:
    project = make_project(tasks=(Task("A", "A", estimate(1), dependencies=("B",)),))
    codes = [issue.code for issue in validate_project(project).issues]
    assert codes == ["unknown_dependency"]


def test_validation_cycle() -> None:
    project = make_project(
        tasks=(
            Task("A", "A", estimate(1), dependencies=("B",)),
            Task("B", "B", estimate(1), dependencies=("A",)),
        )
    )
    codes = [issue.code for issue in validate_project(project).issues]
    assert codes == ["cycle"]


def test_validation_duplicate_tasks_skip_graph_checks() -> None:
    project = make_project(
        tasks=(
            Task("A", "A", estimate(1), dependencies=("ghost",)),
            Task("A", "A", estimate(1)),
        )
    )
    codes = [issue.code for issue in validate_project(project).issues]
    assert codes == ["duplicate_task_id"]


# ---------------------------------------------------------------------------
# Topological sort and critical path
# ---------------------------------------------------------------------------


def test_topological_sort_empty_and_single() -> None:
    assert topological_sort(()) == ()
    assert topological_sort((make_task("A"),)) == ("A",)


def test_topological_sort_parallel_deterministic() -> None:
    tasks = (
        make_task("D", dependencies=("B", "C")),
        make_task("C", dependencies=("A",)),
        make_task("B", dependencies=("A",)),
        make_task("A"),
        make_task("E"),
    )
    assert topological_sort(tasks) == ("A", "B", "C", "D", "E")


def test_topological_sort_duplicate_dependency_is_idempotent() -> None:
    tasks = (make_task("A"), make_task("B", dependencies=("A", "A")))
    assert topological_sort(tasks) == ("A", "B")


def test_topological_sort_errors() -> None:
    with pytest.raises(ValidationError) as duplicate:
        topological_sort((make_task("A"), make_task("A")))
    assert duplicate.value.issues[0].code == "duplicate_task_id"

    with pytest.raises(ValidationError) as unknown:
        topological_sort((make_task("A", dependencies=("Z",)),))
    assert unknown.value.issues[0].code == "unknown_dependency"

    with pytest.raises(ValidationError) as cycle:
        topological_sort(
            (
                make_task("A", dependencies=("B",)),
                make_task("B", dependencies=("A",)),
            )
        )
    assert cycle.value.issues[0].code == "cycle"


def test_critical_path_empty() -> None:
    plan = critical_path(())
    assert plan.order == ()
    assert plan.timings == ()
    assert plan.duration == 0.0
    assert plan.critical_path == ()
    assert plan.critical_tasks == ()


def test_critical_path_single_task() -> None:
    plan = critical_path((make_task("A", 5),))
    timing = plan.timings[0]
    assert plan.duration == 5
    assert plan.critical_path == ("A",)
    assert timing.earliest_start == 0
    assert timing.latest_finish == 5
    assert timing.slack == 0
    assert timing.critical


def test_critical_path_parallel_paths_and_slack() -> None:
    tasks = (
        make_task("A", 2),
        make_task("B", 3, dependencies=("A",)),
        make_task("C", 4, dependencies=("A",)),
        make_task("D", 2, dependencies=("B", "C")),
    )
    plan = critical_path(tasks)
    timings = {timing.task_id: timing for timing in plan.timings}
    assert plan.duration == 8
    assert plan.critical_path == ("A", "C", "D")
    assert timings["B"].slack == 1
    assert not timings["B"].critical
    assert timings["C"].slack == 0
    assert plan.critical_tasks == ("A", "C", "D")


def test_critical_path_multiple_predecessors_and_zero_duration() -> None:
    tasks = (
        make_task("A", 0),
        make_task("B", 0, dependencies=("A",)),
        make_task("C", 0, dependencies=("A",)),
        make_task("D", 0, dependencies=("B", "C")),
    )
    plan = critical_path(tasks)
    assert plan.duration == 0
    assert plan.critical_path == ("A", "B", "D")


def test_critical_path_disconnected_nodes() -> None:
    tasks = (make_task("A", 5), make_task("B", 1))
    plan = critical_path(tasks)
    assert plan.duration == 5
    assert plan.critical_path == ("A",)
    timings = {timing.task_id: timing for timing in plan.timings}
    assert timings["B"].slack == 4


def test_dependency_successors() -> None:
    from project_advisor.schedule import dependency_successors

    tasks = (
        make_task("B", dependencies=("A",)),
        make_task("A"),
        make_task("C", dependencies=("A",)),
    )
    assert dependency_successors(tasks) == {"B": [], "A": ["B", "C"], "C": []}


# ---------------------------------------------------------------------------
# Capacity-constrained sprint allocation
# ---------------------------------------------------------------------------


def test_schedule_single_task() -> None:
    project = make_project(tasks=(make_task("A", 2),), team=(make_member("m", capacity=10),))
    plan = schedule_sprints(project)
    assert plan.feasible
    assert plan.unscheduled == ()
    assert plan.assignments[0].sprint == 1
    assert plan.assignments[0].member_id == "m"
    assert plan.sprints[0].capacity_used == 2
    assert plan.member_loads[0].utilization == pytest.approx(0.2)


def test_schedule_task_spans_sprints() -> None:
    project = make_project(tasks=(make_task("A", 15),), team=(make_member("m", capacity=10),))
    plan = schedule_sprints(project)
    assert [(item.sprint, item.effort) for item in plan.assignments] == [(1, 10.0), (2, 5.0)]
    assert plan.unscheduled == ()
    assert plan.feasible
    assert plan.spillover == ()


def test_schedule_dependencies_wait_for_completion() -> None:
    project = make_project(
        tasks=(
            make_task("A", 5, priority=1),
            make_task("B", 5, dependencies=("A",), priority=2),
        ),
        team=(make_member("m", capacity=10),),
    )
    plan = schedule_sprints(project)
    assert [(item.task_id, item.sprint) for item in plan.assignments] == [("A", 1), ("B", 2)]


def test_schedule_capacity_overload_and_spillover() -> None:
    project = make_project(
        tasks=(
            make_task("A", 10, priority=1),
            make_task("B", 5, priority=2),
        ),
        team=(make_member("m", capacity=10),),
    )
    plan = schedule_sprints(project)
    assert plan.overloaded_sprints == (1,)
    assert plan.spillover == ("B",)
    assert plan.feasible


def test_schedule_owner_preference_and_utilization() -> None:
    project = make_project(
        tasks=(make_task("A", 3, owner="second", priority=1),),
        team=(
            make_member("first", capacity=10),
            make_member("second", capacity=5),
        ),
    )
    plan = schedule_sprints(project)
    assert plan.assignments[0].member_id == "second"
    loads = {load.member_id: load for load in plan.member_loads}
    assert loads["first"].assigned == 0
    assert loads["second"].assigned == 3
    assert loads["second"].capacity == 5


def test_schedule_owner_unavailable_falls_back() -> None:
    project = make_project(
        tasks=(
            make_task("A", 10, owner="busy", priority=1),
            make_task("B", 5, owner="busy", priority=2),
        ),
        team=(
            make_member("busy", capacity=10),
            make_member("spare", capacity=10),
        ),
    )
    plan = schedule_sprints(project)
    records = {item.task_id: item.member_id for item in plan.assignments}
    assert records["B"] == "spare"


def test_schedule_owner_lacks_required_skill() -> None:
    project = make_project(
        tasks=(make_task("A", 2, skills=("design",), owner="dev", priority=1),),
        team=(
            make_member("dev", skills=("backend",), capacity=10),
            make_member("designer", skills=("design",), capacity=10),
        ),
    )
    plan = schedule_sprints(project)
    assert plan.assignments[0].member_id == "designer"


def test_schedule_tie_breaks_by_member_id() -> None:
    project = make_project(
        tasks=(make_task("A", 2),),
        team=(make_member("b", capacity=10), make_member("a", capacity=10)),
    )
    assert schedule_sprints(project).assignments[0].member_id == "a"


def test_schedule_continuing_owner_blocked_by_priority_work() -> None:
    project = make_project(
        tasks=(
            make_task("X", 1, priority=1),
            make_task("A", 15, priority=2),
            make_task("C", 10, dependencies=("X",), priority=1),
        ),
        team=(make_member("m", capacity=10),),
    )
    plan = schedule_sprints(project)
    assert plan.assignments[0].task_id == "X"
    by_sprint = {}
    for assignment in plan.assignments:
        by_sprint.setdefault(assignment.sprint, []).append(assignment.task_id)
    assert by_sprint[2] == ["C"]
    assert 2 in plan.overloaded_sprints
    assert plan.unscheduled == ()


def test_schedule_skill_gap() -> None:
    project = make_project(
        tasks=(make_task("A", 3, skills=("security",)),),
        team=(make_member("be", skills=("backend",), capacity=8),),
    )
    plan = schedule_sprints(project)
    assert not plan.feasible
    assert plan.unscheduled == ("A",)
    assert plan.skill_gaps[0].missing_skills == ("security",)
    assert plan.sprints[0].blocked_task_ids == ("A",)
    assert plan.member_loads[0].utilization == 0


def test_schedule_empty_team_with_no_skills() -> None:
    project = make_project(tasks=(make_task("A", 3),))
    plan = schedule_sprints(project)
    assert plan.skill_gaps[0].missing_skills == ()
    assert plan.unscheduled == ("A",)
    assert not plan.feasible


def test_schedule_max_horizon_leaves_partial_task_unscheduled() -> None:
    project = make_project(tasks=(make_task("A", 15),), team=(make_member("m", capacity=10),))
    plan = schedule_sprints(project, max_sprints=1)
    assert plan.unscheduled == ("A",)
    assert not plan.feasible


def test_schedule_invalid_horizon() -> None:
    with pytest.raises(InputError):
        schedule_sprints(make_project(), max_sprints=0)


def test_schedule_empty_project_with_team() -> None:
    project = make_project(team=(make_member("m", capacity=8),))
    plan = schedule_sprints(project)
    assert plan.sprints == ()
    assert plan.feasible
    assert plan.member_loads[0].capacity == 0
    assert plan.member_loads[0].utilization == 0


def test_schedule_zero_effort_milestone() -> None:
    project = make_project(tasks=(make_task("M", 0),), team=(make_member("m", capacity=10),))
    plan = schedule_sprints(project)
    assert plan.feasible
    assert plan.assignments[0].effort == 0
    assert plan.sprints[0].capacity_used == 0


def test_schedule_unscheduled_dependency_breaks_without_assignment() -> None:
    project = make_project(
        tasks=(
            make_task("A", 3, skills=("security",), priority=1),
            make_task("B", 2, dependencies=("A",), priority=2),
        ),
        team=(make_member("qa", skills=("qa",), capacity=8),),
    )
    plan = schedule_sprints(project)
    assert plan.unscheduled == ("A", "B")
    assert len(plan.sprints) == 1


def test_schedule_low_utilization() -> None:
    project = make_project(tasks=(make_task("A", 1),), team=(make_member("m", capacity=10),))
    plan = schedule_sprints(project, max_sprints=4)
    assert plan.member_loads[0].capacity == 10
    assert plan.member_loads[0].utilization == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# Risk analysis
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "bucket"),
    [(1, "low"), (4, "low"), (5, "medium"), (9, "medium"), (10, "high"), (15, "high"), (16, "critical"), (25, "critical")],
)
def test_risk_buckets(score: int, bucket: str) -> None:
    assert risk_bucket(score) == bucket


def test_risk_score_and_mitigations() -> None:
    risk = Risk("R", "Risk", 3, 4)
    assert risk_score(risk) == 12
    for category in ("technical", "schedule", "resource", "scope", "quality", "external"):
        assert mitigation_suggestion(category)
    assert mitigation_suggestion("TECHNICAL") == mitigation_suggestion("technical")
    assert mitigation_suggestion("unknown-category") == (
        "Assign an owner, define a trigger, and review this risk weekly."
    )


def test_risk_analysis_empty() -> None:
    analysis = analyze_risks(())
    assert analysis.assessments == ()
    assert analysis.exposure == 0
    assert analysis.top_risks == ()
    assert analysis.highest_bucket == "none"
    assert analysis.counts == {bucket: 0 for bucket in BUCKETS}


def test_risk_analysis_ordering_top_five_and_override() -> None:
    risks = (
        Risk("R6", "Low", 2, 2),
        Risk("R1", "Critical", 5, 5, mitigation="Explicit plan"),
        Risk("R2", "High", 3, 4),
        Risk("R3", "Medium", 3, 3, category="schedule"),
        Risk("R4", "Medium tie", 3, 3, owner="pm"),
        Risk("R5", "Tiny", 1, 1, category="unknown"),
    )
    analysis = analyze_risks(risks)
    assert [item.risk_id for item in analysis.assessments] == ["R1", "R2", "R3", "R4", "R6", "R5"]
    assert analysis.exposure == sum(risk_score(risk) for risk in risks)
    assert analysis.counts == {"low": 2, "medium": 2, "high": 1, "critical": 1}
    assert analysis.top_risks == analysis.assessments[:5]
    assert analysis.highest_bucket == "critical"
    assert analysis.assessments[0].mitigation == "Explicit plan"
    assert analysis.assessments[1].mitigation == mitigation_suggestion("technical")
    assert analysis.assessments[-1].mitigation == (
        "Assign an owner, define a trigger, and review this risk weekly."
    )


def test_risk_highest_bucket_medium() -> None:
    analysis = analyze_risks((Risk("R", "Medium", 3, 3),))
    assert analysis.highest_bucket == "medium"
    assert analysis.counts["medium"] == 1


# ---------------------------------------------------------------------------
# PERT, working days, and Monte Carlo
# ---------------------------------------------------------------------------


def test_add_working_days() -> None:
    monday = date(2026, 1, 5)
    assert add_working_days(monday, 0) == monday
    assert add_working_days(monday, -2) == monday
    assert add_working_days(monday, 5) == date(2026, 1, 12)
    assert add_working_days(monday, 1) == date(2026, 1, 6)
    assert add_working_days(date(2026, 1, 9), 1) == date(2026, 1, 12)
    assert add_working_days(monday, 0.2) == date(2026, 1, 6)


def test_finish_date() -> None:
    monday = date(2026, 1, 5)
    assert finish_date(monday, 0) == monday
    assert finish_date(monday, 1) == monday
    assert finish_date(monday, 5) == date(2026, 1, 9)
    assert finish_date(monday, 0.2) == monday
    assert finish_date(date(2026, 1, 9), 2) == date(2026, 1, 12)


def test_working_days_available() -> None:
    monday = date(2026, 1, 5)
    friday = date(2026, 1, 9)
    assert working_days_available(monday, friday) == 5
    assert working_days_available(monday, monday) == 1
    assert working_days_available(friday, monday) == 0
    assert working_days_available(date(2026, 1, 10), date(2026, 1, 11)) == 0


def test_pert_estimate_empty() -> None:
    estimate_result = pert_estimate(make_project())
    assert estimate_result.expected_duration == 0
    assert estimate_result.variance == 0
    assert estimate_result.standard_deviation == 0
    assert estimate_result.optimistic_duration == 0
    assert estimate_result.pessimistic_duration == 0
    assert estimate_result.critical_path == ()


def test_pert_estimate_parallel_paths() -> None:
    tasks = (
        Task("A", "A", Estimate(1, 2, 3)),
        Task("B", "B", Estimate(2, 3, 10), dependencies=("A",)),
        Task("C", "C", Estimate(1, 2, 3), dependencies=("A",)),
    )
    result = pert_estimate(make_project(tasks=tasks))
    assert result.expected_duration == pytest.approx(2 + 4)
    assert result.critical_path == ("A", "B")
    assert result.variance == pytest.approx((1 / 3) ** 2 + (8 / 6) ** 2)
    assert result.optimistic_duration == 3
    assert result.pessimistic_duration == 13


def test_monte_carlo_is_deterministic() -> None:
    project = demo_project()
    first = monte_carlo_forecast(project, simulations=200, seed=7)
    second = monte_carlo_forecast(project, simulations=200, seed=7)
    third = monte_carlo_forecast(project, simulations=200, seed=8)
    assert first == second
    assert first.percentiles[50] == second.percentiles[50]
    assert first.mean == second.mean
    assert first.percentiles[80] != third.percentiles[80]
    assert first.seed == 7
    assert first.simulations == 200
    assert list(first.percentiles) == [50, 80, 90, 95]
    assert first.percentiles[50] <= first.percentiles[80] <= first.percentiles[90] <= first.percentiles[95]


def test_monte_carlo_deadline_probability() -> None:
    tasks = (
        make_task("A", 3),
        make_task("B", 5, dependencies=("A",)),
    )
    generous = make_project(tasks=tasks, deadline=date(2026, 2, 27))
    impossible = make_project(tasks=tasks, deadline=date(2026, 1, 5))
    assert monte_carlo_forecast(generous, simulations=100, seed=1).on_time_probability == 1.0
    assert monte_carlo_forecast(impossible, simulations=100, seed=1).on_time_probability == 0.0
    assert monte_carlo_forecast(make_project(tasks=tasks), simulations=50, seed=1).on_time_probability is None


def test_monte_carlo_empty_and_zero_variance() -> None:
    empty = monte_carlo_forecast(make_project(), simulations=10, seed=1)
    assert empty.mean == 0
    assert empty.percentiles[95] == 0
    zero = monte_carlo_forecast(
        make_project(tasks=(make_task("A", 0),), deadline=date(2026, 1, 5)),
        simulations=10,
        seed=1,
    )
    assert zero.mean == 0
    assert zero.on_time_probability == 1.0


def test_monte_carlo_invalid_simulations() -> None:
    with pytest.raises(InputError):
        monte_carlo_forecast(make_project(), simulations=0)


# ---------------------------------------------------------------------------
# Plan composition and JSON
# ---------------------------------------------------------------------------


def test_build_plan_and_plan_to_dict() -> None:
    project = demo_project()
    plan = build_plan(project, simulations=150, seed=11, max_sprints=12)
    assert isinstance(plan, ProjectPlan)
    payload = plan_to_dict(plan)
    assert payload["project"]["task_count"] == len(project.tasks)
    assert payload["project"]["deadline"] == "2026-04-30"
    assert payload["summary"]["critical_path"] == list(plan.schedule.critical_path)
    assert payload["summary"]["sprints_used"] == len(plan.capacity.sprints)
    assert payload["summary"]["on_time_probability"] is not None
    assert len(payload["tasks"]) == len(project.tasks)
    assert payload["forecast"]["seed"] == 11
    assert set(payload["forecast"]["percentiles"]) == {"50", "80", "90", "95"}
    assert payload["capacity"]["feasible"] == plan.capacity.feasible
    assert payload["risks"]["items"][0]["bucket"] == "critical"
    json.dumps(payload)


def test_plan_to_dict_without_deadline() -> None:
    plan = build_plan(
        make_project(tasks=(make_task("A", 2),), team=(make_member("m"),)),
        simulations=20,
        seed=3,
    )
    payload = plan_to_dict(plan)
    assert payload["project"]["deadline"] is None
    assert payload["summary"]["on_time_probability"] is None
    assert payload["forecast"]["on_time_probability"] is None
    assert payload["capacity"]["skill_gaps"] == []


def test_build_plan_rejects_invalid_project() -> None:
    with pytest.raises(ValidationError):
        build_plan(make_project(tasks=(make_task("A", 1), make_task("A", 1))))


def test_build_plan_rejects_invalid_simulations() -> None:
    with pytest.raises(InputError):
        build_plan(make_project(), simulations=0)


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def test_render_full_report() -> None:
    plan = build_plan(demo_project(), simulations=100, seed=5)
    markdown = render_markdown(plan)
    assert markdown.startswith("# Executive delivery plan: Atlas Release Readiness")
    assert "## Work breakdown structure" in markdown
    assert "## Critical path" in markdown
    assert "## Sprint allocation" in markdown
    assert "## Risk register" in markdown
    assert "## Completion forecast" in markdown
    assert "On-time probability" in markdown
    assert "Overloaded sprints:" in markdown
    assert "Spillover:" in markdown
    assert "Skill gaps:" in markdown
    assert "Unscheduled:" in markdown
    assert "Deadline:" in markdown
    assert "person-days" in markdown


def test_render_empty_report() -> None:
    plan = build_plan(make_project(), simulations=10, seed=1)
    markdown = render_markdown(plan)
    assert "_No tasks were provided._" in markdown
    assert "_The project has no tasks, so there is no critical path._" in markdown
    assert "_No capacity-constrained assignments were produced._" in markdown
    assert "**Overloaded sprints:** none detected." in markdown
    assert "**Spillover:** none." in markdown
    assert "**Skill gaps:** none." in markdown
    assert "**Unscheduled:** none." in markdown
    assert "_No risks were registered._" in markdown
    assert "_No deadline supplied" in markdown
    assert "not calculated (no deadline)" in markdown


def test_render_skill_gap_and_escaped_cells() -> None:
    tasks = (
        Task("A", "Design | review\nphase", estimate(3), skills=("security",), owner=None),
        Task("B", "Blocked", estimate(2), dependencies=("A",)),
    )
    project = make_project(tasks=tasks, risks=(Risk("R", "Unclear scope", 2, 2),))
    plan = build_plan(project, simulations=20, seed=2)
    markdown = render_markdown(plan)
    assert "Design \\| review phase" in markdown
    assert "Skill gap:" in markdown
    assert "no available team member" not in markdown
    assert "requires security" in markdown
    assert "unassigned" in markdown


def test_render_ownerless_task_and_empty_skill_gap() -> None:
    project = make_project(tasks=(Task("A", "No team", estimate(1)),))
    markdown = render_markdown(build_plan(project, simulations=5, seed=1))
    assert "no available team member" in markdown


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def test_load_project(tmp_path: Path) -> None:
    path = tmp_path / "project.json"
    path.write_text(json.dumps(project_document()), encoding="utf-8")
    project = load_project(path)
    assert project.name == "Documented Project"
    assert load_project(str(path)) == project


def test_load_project_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(InputError, match="invalid JSON"):
        load_project(path)


def test_load_project_missing_returns_oserror(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        load_project(tmp_path / "missing.json")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_help() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_cli_version() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0


def test_cli_requires_source() -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_cli_rejects_two_sources() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["x.json", "--demo"])
    assert exc.value.code == 2


def test_cli_demo(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--demo", "--simulations", "30"]) == 0
    captured = capsys.readouterr()
    assert "Atlas Release Readiness" in captured.out
    assert captured.err == ""


def test_cli_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--demo", "--json", "--simulations", "20", "--seed", "9", "--sprints", "9"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["forecast"]["seed"] == 9
    assert payload["summary"]["sprints_used"] <= 9


def test_cli_file_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "project.json"
    path.write_text(json.dumps(project_document()), encoding="utf-8")
    assert main([str(path), "--simulations", "10"]) == 0
    assert "Documented Project" in capsys.readouterr().out


def test_cli_default_argv(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["project_advisor", "--demo", "--simulations", "5"])
    assert main() == 0
    assert "Atlas" in capsys.readouterr().out


def test_cli_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(tmp_path / "missing.json")]) == 2
    assert "cannot read project" in capsys.readouterr().err


def test_cli_invalid_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{oops", encoding="utf-8")
    assert main([str(path)]) == 2
    assert "invalid JSON" in capsys.readouterr().err


def test_cli_validation_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    document = project_document()
    document["tasks"].append(
        {
            "id": "C",
            "name": "Cycle",
            "estimate": {"optimistic": 1, "most_likely": 1, "pessimistic": 1},
            "dependencies": ["C"],
        }
    )
    path = tmp_path / "cycle.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    assert main([str(path)]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_invalid_sprints(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--demo", "--sprints", "0"]) == 2
    assert "max_sprints" in capsys.readouterr().err


def test_cli_invalid_simulations(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--demo", "--simulations", "0"]) == 2
    assert "simulations" in capsys.readouterr().err


def test_module_entry_point(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["project_advisor", "--demo", "--simulations", "5"])
    sys.modules.pop("project_advisor.__main__", None)
    with pytest.raises(SystemExit) as exc:
        importlib.import_module("project_advisor.__main__")
    assert exc.value.code == 0
    assert "Atlas" in capsys.readouterr().out
