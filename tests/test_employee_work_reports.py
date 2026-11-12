from datetime import date, datetime, timezone

import pytest

from app.database.models import Project, Task, TaskAssignment, WeeklyTaskPlan
from app.services import employee_work_service
from app.services.exceptions import NotFoundError
from app.services.week_utils import (
    istanbul_today,
    monday_of,
    week_contains,
)
from tests.test_employees_tasks import seed_employee


TODAY = date(2026, 11, 16)  # Monday


async def seed_task(
    session,
    *,
    title: str = "Elektrik tesisatı",
    project_name: str = "Test Projesi",
    employee_ids: tuple[int, ...] = (),
    planned_start_date: date | None = None,
    planned_due_date: date | None = None,
) -> tuple[int, int]:
    project = Project(name=project_name)
    session.add(project)
    await session.flush()

    task = Task(
        project_id=project.id,
        title=title,
        planned_start_date=planned_start_date,
        planned_due_date=planned_due_date,
    )
    session.add(task)
    await session.flush()

    for employee_id in employee_ids:
        session.add(
            TaskAssignment(task_id=task.id, employee_id=employee_id)
        )

    await session.commit()

    return project.id, task.id


async def seed_plan(
    session,
    task_id: int,
    week_start_date: date,
    week_end_date: date,
    *,
    status: str = "approved",
    percentage: int | None = 50,
    description: str = "Haftalık hedef",
) -> int:
    plan = WeeklyTaskPlan(
        task_id=task_id,
        week_start_date=week_start_date,
        week_end_date=week_end_date,
        target_description=description,
        target_completion_percentage=percentage,
        status=status,
        source="manual",
    )
    session.add(plan)
    await session.commit()
    return plan.id


async def test_active_employee_is_found_by_telegram_id(session):
    employee_id = await seed_employee(
        session,
        "Aktif Çalışan",
        telegram_user_id=5001,
    )

    employee = await (
        employee_work_service.get_active_employee_by_telegram_id(
            session,
            5001,
        )
    )

    assert employee is not None
    assert employee.id == employee_id
    assert employee.full_name == "Aktif Çalışan"


async def test_inactive_employee_is_not_found(session):
    await seed_employee(
        session,
        "Pasif Çalışan",
        is_active=False,
        telegram_user_id=5002,
    )

    employee = await (
        employee_work_service.get_active_employee_by_telegram_id(
            session,
            5002,
        )
    )

    assert employee is None


async def test_unknown_telegram_id_returns_none(session):
    employee = await (
        employee_work_service.get_active_employee_by_telegram_id(
            session,
            999999,
        )
    )

    assert employee is None


async def test_employee_sees_only_assigned_tasks(session):
    employee_id = await seed_employee(
        session,
        "Atanmış Çalışan",
        telegram_user_id=5100,
    )
    other_id = await seed_employee(
        session,
        "Diğer Çalışan",
        telegram_user_id=5101,
    )

    project_id, assigned_task_id = await seed_task(
        session,
        title="Bana atanmış görev",
        employee_ids=(employee_id,),
    )
    await seed_task(
        session,
        title="Başkasına atanmış görev",
        project_name="Diğer Proje",
        employee_ids=(other_id,),
    )

    tasks = await employee_work_service.list_my_tasks(
        session,
        employee_id,
        TODAY,
    )

    assert [task.task_id for task in tasks] == [assigned_task_id]
    assert tasks[0].title == "Bana atanmış görev"
    assert tasks[0].project_id == project_id
    assert tasks[0].project_name == "Test Projesi"


async def test_other_employees_tasks_are_not_listed(session):
    employee_id = await seed_employee(
        session,
        "Birinci Çalışan",
        telegram_user_id=5200,
    )
    other_id = await seed_employee(
        session,
        "İkinci Çalışan",
        telegram_user_id=5201,
    )

    _, first_task_id = await seed_task(
        session,
        title="Birinci görev",
        employee_ids=(employee_id,),
    )
    _, second_task_id = await seed_task(
        session,
        title="İkinci görev",
        project_name="İkinci Proje",
        employee_ids=(other_id,),
    )

    other_tasks = await employee_work_service.list_my_tasks(
        session,
        other_id,
        TODAY,
    )

    assert [task.task_id for task in other_tasks] == [second_task_id]
    assert first_task_id not in {
        task.task_id for task in other_tasks
    }


