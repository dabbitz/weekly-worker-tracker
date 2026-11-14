import json
from datetime import date, datetime, timedelta, timezone
from itertools import count

from app.database.models import (
    Employee,
    Project,
    Task,
    TaskAssignment,
    TaskUpdate,
    WeeklyTaskPlan,
)
from app.services.week_utils import istanbul_day_start_utc
from app.services.weekly_report_metrics import (
    build_ai_payload,
    build_weekly_metrics,
    normalize_match_text,
)


UTC = timezone.utc
WEEK_START = date(2026, 11, 2)
WEEK_END = date(2026, 11, 8)
PRIOR_WEEK_START = date(2026, 10, 26)
AFTER_WEEK = date(2026, 11, 14)

_message_ids = count(10_000)


def at(day: date, hour: int = 10) -> datetime:
    return istanbul_day_start_utc(day) + timedelta(hours=hour)


async def add_employee(
    session,
    full_name: str = "Ali Veli",
    *,
    is_active: bool = True,
    telegram_user_id: int | None = None,
) -> Employee:
    employee = Employee(
        full_name=full_name,
        role="Saha",
        is_active=is_active,
        telegram_user_id=telegram_user_id,
    )
    session.add(employee)
    await session.flush()
    return employee


async def add_project(session, name: str = "Proje A") -> Project:
    project = Project(name=name, description="Açıklama")
    session.add(project)
    await session.flush()
    return project


async def add_task(
    session,
    project: Project,
    *,
    title: str = "Görev",
    start: date | None = WEEK_START,
    due: date | None = WEEK_END,
    description: str | None = None,
) -> Task:
    task = Task(
        project_id=project.id,
        title=title,
        description=description,
        planned_start_date=start,
        planned_due_date=due,
    )
    session.add(task)
    await session.flush()
    return task


async def assign(session, task: Task, employee: Employee) -> None:
    session.add(
        TaskAssignment(
            task_id=task.id,
            employee_id=employee.id,
            assigned_at=at(WEEK_START, 8),
        )
    )
    await session.flush()


async def add_plan(
    session,
    task: Task,
    *,
    week_start: date = WEEK_START,
    week_end: date = WEEK_END,
    target: int | None = 80,
    approved_at: datetime | None = None,
    status: str = "approved",
    description: str = "Haftalık hedef",
) -> WeeklyTaskPlan:
    plan = WeeklyTaskPlan(
        task_id=task.id,
        week_start_date=week_start,
        week_end_date=week_end,
        target_description=description,
        target_completion_percentage=target,
        status=status,
        source="manual",
        approved_at=(
            approved_at if approved_at is not None else at(WEEK_START, 9)
        ),
    )
    session.add(plan)
    await session.flush()
    return plan


async def add_update(
    session,
    *,
    task: Task | None,
    employee: Employee | None,
    received_at: datetime,
    status: str = "in_progress",
    completion: int | None = 50,
    blocker: str | None = None,
    delay_reason: str | None = None,
    next_step: str | None = None,
    summary: str | None = None,
    eta: date | None = None,
    review_status: str = "approved",
) -> TaskUpdate:
    update = TaskUpdate(
        task_id=task.id if task else None,
        employee_id=employee.id if employee else None,
        telegram_user_id=(
            employee.telegram_user_id if employee else 1
        )
        or 1,
        telegram_chat_id=555,
        telegram_message_id=next(_message_ids),
        original_message="gizli ham mesaj",
        status=status,
        completion_percentage=completion,
        blocker=blocker,
        delay_reason=delay_reason,
        next_step=next_step,
        reported_eta_date=eta,
        summary=summary,
        review_status=review_status,
        reviewed_by_employee_id=(
            employee.id
            if review_status != "pending" and employee is not None
            else None
        ),
        reviewed_at=(
            datetime.now(UTC)
            if review_status != "pending" and employee is not None
            else None
        ),
        received_at=received_at,
    )
    session.add(update)
    await session.flush()
    return update


async def build(session, *, today: date = AFTER_WEEK, week_start: date = WEEK_START):
    return await build_weekly_metrics(session, week_start, today=today)


