"""A realistic, fully offline demo project used by the CLI and docs."""

from __future__ import annotations

from datetime import date

from project_advisor.models import Estimate, Project, Risk, Task, TeamMember


def demo_project() -> Project:
    """Return the deterministic "Atlas" release-planning demo.

    The scenario is a cross-functional software release with parallel design,
    backend, data, and frontend streams, a security gate, a documentation and
    training tail, and a mixed risk register.
    """
    tasks = (
        Task(
            "DISC",
            "Discovery and success metrics",
            Estimate(4, 6, 10),
            skills=("product",),
            owner="pm",
            priority=1,
            description="Interview stakeholders, agree outcomes, and baseline scope.",
        ),
        Task(
            "ARCH",
            "Solution architecture and ADRs",
            Estimate(4, 7, 11),
            dependencies=("DISC",),
            skills=("architecture",),
            owner="arch",
            priority=1,
            description="Produce the target architecture and decision records.",
        ),
        Task(
            "UIX",
            "UX flows and high-fidelity prototype",
            Estimate(7, 10, 16),
            dependencies=("DISC",),
            skills=("design",),
            owner="design",
            priority=2,
            description="Validate the primary journey with five users.",
        ),
        Task(
            "API",
            "Core API and domain model",
            Estimate(9, 13, 20),
            dependencies=("ARCH",),
            skills=("backend",),
            owner="be",
            priority=1,
            description="Implement the core service and persistence layer.",
        ),
        Task(
            "FE",
            "Web client implementation",
            Estimate(10, 15, 22),
            dependencies=("UIX", "ARCH"),
            skills=("frontend", "design"),
            owner="fe",
            priority=2,
            description="Build the responsive client against the API contract.",
        ),
        Task(
            "DATA",
            "Analytics events and dashboards",
            Estimate(5, 8, 12),
            dependencies=("ARCH",),
            skills=("data",),
            owner="be",
            priority=3,
            description="Instrument the funnel and publish the launch dashboard.",
        ),
        Task(
            "INT",
            "Integration and contract tests",
            Estimate(4, 6, 9),
            dependencies=("API", "DATA"),
            skills=("backend", "qa"),
            owner="qa",
            priority=2,
            description="Prove the API, data, and client contracts hold together.",
        ),
        Task(
            "SEC",
            "Security and privacy review",
            Estimate(3, 5, 8),
            dependencies=("API",),
            skills=("security", "backend"),
            owner="devops",
            priority=1,
            description="Threat model, dependency scan, and privacy sign-off.",
        ),
        Task(
            "QA",
            "End-to-end regression pass",
            Estimate(6, 9, 14),
            dependencies=("FE", "INT"),
            skills=("qa",),
            owner="qa",
            priority=2,
            description="Execute the release regression suite and triage defects.",
        ),
        Task(
            "DOC",
            "Release notes and operator guide",
            Estimate(2, 4, 6),
            dependencies=("FE", "INT"),
            skills=("product", "techwriting"),
            owner="pm",
            priority=4,
            description="Document changes, rollout, and rollback steps.",
        ),
        Task(
            "DEPLOY",
            "Production rollout and monitoring",
            Estimate(2, 3, 5),
            dependencies=("QA", "SEC", "DOC"),
            skills=("devops",),
            owner="devops",
            priority=1,
            description="Ship behind a flag, monitor SLOs, and enable progressively.",
        ),
        Task(
            "TRAIN",
            "Support-team enablement",
            Estimate(2, 3, 5),
            dependencies=("DOC",),
            skills=("product",),
            owner="pm",
            priority=5,
            description="Run enablement and publish the support playbook.",
        ),
        Task(
            "RETRO",
            "Launch retrospective",
            Estimate(1, 1, 2),
            dependencies=("DEPLOY", "TRAIN"),
            skills=("product",),
            owner="pm",
            priority=5,
            description="Capture outcomes, surprises, and follow-up actions.",
        ),
    )
    team = (
        TeamMember("pm", "Maya (Product lead)", ("product", "techwriting"), 8.0),
        TeamMember("arch", "Ravi (Architect)", ("architecture", "backend"), 8.0),
        TeamMember("design", "Lena (Product designer)", ("design",), 7.0),
        TeamMember("fe", "Tomas (Frontend)", ("frontend", "design"), 9.0),
        TeamMember("be", "Aisha (Backend/Data)", ("backend", "data"), 9.0),
        TeamMember("qa", "Noah (QA)", ("qa", "backend"), 8.0),
        TeamMember("devops", "Priya (DevOps/Security)", ("devops", "security", "backend"), 8.0),
    )
    risks = (
        Risk(
            "R1",
            "Third-party payment sandbox changes its contract",
            4,
            4,
            category="external",
            owner="arch",
            mitigation="Pin the sandbox version and keep a recorded-contract test double.",
        ),
        Risk("R2", "Security review finds a high-severity dependency issue", 5, 5, category="technical", owner="devops"),
        Risk("R3", "Designer availability drops during prototype week", 3, 4, category="resource", owner="pm"),
        Risk("R4", "Stakeholders add a reporting requirement late", 3, 3, category="scope", owner="pm"),
        Risk("R5", "Regression suite is flaky and slows the release", 4, 2, category="quality", owner="qa"),
        Risk("R6", "Rollout window collides with a company freeze", 2, 3, category="schedule", owner="devops"),
        Risk("R7", "Dashboard queries exceed the analytics budget", 2, 2, category="technical", owner="be"),
    )
    return Project(
        name="Atlas Release Readiness",
        start_date=date(2026, 1, 5),
        tasks=tasks,
        team=team,
        risks=risks,
        deadline=date(2026, 4, 30),
        sprint_days=10,
        metadata={"scenario": "demo", "industry": "software"},
    )


__all__ = ["demo_project"]
