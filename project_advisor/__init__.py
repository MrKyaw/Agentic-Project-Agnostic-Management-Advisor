"""Deterministic project-management decision engine.

``project_advisor`` turns a plain JSON description of a project into an
evidence-based delivery plan: work-breakdown validation, critical-path
analysis, capacity-constrained sprint allocation, risk scoring, PERT and
Monte Carlo forecasts, and an executive Markdown report.

The runtime package uses only the Python standard library. The original
CrewAI / FastAPI prototype lives in ``src/`` and is entirely optional.
"""

from project_advisor.capacity import (
    Assignment,
    CapacityPlan,
    MemberLoad,
    SkillGap,
    SprintPlan,
    schedule_sprints,
)
from project_advisor.demo import demo_project
from project_advisor.exceptions import InputError, ProjectAdvisorError, ValidationError
from project_advisor.forecast import (
    ForecastResult,
    PertEstimate,
    add_working_days,
    finish_date,
    monte_carlo_forecast,
    pert_estimate,
    working_days_available,
)
from project_advisor.models import (
    Estimate,
    Issue,
    Project,
    Risk,
    Task,
    TeamMember,
    project_from_dict,
)
from project_advisor.plan import ProjectPlan, build_plan, plan_to_dict
from project_advisor.report import render_markdown
from project_advisor.risk import (
    RiskAnalysis,
    RiskAssessment,
    analyze_risks,
    mitigation_suggestion,
    risk_bucket,
    risk_score,
)
from project_advisor.schedule import (
    SchedulePlan,
    TaskTiming,
    critical_path,
    topological_sort,
)
from project_advisor.validation import ValidationReport, load_project, validate_project

__all__ = [
    "Assignment",
    "CapacityPlan",
    "Estimate",
    "ForecastResult",
    "InputError",
    "Issue",
    "MemberLoad",
    "PertEstimate",
    "Project",
    "ProjectAdvisorError",
    "ProjectPlan",
    "Risk",
    "RiskAnalysis",
    "RiskAssessment",
    "SchedulePlan",
    "SkillGap",
    "SprintPlan",
    "Task",
    "TaskTiming",
    "TeamMember",
    "ValidationError",
    "ValidationReport",
    "add_working_days",
    "analyze_risks",
    "build_plan",
    "critical_path",
    "demo_project",
    "finish_date",
    "load_project",
    "mitigation_suggestion",
    "monte_carlo_forecast",
    "pert_estimate",
    "plan_to_dict",
    "project_from_dict",
    "render_markdown",
    "risk_bucket",
    "risk_score",
    "schedule_sprints",
    "topological_sort",
    "validate_project",
    "working_days_available",
]

__version__ = "1.0.0"