def tasks_by_id(metrics) -> dict[int, dict]:
    return {item["id"]: item for item in metrics.snapshot["tasks"]}


def quality_codes(metrics) -> set[str]:
    return {
        item["code"] for item in metrics.snapshot["data_quality"]
    }


def candidate_codes(metrics) -> set[str]:
    return {
        item["code"]
        for item in metrics.snapshot["intervention_candidates"]
    }


async def test_week_window_and_partial_flag(session):
    metrics = await build(session, today=date(2026, 11, 4))

    assert metrics.week_start_date == WEEK_START
    assert metrics.week_end_date == WEEK_END
    assert metrics.is_partial_week is True
    assert metrics.is_current_week is True
    assert metrics.snapshot["week"]["timezone"] == "Europe/Istanbul"

    completed = await build(session, today=AFTER_WEEK)

    assert completed.is_partial_week is False
    assert completed.is_current_week is False


async def test_task_universe_by_dates_plans_and_reports(session):
    project = await add_project(session)
    dated = await add_task(
        session,
        project,
        title="Tarihli",
        start=date(2026, 11, 1),
        due=date(2026, 11, 10),
    )
    future = await add_task(
        session,
        project,
        title="Gelecek",
        start=date(2026, 11, 20),
        due=date(2026, 11, 30),
    )
    planned = await add_task(
        session,
        project,
        title="Tarihsiz planlı",
        start=None,
        due=None,
    )
    await add_plan(session, planned)
    unrelated = await add_task(
        session,
        project,
        title="Tarihsiz ilgisiz",
        start=None,
        due=None,
    )

    metrics = await build(session)
    ids = set(tasks_by_id(metrics))

    assert dated.id in ids
    assert planned.id in ids
    assert future.id not in ids
    assert unrelated.id not in ids


async def test_only_approved_reports_feed_activity(session):
    project = await add_project(session)
    employee = await add_employee(session)
    task = await add_task(session, project)
    await assign(session, task, employee)

    await add_update(
        session,
        task=task,
        employee=employee,
        received_at=at(date(2026, 11, 3), 10),
        completion=40,
        review_status="approved",
    )
    await add_update(
        session,
        task=task,
        employee=employee,
        received_at=at(date(2026, 11, 4), 10),
        completion=90,
        review_status="pending",
    )

    metrics = await build(session)
    summary = metrics.snapshot["summary"]

    assert summary["report_count"] == 1
    assert summary["pending_review_report_count"] == 1
    assert tasks_by_id(metrics)[task.id][
        "reported_completion_percentage"
    ] == 40
    assert "PENDING_REVIEW_REPORTS" in quality_codes(metrics)


async def test_plan_selected_by_intersection_not_week_start(session):
    project = await add_project(session)
    task = await add_task(
        session,
        project,
        start=date(2026, 10, 28),
        due=date(2026, 11, 15),
    )
    await add_plan(
        session,
        task,
        week_start=date(2026, 10, 28),
        week_end=date(2026, 11, 3),
        target=70,
    )
    await add_plan(
        session,
        task,
        week_start=date(2026, 11, 9),
        week_end=date(2026, 11, 15),
        target=95,
    )

    metrics = await build(session)
    snapshot_task = tasks_by_id(metrics)[task.id]

    assert metrics.snapshot["summary"]["plan_count"] == 1
    assert snapshot_task["plan"]["target_completion_percentage"] == 70
    assert snapshot_task["plan_conflict"] is False


async def test_plan_approved_after_week_is_not_official(session):
    project = await add_project(session)
    task = await add_task(session, project)
    await add_plan(
        session,
        task,
        target=80,
        approved_at=at(date(2026, 11, 9), 9),
    )

    metrics = await build(session)
    snapshot_task = tasks_by_id(metrics)[task.id]

    assert snapshot_task["classification"] == (
        "plan_approved_after_week"
    )
    assert snapshot_task["target_completion_percentage"] is None
    assert snapshot_task["plan"] is None
    assert "PLAN_APPROVED_AFTER_WEEK" in candidate_codes(metrics)