async def test_only_approved_weekly_plan_is_shown(session):
    employee_id = await seed_employee(
        session,
        "Planlı Çalışan",
        telegram_user_id=5300,
    )
    _, task_id = await seed_task(
        session,
        employee_ids=(employee_id,),
    )
    plan_id = await seed_plan(
        session,
        task_id,
        TODAY,
        date(2026, 11, 22),
        description="Kablo hatlarını döşe",
        percentage=40,
    )

    tasks = await employee_work_service.list_my_tasks(
        session,
        employee_id,
        TODAY,
    )

    assert len(tasks) == 1
    context = tasks[0]
    assert context.has_plan is True
    assert context.plan_conflict is False
    assert context.weekly_plan is not None
    assert context.weekly_plan.id == plan_id
    assert context.weekly_plan.target_description == (
        "Kablo hatlarını döşe"
    )
    assert context.weekly_plan.target_completion_percentage == 40
    assert context.weekly_plan.week_start_date == TODAY
    assert context.weekly_plan.week_end_date == date(2026, 11, 22)


@pytest.mark.parametrize(
    "status",
    ["draft", "rejected", "superseded"],
)
async def test_non_approved_plans_are_hidden(session, status):
    employee_id = await seed_employee(
        session,
        "Planlı Çalışan",
        telegram_user_id=5400,
    )
    _, task_id = await seed_task(
        session,
        employee_ids=(employee_id,),
    )
    await seed_plan(
        session,
        task_id,
        TODAY,
        date(2026, 11, 22),
        status=status,
    )

    tasks = await employee_work_service.list_my_tasks(
        session,
        employee_id,
        TODAY,
    )

    assert len(tasks) == 1
    assert tasks[0].has_plan is False
    assert tasks[0].plan_conflict is False


async def test_task_without_approved_plan_is_still_listed(session):
    employee_id = await seed_employee(
        session,
        "Plansız Çalışan",
        telegram_user_id=5500,
    )
    _, task_id = await seed_task(
        session,
        employee_ids=(employee_id,),
    )

    tasks = await employee_work_service.list_my_tasks(
        session,
        employee_id,
        TODAY,
    )

    assert [task.task_id for task in tasks] == [task_id]
    assert tasks[0].weekly_plan is None
    assert tasks[0].has_plan is False
    assert tasks[0].plan_conflict is False


async def test_conflicting_approved_plans_are_flagged(session):
    employee_id = await seed_employee(
        session,
        "Çakışan Plan",
        telegram_user_id=5600,
    )
    _, task_id = await seed_task(
        session,
        employee_ids=(employee_id,),
    )

    # Two approved plans with different week starts both cover TODAY.
    await seed_plan(
        session,
        task_id,
        date(2026, 11, 9),
        TODAY,
        description="Eski hedef",
        percentage=40,
    )
    await seed_plan(
        session,
        task_id,
        TODAY,
        date(2026, 11, 22),
        description="Yeni hedef",
        percentage=60,
    )

    tasks = await employee_work_service.list_my_tasks(
        session,
        employee_id,
        TODAY,
    )

    assert len(tasks) == 1
    assert tasks[0].plan_conflict is True
    assert tasks[0].weekly_plan is None
    assert tasks[0].has_plan is False

    context = await employee_work_service.get_task_context(
        session,
        employee_id,
        task_id,
        TODAY,
    )
    assert context.plan_conflict is True
    assert context.weekly_plan is None


async def test_get_task_context_rejects_unassigned_task(session):
    owner_id = await seed_employee(
        session,
        "Görev Sahibi",
        telegram_user_id=5700,
    )
    outsider_id = await seed_employee(
        session,
        "Yetkisiz Çalışan",
        telegram_user_id=5701,
    )
    _, task_id = await seed_task(
        session,
        employee_ids=(owner_id,),
    )

    with pytest.raises(NotFoundError):
        await employee_work_service.get_task_context(
            session,
            outsider_id,
            task_id,
            TODAY,
        )


