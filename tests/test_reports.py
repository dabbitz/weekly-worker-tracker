from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.database.models import (
    Employee,
    Project,
    Task,
    TaskUpdate,
    WeeklyTaskPlan,
)
from tests.conftest import auth_headers


UTC = timezone.utc
WEEK_START = date(2026, 11, 16)
WEEK_END = date(2026, 11, 22)


async def make_employee(session, full_name: str) -> Employee:
    employee = Employee(full_name=full_name)
    session.add(employee)
    await session.flush()
    return employee


async def make_task(
    session,
    *,
    project_name: str = "Rapor Projesi",
    task_title: str = "Elektrik tesisatı",
    task_description: str | None = None,
) -> tuple[Task, Project]:
    project = Project(name=project_name)
    session.add(project)
    await session.flush()

    task = Task(
        project_id=project.id,
        title=task_title,
        description=task_description,
    )
    session.add(task)
    await session.flush()
    return task, project


async def make_plan(
    session,
    task: Task,
    *,
    status: str = "approved",
    description: str = "Haftalık hedef",
    percentage: int | None = 60,
) -> WeeklyTaskPlan:
    plan = WeeklyTaskPlan(
        task_id=task.id,
        week_start_date=WEEK_START,
        week_end_date=WEEK_END,
        target_description=description,
        target_completion_percentage=percentage,
        status=status,
        source="manual",
    )
    session.add(plan)
    await session.flush()
    return plan


async def add_update(
    session,
    *,
    message_id: int,
    received_at: datetime,
    employee: Employee | None = None,
    task: Task | None = None,
    plan: WeeklyTaskPlan | None = None,
    status: str = "in_progress",
    completion_percentage: int | None = 50,
    blocker: str | None = None,
    delay_reason: str | None = None,
    next_step: str | None = None,
    reported_eta_text: str | None = None,
    reported_eta_date: date | None = None,
    summary: str | None = "İş devam ediyor.",
    task_reference_text: str | None = "Elektrik tesisatı",
    ai_model: str | None = "gemini-test-model",
    original_message: str = "Bu hafta işin yarısını tamamladık.",
    review_status: str | None = None,
) -> TaskUpdate:
    if review_status is None:
        review_status = "approved" if employee is not None else "pending"

    reviewed = review_status != "pending"

    update = TaskUpdate(
        task_id=task.id if task is not None else None,
        employee_id=employee.id if employee is not None else None,
        weekly_plan_id=plan.id if plan is not None else None,
        telegram_user_id=900000 + message_id,
        telegram_chat_id=900000 + message_id,
        telegram_message_id=message_id,
        original_message=original_message,
        task_reference_text=task_reference_text,
        status=status,
        completion_percentage=completion_percentage,
        blocker=blocker,
        delay_reason=delay_reason,
        next_step=next_step,
        reported_eta_text=reported_eta_text,
        reported_eta_date=reported_eta_date,
        summary=summary,
        review_status=review_status,
        reviewed_by_employee_id=(
            employee.id if reviewed and employee is not None else None
        ),
        reviewed_at=received_at if reviewed else None,
        ai_model=ai_model,
        received_at=received_at,
    )
    session.add(update)
    await session.commit()
    return update


async def test_reports_require_admin_authentication(client):
    list_response = await client.get("/api/reports")
    detail_response = await client.get("/api/reports/1")

    assert list_response.status_code == 401
    assert detail_response.status_code == 401