async def test_plan_conflict_never_picks_a_target(session):
    project = await add_project(session)
    task = await add_task(
        session,
        project,
        start=date(2026, 10, 26),
        due=date(2026, 11, 10),
    )
    await add_plan(
        session,
        task,
        week_start=date(2026, 10, 26),
        week_end=date(2026, 11, 3),
        target=60,
    )
    await add_plan(
        session,
        task,
        week_start=date(2026, 11, 1),
        week_end=date(2026, 11, 8),
        target=90,
    )

    metrics = await build(session)
    snapshot_task = tasks_by_id(metrics)[task.id]

    assert snapshot_task["plan_conflict"] is True
    assert snapshot_task["classification"] == "plan_conflict"
    assert snapshot_task["target_completion_percentage"] is None
    assert "PLAN_CONFLICT" in quality_codes(metrics)
    assert "PLAN_CONFLICT" in candidate_codes(metrics)


async def test_target_vs_actual_classifications(session):
    project = await add_project(session)
    employee = await add_employee(session)

    met = await add_task(session, project, title="Hedefe ulaşan")
    below = await add_task(session, project, title="Hedef altı")
    completed = await add_task(session, project, title="Tamamlanan")

    for task, target in ((met, 80), (below, 80), (completed, 80)):
        await assign(session, task, employee)
        await add_plan(session, task, target=target)

    await add_update(
        session,
        task=met,
        employee=employee,
        received_at=at(date(2026, 11, 3), 10),
        completion=85,
    )
    await add_update(
        session,
        task=below,
        employee=employee,
        received_at=at(date(2026, 11, 3), 11),
        completion=50,
    )
    await add_update(
        session,
        task=completed,
        employee=employee,
        received_at=at(date(2026, 11, 3), 12),
        status="completed",
        completion=100,
    )

    metrics = await build(session)
    snapshot = tasks_by_id(metrics)

    assert snapshot[met.id]["classification"] == "met"
    assert snapshot[below.id]["classification"] == "below_target"
    assert snapshot[completed.id]["classification"] == (
        "reported_completed"
    )


async def test_partial_week_never_marks_target_as_failed(session):
    project = await add_project(session)
    employee = await add_employee(session)
    task = await add_task(session, project)
    await assign(session, task, employee)
    await add_plan(session, task, target=80)
    await add_update(
        session,
        task=task,
        employee=employee,
        received_at=at(date(2026, 11, 3), 10),
        completion=20,
    )

    metrics = await build(session, today=date(2026, 11, 4))
    snapshot_task = tasks_by_id(metrics)[task.id]

    assert metrics.is_partial_week is True
    assert snapshot_task["classification"] == "partial"
    assert snapshot_task["classification_label"] == (
        "Kısmi değerlendirme"
    )


async def test_missing_report_and_missing_target_are_neutral(session):
    project = await add_project(session)
    employee = await add_employee(session)
    no_report = await add_task(session, project, title="Raporsuz")
    missing_target = await add_task(
        session,
        project,
        title="Hedefsiz",
    )

    await assign(session, no_report, employee)
    await assign(session, missing_target, employee)
    await add_plan(session, no_report, target=80)
    await add_plan(session, missing_target, target=None)
    await add_update(
        session,
        task=missing_target,
        employee=employee,
        received_at=at(date(2026, 11, 3), 10),
        completion=30,
    )

    metrics = await build(session)
    snapshot = tasks_by_id(metrics)

    assert snapshot[no_report.id]["classification"] == "no_report"
    assert snapshot[no_report.id]["classification_label"] == (
        "Rapor gönderilmedi"
    )
    assert snapshot[missing_target.id]["classification"] == (
        "target_missing"
    )
    assert "TASK_WITHOUT_REPORT" in quality_codes(metrics)
    assert "MISSING_TARGET_PERCENTAGE" in quality_codes(metrics)

    joined = json.dumps(metrics.snapshot, ensure_ascii=False).casefold()

    assert "başarısız" not in joined
    assert "ihmal edildi" not in joined