async def test_get_task_context_rejects_unknown_task(session):
    employee_id = await seed_employee(
        session,
        "Çalışan",
        telegram_user_id=5750,
    )

    with pytest.raises(NotFoundError):
        await employee_work_service.get_task_context(
            session,
            employee_id,
            999999,
            TODAY,
        )


async def test_get_task_context_returns_plan_for_assigned_task(session):
    employee_id = await seed_employee(
        session,
        "Yetkili Çalışan",
        telegram_user_id=5800,
    )
    _, task_id = await seed_task(
        session,
        employee_ids=(employee_id,),
    )
    plan_id = await seed_plan(
        session,
        task_id,
        TODAY,
        date(2026, 11, 22),
    )

    context = await employee_work_service.get_task_context(
        session,
        employee_id,
        task_id,
        TODAY,
    )

    assert context.task_id == task_id
    assert context.weekly_plan is not None
    assert context.weekly_plan.id == plan_id


async def test_clipped_week_boundaries_are_inclusive(session):
    employee_id = await seed_employee(
        session,
        "Kırpılmış Hafta",
        telegram_user_id=5900,
    )
    _, task_id = await seed_task(
        session,
        employee_ids=(employee_id,),
        planned_start_date=date(2026, 11, 11),  # Wednesday
        planned_due_date=date(2026, 11, 17),  # Tuesday
    )

    # First week is clipped to the task start.
    await seed_plan(
        session,
        task_id,
        date(2026, 11, 11),
        date(2026, 11, 15),
        description="İlk kısmi hafta",
    )

    inside_start = await employee_work_service.list_my_tasks(
        session,
        employee_id,
        date(2026, 11, 11),
    )
    inside_end = await employee_work_service.list_my_tasks(
        session,
        employee_id,
        date(2026, 11, 15),
    )
    outside_before = await employee_work_service.list_my_tasks(
        session,
        employee_id,
        date(2026, 11, 10),
    )
    outside_after = await employee_work_service.list_my_tasks(
        session,
        employee_id,
        date(2026, 11, 16),
    )

    assert inside_start[0].weekly_plan is not None
    assert inside_end[0].weekly_plan is not None
    assert outside_before[0].weekly_plan is None
    assert outside_after[0].weekly_plan is None


def test_week_contains_uses_inclusive_boundaries():
    plan = WeeklyTaskPlan(
        week_start_date=date(2026, 11, 11),
        week_end_date=date(2026, 11, 15),
        target_description="Kırpılmış hafta",
        status="approved",
        source="manual",
    )

    assert week_contains(plan, date(2026, 11, 11)) is True
    assert week_contains(plan, date(2026, 11, 13)) is True
    assert week_contains(plan, date(2026, 11, 15)) is True
    assert week_contains(plan, date(2026, 11, 10)) is False
    assert week_contains(plan, date(2026, 11, 16)) is False


def test_istanbul_week_boundary():
    # Sunday 15 November 2026 21:30 UTC is Monday 16 November 00:30
    # in Istanbul and therefore belongs to the next Monday-based week.
    utc_moment = datetime(
        2026,
        11,
        15,
        21,
        30,
        tzinfo=timezone.utc,
    )

    assert istanbul_today(utc_moment) == date(2026, 11, 16)
    assert monday_of(istanbul_today(utc_moment)) == date(2026, 11, 16)

    naive_moment = datetime(2026, 11, 15, 21, 30)
    assert istanbul_today(naive_moment) == date(2026, 11, 16)


def test_monday_of_returns_week_start():
    assert monday_of(date(2026, 11, 16)) == date(2026, 11, 16)
    assert monday_of(date(2026, 11, 18)) == date(2026, 11, 16)
    assert monday_of(date(2026, 11, 22)) == date(2026, 11, 16)