async def test_list_reports_returns_real_rows(client, session):
    employee = await make_employee(session, "Zeynep Yılmaz")
    task, project = await make_task(session, task_description="Pano montajı")
    update = await add_update(
        session,
        message_id=1001,
        received_at=datetime(2026, 11, 16, 9, 30, tzinfo=UTC),
        employee=employee,
        task=task,
        status="in_progress",
        completion_percentage=65,
        blocker="Kablo temini",
        delay_reason=None,
    )

    headers = await auth_headers(client)
    response = await client.get("/api/reports", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["pages"] == 1

    item = body["items"][0]
    assert item["id"] == update.id
    assert item["employee_id"] == employee.id
    assert item["employee_name"] == "Zeynep Yılmaz"
    assert item["project_id"] == project.id
    assert item["project_name"] == "Rapor Projesi"
    assert item["task_id"] == task.id
    assert item["task_title"] == "Elektrik tesisatı"
    assert item["completion_percentage"] == 65
    assert item["status"] == "in_progress"
    assert item["has_blocker"] is True
    assert item["has_delay"] is False
    assert item["review_status"] == "approved"
    assert item["weekly_plan_id"] is None
    assert item["has_weekly_plan"] is False
    assert "original_message" not in item

    assert body["stats"] == {
        "total": 1,
        "blocked_count": 0,
        "with_blocker_count": 1,
        "with_delay_count": 0,
        "completed_count": 0,
    }


async def test_detail_preserves_original_message(client, session):
    employee = await make_employee(session, "Ali Demir")
    task, _ = await make_task(session)
    original = (
        "Kablo çekimi tamamlandı.\r\n"
        "Pano bağlantısı yarına kaldı: ĞÜŞİÖÇ ığüşiöç.\n"
        "  Girintili satır korunmalı.  "
    )
    update = await add_update(
        session,
        message_id=1002,
        received_at=datetime(2026, 11, 16, 10, 0, tzinfo=UTC),
        employee=employee,
        task=task,
        original_message=original,
    )

    headers = await auth_headers(client)
    response = await client.get(
        f"/api/reports/{update.id}",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["original_message"] == original


async def test_detail_maps_all_ai_fields(client, session):
    employee = await make_employee(session, "Mehmet Kaya")
    task, _ = await make_task(session)
    update = await add_update(
        session,
        message_id=1003,
        received_at=datetime(2026, 11, 16, 11, 0, tzinfo=UTC),
        employee=employee,
        task=task,
        status="blocked",
        completion_percentage=35,
        blocker="Kablo temini",
        delay_reason="Tedarik gecikmesi",
        next_step="Kablolar gelince devam et",
        reported_eta_text="cuma gününe kadar",
        reported_eta_date=date(2026, 11, 18),
        summary="Pano bağlantıları kablo bekliyor.",
        task_reference_text="Ana pano bağlantıları",
        ai_model="gemini-test-model",
    )

    headers = await auth_headers(client)
    body = (
        await client.get(
            f"/api/reports/{update.id}",
            headers=headers,
        )
    ).json()

    assert body["task_reference_text"] == "Ana pano bağlantıları"
    assert body["status"] == "blocked"
    assert body["completion_percentage"] == 35
    assert body["blocker"] == "Kablo temini"
    assert body["delay_reason"] == "Tedarik gecikmesi"
    assert body["next_step"] == "Kablolar gelince devam et"
    assert body["reported_eta_text"] == "cuma gününe kadar"
    assert body["reported_eta_date"] == "2026-11-18"
    assert body["reported_eta_weekday"] == "çarşamba"
    assert body["summary"] == "Pano bağlantıları kablo bekliyor."
    assert body["ai_model"] == "gemini-test-model"


async def test_detail_includes_employee_project_and_task(client, session):
    employee = await make_employee(session, "Ayşe Çelik")
    task, project = await make_task(
        session,
        project_name="Konut Projesi",
        task_title="Sıva işleri",
        task_description="İç cephe sıvası",
    )
    update = await add_update(
        session,
        message_id=1004,
        received_at=datetime(2026, 11, 16, 12, 0, tzinfo=UTC),
        employee=employee,
        task=task,
    )

    headers = await auth_headers(client)
    body = (
        await client.get(
            f"/api/reports/{update.id}",
            headers=headers,
        )
    ).json()

    assert body["employee_name"] == "Ayşe Çelik"
    assert body["project_id"] == project.id
    assert body["project_name"] == "Konut Projesi"
    assert body["task_id"] == task.id
    assert body["task_title"] == "Sıva işleri"
    assert body["task_description"] == "İç cephe sıvası"


async def test_detail_returns_weekly_plan_information(client, session):
    employee = await make_employee(session, "Fatma Şahin")
    task, _ = await make_task(session)
    plan = await make_plan(
        session,
        task,
        description="Hafta sonunda %80'e ulaş",
        percentage=80,
    )
    update = await add_update(
        session,
        message_id=1005,
        received_at=datetime(2026, 11, 16, 13, 0, tzinfo=UTC),
        employee=employee,
        task=task,
        plan=plan,
    )

    headers = await auth_headers(client)
    body = (
        await client.get(
            f"/api/reports/{update.id}",
            headers=headers,
        )
    ).json()

    assert body["weekly_plan_id"] == plan.id
    assert body["has_weekly_plan"] is True
    assert body["weekly_plan"] == {
        "id": plan.id,
        "target_description": "Hafta sonunda %80'e ulaş",
        "target_completion_percentage": 80,
        "week_start_date": "2026-11-16",
        "week_end_date": "2026-11-22",
        "status": "approved",
    }


async def test_detail_without_weekly_plan_is_valid(client, session):
    employee = await make_employee(session, "Burak Öz")
    task, _ = await make_task(session)
    update = await add_update(
        session,
        message_id=1006,
        received_at=datetime(2026, 11, 16, 14, 0, tzinfo=UTC),
        employee=employee,
        task=task,
    )

    headers = await auth_headers(client)
    response = await client.get(
        f"/api/reports/{update.id}",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["weekly_plan_id"] is None
    assert body["has_weekly_plan"] is False
    assert body["weekly_plan"] is None


async def test_missing_relations_are_returned_safely(client, session):
    update = await add_update(
        session,
        message_id=1007,
        received_at=datetime(2026, 11, 16, 15, 0, tzinfo=UTC),
        review_status="pending",
    )

    headers = await auth_headers(client)
    response = await client.get(
        f"/api/reports/{update.id}",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["employee_id"] is None
    assert body["employee_name"] is None
    assert body["project_id"] is None
    assert body["project_name"] is None
    assert body["task_id"] is None
    assert body["task_title"] is None
    assert body["task_description"] is None
    assert body["weekly_plan_id"] is None
    assert body["weekly_plan"] is None
    assert body["review_status"] == "pending"
    assert body["reviewed_at"] is None
    assert body["reviewed_by_employee_id"] is None
    assert body["reviewed_by_employee_name"] is None


async def test_deleted_task_and_plan_are_returned_safely(
    client,
    session,
):
    employee = await make_employee(session, "Deleted Relations")
    task, _ = await make_task(session)
    plan = await make_plan(session, task)
    update = await add_update(
        session,
        message_id=1008,
        received_at=datetime(2026, 11, 16, 16, 0, tzinfo=UTC),
        employee=employee,
        task=task,
        plan=plan,
    )

    await session.execute(delete(Task).where(Task.id == task.id))
    await session.commit()

    headers = await auth_headers(client)
    response = await client.get(
        f"/api/reports/{update.id}",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] is None
    assert body["task_title"] is None
    assert body["project_id"] is None
    assert body["project_name"] is None
    assert body["weekly_plan_id"] is None
    assert body["weekly_plan"] is None
    assert body["employee_name"] == "Deleted Relations"


async def test_date_filters_use_istanbul_day_boundaries(client, session):
    employee = await make_employee(session, "Tarih Çalışanı")
    task, _ = await make_task(session)

    before_midnight = await add_update(
        session,
        message_id=1101,
        received_at=datetime(2026, 11, 15, 20, 30, tzinfo=UTC),
        employee=employee,
        task=task,
    )
    after_midnight = await add_update(
        session,
        message_id=1102,
        received_at=datetime(2026, 11, 15, 21, 30, tzinfo=UTC),
        employee=employee,
        task=task,
    )
    before_end = await add_update(
        session,
        message_id=1103,
        received_at=datetime(2026, 11, 16, 20, 59, tzinfo=UTC),
        employee=employee,
        task=task,
    )
    after_end = await add_update(
        session,
        message_id=1104,
        received_at=datetime(2026, 11, 16, 21, 0, tzinfo=UTC),
        employee=employee,
        task=task,
    )

    headers = await auth_headers(client)

    response = await client.get(
        "/api/reports",
        headers=headers,
        params={
            "date_from": "2026-11-16",
            "date_to": "2026-11-16",
        },
    )

    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()["items"]}
    assert ids == {after_midnight.id, before_end.id}
    assert before_midnight.id not in ids
    assert after_end.id not in ids

    only_end = await client.get(
        "/api/reports",
        headers=headers,
        params={"date_to": "2026-11-15"},
    )
    assert [item["id"] for item in only_end.json()["items"]] == [
        before_midnight.id
    ]

    only_start = await client.get(
        "/api/reports",
        headers=headers,
        params={"date_from": "2026-11-16"},
    )
    assert {item["id"] for item in only_start.json()["items"]} == {
        after_midnight.id,
        before_end.id,
        after_end.id,
    }


async def test_invalid_date_range_is_rejected(client):
    headers = await auth_headers(client)

    response = await client.get(
        "/api/reports",
        headers=headers,
        params={
            "date_from": "2026-11-20",
            "date_to": "2026-11-10",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Başlangıç tarihi, bitiş tarihinden sonra olamaz."
    )


async def test_project_employee_task_and_status_filters(client, session):
    first_employee = await make_employee(session, "Birinci Çalışan")
    second_employee = await make_employee(session, "İkinci Çalışan")
    first_task, first_project = await make_task(
        session,
        project_name="Proje A",
        task_title="Görev A",
    )
    second_task, second_project = await make_task(
        session,
        project_name="Proje B",
        task_title="Görev B",
    )

    first = await add_update(
        session,
        message_id=1201,
        received_at=datetime(2026, 11, 16, 9, 0, tzinfo=UTC),
        employee=first_employee,
        task=first_task,
        status="blocked",
        blocker="Kablo yok",
    )
    second = await add_update(
        session,
        message_id=1202,
        received_at=datetime(2026, 11, 16, 10, 0, tzinfo=UTC),
        employee=second_employee,
        task=second_task,
        status="completed",
        delay_reason="Hava koşulları",
    )

    headers = await auth_headers(client)

    async def ids_for(params):
        response = await client.get(
            "/api/reports",
            headers=headers,
            params=params,
        )
        assert response.status_code == 200, response.text
        return {item["id"] for item in response.json()["items"]}

    assert await ids_for({"project_id": first_project.id}) == {
        first.id
    }
    assert await ids_for({"employee_id": second_employee.id}) == {
        second.id
    }
    assert await ids_for({"task_id": first_task.id}) == {first.id}
    assert await ids_for({"status": "blocked"}) == {first.id}
    assert await ids_for({"status": "completed"}) == {second.id}
    assert await ids_for({"has_blocker": "true"}) == {first.id}
    assert await ids_for({"has_delay": "true"}) == {second.id}
    assert await ids_for({"has_blocker": "false"}) == {second.id}
    assert await ids_for({"has_delay": "false"}) == {first.id}
    assert await ids_for(
        {
            "project_id": second_project.id,
            "employee_id": second_employee.id,
            "status": "completed",
        }
    ) == {second.id}
    assert await ids_for(
        {
            "project_id": second_project.id,
            "status": "blocked",
        }
    ) == set()


async def test_pagination_and_total_count(client, session):
    employee = await make_employee(session, "Sayfalama Çalışanı")
    task, _ = await make_task(session)
    updates = []

    for index in range(5):
        updates.append(
            await add_update(
                session,
                message_id=1300 + index,
                received_at=datetime(
                    2026,
                    11,
                    16,
                    8,
                    index,
                    tzinfo=UTC,
                ),
                employee=employee,
                task=task,
            )
        )

    headers = await auth_headers(client)

    first_page = await client.get(
        "/api/reports",
        headers=headers,
        params={"page": 1, "page_size": 2},
    )
    second_page = await client.get(
        "/api/reports",
        headers=headers,
        params={"page": 2, "page_size": 2},
    )
    third_page = await client.get(
        "/api/reports",
        headers=headers,
        params={"page": 3, "page_size": 2},
    )

    first_body = first_page.json()
    assert first_body["total"] == 5
    assert first_body["pages"] == 3
    assert first_body["page"] == 1
    assert [item["id"] for item in first_body["items"]] == [
        updates[4].id,
        updates[3].id,
    ]
    assert [item["id"] for item in second_page.json()["items"]] == [
        updates[2].id,
        updates[1].id,
    ]
    assert [item["id"] for item in third_page.json()["items"]] == [
        updates[0].id
    ]
    assert first_body["stats"]["total"] == 5


async def test_ordering_is_deterministic_for_equal_timestamps(
    client,
    session,
):
    employee = await make_employee(session, "Sıralama Çalışanı")
    task, _ = await make_task(session)
    received_at = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)

    first = await add_update(
        session,
        message_id=1401,
        received_at=received_at,
        employee=employee,
        task=task,
    )
    second = await add_update(
        session,
        message_id=1402,
        received_at=received_at,
        employee=employee,
        task=task,
    )

    headers = await auth_headers(client)
    response = await client.get("/api/reports", headers=headers)

    ids = [item["id"] for item in response.json()["items"]]
    assert ids == [second.id, first.id]


async def test_stats_separate_blocked_status_from_blocker_text(
    client,
    session,
):
    employee = await make_employee(session, "İstatistik Çalışanı")
    task, _ = await make_task(session)
    received_at = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)

    await add_update(
        session,
        message_id=1501,
        received_at=received_at,
        employee=employee,
        task=task,
        status="blocked",
    )
    await add_update(
        session,
        message_id=1502,
        received_at=received_at,
        employee=employee,
        task=task,
        status="in_progress",
        blocker="Kablo temini",
        delay_reason="Tedarik gecikmesi",
    )
    await add_update(
        session,
        message_id=1503,
        received_at=received_at,
        employee=employee,
        task=task,
        status="in_progress",
        delay_reason="Hava koşulları",
    )
    await add_update(
        session,
        message_id=1504,
        received_at=received_at,
        employee=employee,
        task=task,
        status="completed",
    )
    await add_update(
        session,
        message_id=1505,
        received_at=received_at,
        employee=employee,
        task=task,
        status="completed",
        blocker="Ekipman arızası",
        delay_reason="Yedek parça",
    )

    headers = await auth_headers(client)
    response = await client.get("/api/reports", headers=headers)

    stats = response.json()["stats"]
    assert stats == {
        "total": 5,
        "blocked_count": 1,
        "with_blocker_count": 2,
        "with_delay_count": 3,
        "completed_count": 2,
    }

    filtered = await client.get(
        "/api/reports",
        headers=headers,
        params={"status": "blocked"},
    )

    filtered_stats = filtered.json()["stats"]
    assert filtered_stats == {
        "total": 1,
        "blocked_count": 1,
        "with_blocker_count": 0,
        "with_delay_count": 0,
        "completed_count": 0,
    }


async def test_review_status_represents_employee_approval(
    client,
    session,
):
    employee = await make_employee(session, "Onaylayan Çalışan")
    task, _ = await make_task(session)
    reviewed_at = datetime(2026, 11, 16, 13, 0, tzinfo=UTC)

    approved = await add_update(
        session,
        message_id=1601,
        received_at=reviewed_at,
        employee=employee,
        task=task,
    )
    pending = await add_update(
        session,
        message_id=1602,
        received_at=reviewed_at,
        employee=employee,
        task=task,
        review_status="pending",
    )

    headers = await auth_headers(client)

    approved_body = (
        await client.get(
            f"/api/reports/{approved.id}",
            headers=headers,
        )
    ).json()
    assert approved_body["review_status"] == "approved"
    assert approved_body["reviewed_by_employee_id"] == employee.id
    assert approved_body["reviewed_by_employee_name"] == (
        "Onaylayan Çalışan"
    )
    assert approved_body["reviewed_at"] is not None
    assert "admin_approved" not in approved_body
    assert "manager_review_status" not in approved_body

    pending_body = (
        await client.get(
            f"/api/reports/{pending.id}",
            headers=headers,
        )
    ).json()
    assert pending_body["review_status"] == "pending"
    assert pending_body["reviewed_at"] is None
    assert pending_body["reviewed_by_employee_id"] is None
    assert pending_body["reviewed_by_employee_name"] is None


async def test_unknown_report_returns_not_found(client):
    headers = await auth_headers(client)

    response = await client.get(
        "/api/reports/999999",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Rapor bulunamadı."


async def test_report_endpoints_do_not_modify_records(client, session):
    employee = await make_employee(session, "Salt Okunur Çalışan")
    task, _ = await make_task(session)
    plan = await make_plan(session, task)
    update = await add_update(
        session,
        message_id=1701,
        received_at=datetime(2026, 11, 16, 14, 0, tzinfo=UTC),
        employee=employee,
        task=task,
        plan=plan,
        status="blocked",
        blocker="Bekleyen malzeme",
    )

    await session.rollback()

    def snapshot(rows):
        return [
            (
                row.id,
                row.status,
                row.completion_percentage,
                row.task_id,
                row.employee_id,
                row.weekly_plan_id,
                row.review_status,
                row.blocker,
            )
            for row in rows
        ]

    before_updates = snapshot(
        (
            await session.execute(
                select(TaskUpdate).order_by(TaskUpdate.id)
            )
        ).scalars().all()
    )
    before_plans = [
        (
            row.id,
            row.status,
            row.target_description,
            row.target_completion_percentage,
        )
        for row in (
            await session.execute(
                select(WeeklyTaskPlan).order_by(WeeklyTaskPlan.id)
            )
        ).scalars().all()
    ]

    headers = await auth_headers(client)
    list_response = await client.get("/api/reports", headers=headers)
    detail_response = await client.get(
        f"/api/reports/{update.id}",
        headers=headers,
    )

    assert list_response.status_code == 200
    assert detail_response.status_code == 200

    await session.rollback()

    after_updates = snapshot(
        (
            await session.execute(
                select(TaskUpdate).order_by(TaskUpdate.id)
            )
        ).scalars().all()
    )
    after_plans = [
        (
            row.id,
            row.status,
            row.target_description,
            row.target_completion_percentage,
        )
        for row in (
            await session.execute(
                select(WeeklyTaskPlan).order_by(WeeklyTaskPlan.id)
            )
        ).scalars().all()
    ]

    assert after_updates == before_updates
    assert after_plans == before_plans