async def test_percentages_from_different_employees_are_not_averaged(
    session,
):
    project = await add_project(session)
    first = await add_employee(session, "Birinci Çalışan")
    second = await add_employee(session, "İkinci Çalışan")
    task = await add_task(session, project)
    await assign(session, task, first)
    await assign(session, task, second)
    await add_plan(session, task, target=80)

    await add_update(
        session,
        task=task,
        employee=first,
        received_at=at(date(2026, 11, 3), 10),
        completion=20,
    )
    await add_update(
        session,
        task=task,
        employee=second,
        received_at=at(date(2026, 11, 4), 10),
        completion=60,
    )

    metrics = await build(session)
    snapshot_task = tasks_by_id(metrics)[task.id]

    assert snapshot_task["reported_completion_percentage"] == 60

    employees = {
        item["employee_token"]: item
        for item in metrics.snapshot["employees"]
    }
    progress_values = {
        item["completion_percentage"]
        for employee in employees.values()
        for item in employee["task_progress"]
        if item["task_token"] == snapshot_task["task_token"]
    }

    assert progress_values == {20, 60}
    assert 40 not in progress_values


async def test_same_day_conflicting_reports_are_flagged(session):
    project = await add_project(session)
    first = await add_employee(session, "Birinci Çalışan")
    second = await add_employee(session, "İkinci Çalışan")
    task = await add_task(session, project)
    await assign(session, task, first)
    await assign(session, task, second)
    await add_plan(session, task, target=80)

    await add_update(
        session,
        task=task,
        employee=first,
        received_at=at(date(2026, 11, 3), 10),
        completion=20,
    )
    await add_update(
        session,
        task=task,
        employee=second,
        received_at=at(date(2026, 11, 3), 14),
        completion=60,
    )

    metrics = await build(session)
    snapshot_task = tasks_by_id(metrics)[task.id]

    assert snapshot_task["conflicting_reports"] is True
    assert "CONFLICTING_REPORTS" in quality_codes(metrics)
    assert "CONFLICTING_REPORTS" in candidate_codes(metrics)


async def test_overdue_unassigned_and_eta_slipped(session):
    project = await add_project(session)
    employee = await add_employee(session)

    overdue = await add_task(
        session,
        project,
        title="Geciken",
        start=date(2026, 11, 1),
        due=date(2026, 11, 5),
    )
    await add_update(
        session,
        task=overdue,
        employee=employee,
        received_at=at(date(2026, 11, 4), 10),
        completion=30,
    )

    eta_slipped = await add_task(
        session,
        project,
        title="ETA ötelenen",
        start=date(2026, 11, 1),
        due=date(2026, 11, 20),
    )
    await assign(session, eta_slipped, employee)
    await add_update(
        session,
        task=eta_slipped,
        employee=employee,
        received_at=at(date(2026, 11, 4), 11),
        completion=30,
        eta=date(2026, 11, 25),
    )

    metrics = await build(session)
    snapshot = tasks_by_id(metrics)

    assert snapshot[overdue.id]["overdue"] is True
    assert snapshot[overdue.id]["unassigned"] is True
    assert snapshot[eta_slipped.id]["eta_slipped"] is True

    codes = candidate_codes(metrics)
    assert "OVERDUE_NOT_REPORTED_COMPLETE" in codes
    assert "UNASSIGNED_ACTIVE_TASK" in codes
    assert "ETA_SLIPPED" in codes


async def test_repeated_blocker_requires_exact_normalized_match(session):
    project = await add_project(session)
    employee = await add_employee(session)
    task = await add_task(
        session,
        project,
        start=date(2026, 10, 26),
        due=date(2026, 11, 10),
    )
    await assign(session, task, employee)

    await add_update(
        session,
        task=task,
        employee=employee,
        received_at=at(date(2026, 10, 28), 10),
        blocker="Malzeme temini gecikti",
        completion=20,
    )
    await add_update(
        session,
        task=task,
        employee=employee,
        received_at=at(date(2026, 11, 3), 10),
        blocker="malzeme temini gecikti!",
        completion=30,
    )
    await add_update(
        session,
        task=task,
        employee=employee,
        received_at=at(date(2026, 11, 4), 10),
        blocker="Malzeme gecikmesi",
        completion=35,
    )

    assert normalize_match_text("Malzeme temini gecikti") == (
        normalize_match_text("malzeme temini gecikti!")
    )
    assert normalize_match_text("Malzeme temini gecikti") != (
        normalize_match_text("Malzeme gecikmesi")
    )

    metrics = await build(session)

    assert len(metrics.snapshot["repeated_blockers"]) == 1
    assert "REPEATED_BLOCKER" in candidate_codes(metrics)


async def test_prior_week_comparison_and_insufficient_history(session):
    project = await add_project(session)
    employee = await add_employee(session)
    task = await add_task(
        session,
        project,
        start=date(2026, 10, 26),
        due=date(2026, 11, 10),
    )
    await assign(session, task, employee)
    await add_update(
        session,
        task=task,
        employee=employee,
        received_at=at(date(2026, 11, 3), 10),
        completion=55,
    )

    without_history = await build(session)
    assert without_history.snapshot["comparison"]["available"] is False
    assert "INSUFFICIENT_HISTORY" in quality_codes(without_history)

    await add_update(
        session,
        task=task,
        employee=employee,
        received_at=at(date(2026, 10, 28), 10),
        completion=30,
    )

    with_history = await build(session)
    comparison = with_history.snapshot["comparison"]

    assert comparison["available"] is True
    assert comparison["prior_report_count"] == 1
    assert comparison["current_report_count"] == 1
    assert comparison["task_progress_changes"][0]["delta"] == 25


async def test_dateless_task_is_flagged_but_not_included(session):
    project = await add_project(session)
    await add_task(
        session,
        project,
        title="Tarihsiz görev",
        start=None,
        due=None,
    )

    metrics = await build(session)

    assert metrics.snapshot["summary"]["task_count"] == 0
    assert metrics.has_data is False

    item = next(
        quality
        for quality in metrics.snapshot["data_quality"]
        if quality["code"] == "TASK_WITHOUT_DATES"
    )
    assert "Tarihsiz görev" in item["task_labels"]


async def test_ai_payload_excludes_names_messages_and_ids(session):
    project = await add_project(session)
    employee = await add_employee(
        session,
        "Ayşe Yılmaz",
        telegram_user_id=987654321,
    )
    task = await add_task(session, project)
    await assign(session, task, employee)
    await add_plan(session, task, target=80)
    await add_update(
        session,
        task=task,
        employee=employee,
        received_at=at(date(2026, 11, 3), 10),
        completion=40,
        summary="Kalıp işleri sürüyor",
    )

    metrics = await build(session)
    payload = build_ai_payload(metrics)
    serialized = json.dumps(payload, ensure_ascii=False)

    assert "Ayşe Yılmaz" not in serialized
    assert "Ayşe" not in serialized
    assert "gizli ham mesaj" not in serialized
    assert "987654321" not in serialized
    assert "original_message" not in serialized
    assert "telegram_user_id" not in serialized
    assert payload["ai_references"]["E1"]["kind"] == "employee"
    assert payload["tasks"][0]["token"] == "T1"
    assert "Kalıp işleri sürüyor" in serialized


async def test_references_keep_real_labels_for_backend(session):
    project = await add_project(session, "Kule Projesi")
    employee = await add_employee(session, "Mehmet Demir")
    task = await add_task(session, project, title="Cephe boyası")
    await assign(session, task, employee)
    await add_update(
        session,
        task=task,
        employee=employee,
        received_at=at(date(2026, 11, 3), 10),
        completion=40,
    )

    metrics = await build(session)
    references = metrics.references

    assert references["projects"]["P1"]["label"] == "Kule Projesi"
    assert references["employees"]["E1"]["label"] == "Mehmet Demir"
    assert references["employees"]["E1"]["href"] == (
        f"/calisanlar/{employee.id}"
    )
    assert references["tasks"]["T1"]["label"] == "Cephe boyası"


async def test_future_dated_task_never_enters_past_week(session):
    project = await add_project(session)
    task = await add_task(
        session,
        project,
        start=date(2026, 11, 20),
        due=date(2026, 11, 30),
    )

    metrics = await build(session)

    assert task.id not in tasks_by_id(metrics)
