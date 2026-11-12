import json
import logging
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select

from app.database.models import TaskUpdate, WeeklyPlanGeneration
from app.schemas.ai_weekly_plan import (
    AIWeeklyPlanResult,
    AIWeeklyTaskPlan,
    AIWeeklyPlanWeek,
)
from app.services import weekly_plan_service
from app.services.ai_service import (
    AIPlanGenerationError,
    GeneratedWeeklyPlans,
)
from tests.conftest import auth_headers
from tests.test_employees_tasks import create_project, seed_employee


def week(
    start: str,
    end: str,
    description: str,
    percentage: int,
    rationale: str | None = None,
) -> dict:
    return {
        "week_start_date": start,
        "week_end_date": end,
        "target_description": description,
        "target_completion_percentage": percentage,
        "rationale": rationale,
    }


def ai_result(
    *groups: dict,
) -> AIWeeklyPlanResult:
    return AIWeeklyPlanResult.model_validate({"tasks": list(groups)})


def task_group(
    task_id: int,
    weeks: list[dict],
    *,
    assumptions: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict:
    return {
        "task_id": task_id,
        "weeks": weeks,
        "assumptions": assumptions or [],
        "warnings": warnings or [],
    }


def mock_ai(monkeypatch, result: AIWeeklyPlanResult) -> list[int]:
    calls = []

    async def fake(context):
        calls.append(context)
        return GeneratedWeeklyPlans(
            result=result,
            model="gemini-test-model",
        )

    monkeypatch.setattr(
        weekly_plan_service,
        "generate_weekly_plan_drafts",
        fake,
    )

    return calls


async def create_task(
    client,
    headers,
    project_id: int,
    *,
    title: str = "Elektrik tesisatı",
    start: str = "2026-11-09",
    due: str = "2026-11-27",
    employee_ids: list[int] | None = None,
) -> int:
    response = await client.post(
        "/api/tasks",
        headers=headers,
        json={
            "project_id": project_id,
            "title": title,
            "description": "Ana kablo hatları ve pano bağlantıları",
            "planned_start_date": start,
            "planned_due_date": due,
            "employee_ids": employee_ids or [],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_ai_generates_one_week_draft_for_single_task(
    client,
    session,
    monkeypatch,
):
    headers = await auth_headers(client)
    employee_id = await seed_employee(session, "Saha Teknikeri")
    project_id = await create_project(client, headers)
    task_id = await create_task(
        client,
        headers,
        project_id,
        start="2026-11-09",
        due="2026-11-13",
        employee_ids=[employee_id],
    )

    mock_ai(
        monkeypatch,
        ai_result(
            task_group(
                task_id,
                [
                    week(
                        "2026-11-09",
                        "2026-11-13",
                        "Ana kablo hatlarını döşe",
                        40,
                        "İlk hafta altyapıya ayrıldı.",
                    )
                ],
                assumptions=["Malzeme temini zamanında yapılacak."],
                warnings=["Çalışan kapasitesi doğrulanmadı."],
            )
        ),
    )

    response = await client.post(
        "/api/weekly-plans/ai/generate",
        headers=headers,
        json={
            "task_ids": [task_id],
            "extra_instructions": "Altyapıya öncelik ver.",
            "request_id": "single-task-request",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["plan_count"] == 1
    assert body["tasks"] == [task_id]
    plan = body["plans"][0]
    assert plan["status"] == "draft"
    assert plan["source"] == "ai"
    assert plan["generation_id"] == body["generation_id"]
    assert plan["generation_request_id"] == "single-task-request"
    assert plan["target_completion_percentage"] == 40
    assert plan["ai_rationale"] == "İlk hafta altyapıya ayrıldı."
    assert "Malzeme" in plan["ai_assumptions"]
    assert "kapasitesi" in plan["ai_warnings"]

    listed = await client.get(
        "/api/weekly-plans",
        headers=headers,
        params={
            "task_id": task_id,
            "status": "draft",
            "source": "ai",
        },
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


async def test_ai_generates_multiple_cumulative_weeks(
    client,
    session,
    monkeypatch,
):
    headers = await auth_headers(client)
    project_id = await create_project(client, headers)
    task_id = await create_task(client, headers, project_id)

    mock_ai(
        monkeypatch,
        ai_result(
            task_group(
                task_id,
                [
                    week("2026-11-09", "2026-11-15", "Kablo hatları", 35),
                    week("2026-11-16", "2026-11-22", "Pano bağlantıları", 70),
                    week("2026-11-23", "2026-11-27", "Son kontroller", 100),
                ]
            )
        ),
    )

    response = await client.post(
        "/api/weekly-plans/ai/generate",
        headers=headers,
        json={
            "task_ids": [task_id],
            "request_id": "multi-week-request",
        },
    )

    assert response.status_code == 201, response.text
    plans = response.json()["plans"]
    assert [plan["target_completion_percentage"] for plan in plans] == [
        35,
        70,
        100,
    ]
    assert [plan["week_start_date"] for plan in plans] == [
        "2026-11-09",
        "2026-11-16",
        "2026-11-23",
    ]


async def test_ai_generates_plans_for_multiple_tasks(
    client,
    session,
    monkeypatch,
):
    headers = await auth_headers(client)
    project_id = await create_project(client, headers)
    first_task_id = await create_task(
        client,
        headers,
        project_id,
        title="Elektrik",
        start="2026-11-09",
        due="2026-11-13",
    )
    second_task_id = await create_task(
        client,
        headers,
        project_id,
        title="Su tesisatı",
        start="2026-11-09",
        due="2026-11-13",
    )

    mock_ai(
        monkeypatch,
        ai_result(
            task_group(
                first_task_id,
                [week("2026-11-09", "2026-11-13", "Elektrik hedefi", 50)],
            ),
            task_group(
                second_task_id,
                [week("2026-11-09", "2026-11-13", "Tesisat hedefi", 30)],
            ),
        ),
    )

    response = await client.post(
        "/api/weekly-plans/ai/generate",
        headers=headers,
        json={
            "task_ids": [first_task_id, second_task_id],
            "request_id": "multi-task-request",
        },
    )

    assert response.status_code == 201, response.text
    plans = response.json()["plans"]
    assert len(plans) == 2
    assert {plan["task_id"] for plan in plans} == {
        first_task_id,
        second_task_id,
    }


async def test_ai_output_schema_rejects_invalid_percentage():
    with pytest.raises(PydanticValidationError):
        AIWeeklyPlanResult.model_validate(
            {
                "tasks": [
                    {
                        "task_id": 1,
                        "weeks": [
                            week(
                                "2026-11-09",
                                "2026-11-13",
                                "Hedef",
                                140,
                            )
                        ],
                    }
                ]
            }
        )


def constructed_result(percentage: int) -> AIWeeklyPlanResult:
    week_model = AIWeeklyPlanWeek.model_construct(
        week_start_date="2026-11-09",
        week_end_date="2026-11-13",
        target_description="Hedef",
        target_completion_percentage=percentage,
        rationale=None,
    )
    group = AIWeeklyTaskPlan.model_construct(
        task_id=1,
        assumptions=[],
        warnings=[],
        weeks=[week_model],
    )
    return AIWeeklyPlanResult.model_construct(tasks=[group])


async def test_ai_rejects_invalid_dates_and_saves_nothing(
    client,
    session,
    monkeypatch,
):
    headers = await auth_headers(client)
    project_id = await create_project(client, headers)
    task_id = await create_task(
        client,
        headers,
        project_id,
        start="2026-11-09",
        due="2026-11-13",
    )

    mock_ai(
        monkeypatch,
        ai_result(
            task_group(
                task_id,
                [week("2026-11-13", "2026-11-09", "Hatalı hafta", 40)],
            )
        ),
    )

    response = await client.post(
        "/api/weekly-plans/ai/generate",
        headers=headers,
        json={
            "task_ids": [task_id],
            "request_id": "invalid-date-request",
        },
    )

    assert response.status_code == 503
    listed = await client.get(
        "/api/weekly-plans",
        headers=headers,
        params={"task_id": task_id},
    )
    assert listed.json()["total"] == 0

    generation = await session.scalar(
        select(WeeklyPlanGeneration).where(
            WeeklyPlanGeneration.request_id == "invalid-date-request"
        )
    )
    assert generation is not None
    assert generation.status == "failed"


async def test_ai_rejects_percentage_outside_range(
    client,
    session,
    monkeypatch,
):
    headers = await auth_headers(client)
    project_id = await create_project(client, headers)
    task_id = await create_task(
        client,
        headers,
        project_id,
        start="2026-11-09",
        due="2026-11-13",
    )

    # Bypass the AI schema once to prove the backend validates it again.
    invalid = constructed_result(120)
    invalid.tasks[0].task_id = task_id
    mock_ai(monkeypatch, invalid)

    response = await client.post(
        "/api/weekly-plans/ai/generate",
        headers=headers,
        json={
            "task_ids": [task_id],
            "request_id": "invalid-percentage-request",
        },
    )

    assert response.status_code == 503
    listed = await client.get(
        "/api/weekly-plans",
        headers=headers,
        params={"task_id": task_id},
    )
    assert listed.json()["total"] == 0


async def test_ai_rejects_decreasing_cumulative_progress(
    client,
    session,
    monkeypatch,
):
    headers = await auth_headers(client)
    project_id = await create_project(client, headers)
    task_id = await create_task(client, headers, project_id)

    mock_ai(
        monkeypatch,
        ai_result(
            task_group(
                task_id,
                [
                    week("2026-11-09", "2026-11-15", "Birinci", 60),
                    week("2026-11-16", "2026-11-22", "İkinci", 40),
                ],
            )
        ),
    )

    response = await client.post(
        "/api/weekly-plans/ai/generate",
        headers=headers,
        json={
            "task_ids": [task_id],
            "request_id": "decreasing-request",
        },
    )

    assert response.status_code == 503
    listed = await client.get(
        "/api/weekly-plans",
        headers=headers,
        params={"task_id": task_id},
    )
    assert listed.json()["total"] == 0


async def test_ai_request_is_idempotent_with_same_request_id(
    client,
    session,
    monkeypatch,
):
    headers = await auth_headers(client)
    project_id = await create_project(client, headers)
    task_id = await create_task(
        client,
        headers,
        project_id,
        start="2026-11-09",
        due="2026-11-13",
    )

    calls = mock_ai(
        monkeypatch,
        ai_result(
            task_group(
                task_id,
                [week("2026-11-09", "2026-11-13", "Hedef", 50)],
            )
        ),
    )

    payload = {
        "task_ids": [task_id],
        "request_id": "idempotent-request",
    }

    first = await client.post(
        "/api/weekly-plans/ai/generate",
        headers=headers,
        json=payload,
    )
    second = await client.post(
        "/api/weekly-plans/ai/generate",
        headers=headers,
        json=payload,
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["generation_id"] == second.json()["generation_id"]
    assert len(calls) == 1

    listed = await client.get(
        "/api/weekly-plans",
        headers=headers,
        params={"task_id": task_id},
    )
    assert listed.json()["total"] == 1


async def test_manual_plan_edit_approve_reject_and_delete(client):
    headers = await auth_headers(client)
    project_id = await create_project(client, headers)
    task_id = await create_task(
        client,
        headers,
        project_id,
        start="2026-11-09",
        due="2026-11-13",
    )

    created = await client.post(
        "/api/weekly-plans",
        headers=headers,
        json={
            "task_id": task_id,
            "week_start_date": "2026-11-09",
            "week_end_date": "2026-11-13",
            "target_description": "Manuel hedef",
            "target_completion_percentage": 30,
        },
    )
    assert created.status_code == 201, created.text
    plan = created.json()
    assert plan["source"] == "manual"
    assert plan["status"] == "draft"

    edited = await client.patch(
        f"/api/weekly-plans/{plan['id']}",
        headers=headers,
        json={
            "target_description": "Güncellenmiş manuel hedef",
            "target_completion_percentage": 45,
        },
    )
    assert edited.status_code == 200
    assert edited.json()["target_completion_percentage"] == 45

    rejected = await client.post(
        f"/api/weekly-plans/{plan['id']}/reject",
        headers=headers,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    second = await client.post(
        "/api/weekly-plans",
        headers=headers,
        json={
            "task_id": task_id,
            "week_start_date": "2026-11-09",
            "week_end_date": "2026-11-13",
            "target_description": "Onaylanacak hedef",
            "target_completion_percentage": 55,
        },
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["id"]

    approved = await client.post(
        f"/api/weekly-plans/{second_id}/approve",
        headers=headers,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_at"] is not None

    deleted = await client.delete(
        f"/api/weekly-plans/{plan['id']}",
        headers=headers,
    )
    assert deleted.status_code == 204


async def test_approved_plan_cannot_be_deleted(client):
    headers = await auth_headers(client)
    project_id = await create_project(client, headers)
    task_id = await create_task(
        client,
        headers,
        project_id,
        start="2026-11-09",
        due="2026-11-13",
    )

    created = await client.post(
        "/api/weekly-plans",
        headers=headers,
        json={
            "task_id": task_id,
            "week_start_date": "2026-11-09",
            "week_end_date": "2026-11-13",
            "target_description": "Resmî hedef",
            "target_completion_percentage": 100,
        },
    )
    plan_id = created.json()["id"]

    approved = await client.post(
        f"/api/weekly-plans/{plan_id}/approve",
        headers=headers,
    )
    assert approved.status_code == 200

    deleted = await client.delete(
        f"/api/weekly-plans/{plan_id}",
        headers=headers,
    )
    assert deleted.status_code == 409

    detail = await client.get(
        f"/api/weekly-plans/{plan_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "approved"


async def test_only_one_approved_plan_per_task_week(
    client,
    session,
    monkeypatch,
):
    headers = await auth_headers(client)
    project_id = await create_project(client, headers)
    task_id = await create_task(
        client,
        headers,
        project_id,
        start="2026-11-09",
        due="2026-11-13",
    )

    mock_ai(
        monkeypatch,
        ai_result(
            task_group(
                task_id,
                [week("2026-11-09", "2026-11-13", "İlk AI hedefi", 60)],
            )
        ),
    )

    first_generation = await client.post(
        "/api/weekly-plans/ai/generate",
        headers=headers,
        json={
            "task_ids": [task_id],
            "request_id": "approval-request-1",
        },
    )
    first_plan_id = first_generation.json()["plans"][0]["id"]

    first_approval = await client.post(
        f"/api/weekly-plans/{first_plan_id}/approve",
        headers=headers,
    )
    assert first_approval.status_code == 200

    second_generation = await client.post(
        "/api/weekly-plans/ai/generate",
        headers=headers,
        json={
            "task_ids": [task_id],
            "request_id": "approval-request-2",
        },
    )
    second_plan_id = second_generation.json()["plans"][0]["id"]

    conflict = await client.post(
        f"/api/weekly-plans/{second_plan_id}/approve",
        headers=headers,
    )
    assert conflict.status_code == 409

    replaced = await client.post(
        f"/api/weekly-plans/{second_plan_id}/approve",
        headers=headers,
        json={"replace_existing": True},
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["status"] == "approved"

    old_plan = await client.get(
        f"/api/weekly-plans/{first_plan_id}",
        headers=headers,
    )
    assert old_plan.status_code == 200
    assert old_plan.json()["status"] == "superseded"

    approved_only = await client.get(
        "/api/weekly-plans",
        headers=headers,
        params={"task_id": task_id, "status": "approved"},
    )
    assert approved_only.json()["total"] == 1


async def test_plan_with_task_update_history_is_preserved(
    client,
    session,
):
    headers = await auth_headers(client)
    employee_id = await seed_employee(
        session,
        "Geçmiş Çalışan",
        telegram_user_id=321,
    )
    project_id = await create_project(client, headers)
    task_id = await create_task(
        client,
        headers,
        project_id,
        start="2026-11-09",
        due="2026-11-13",
        employee_ids=[employee_id],
    )

    created = await client.post(
        "/api/weekly-plans",
        headers=headers,
        json={
            "task_id": task_id,
            "week_start_date": "2026-11-09",
            "week_end_date": "2026-11-13",
            "target_description": "Geçmiş korunacak hedef",
            "target_completion_percentage": 70,
        },
    )
    plan_id = created.json()["id"]

    update = TaskUpdate(
        task_id=task_id,
        weekly_plan_id=plan_id,
        employee_id=employee_id,
        telegram_user_id=321,
        telegram_chat_id=321,
        telegram_message_id=987654,
        original_message="İş %70 tamamlandı.",
        status="in_progress",
        review_status="pending",
        received_at=datetime.now(timezone.utc),
    )
    session.add(update)
    await session.commit()

    deleted = await client.delete(
        f"/api/weekly-plans/{plan_id}",
        headers=headers,
    )
    assert deleted.status_code == 409

    stored_update = await session.get(TaskUpdate, update.id)
    assert stored_update is not None
    assert stored_update.weekly_plan_id == plan_id


async def test_ai_generation_failure_saves_no_partial_plans(
    client,
    session,
    monkeypatch,
):
    headers = await auth_headers(client)
    project_id = await create_project(client, headers)
    task_id = await create_task(
        client,
        headers,
        project_id,
        start="2026-11-09",
        due="2026-11-13",
    )
    calls = {"count": 0}

    async def failing(context):
        calls["count"] += 1
        raise AIPlanGenerationError("simulated AI outage")

    monkeypatch.setattr(
        weekly_plan_service,
        "generate_weekly_plan_drafts",
        failing,
    )

    response = await client.post(
        "/api/weekly-plans/ai/generate",
        headers=headers,
        json={
            "task_ids": [task_id],
            "request_id": "failed-ai-request",
        },
    )
    assert response.status_code == 503

    listed = await client.get(
        "/api/weekly-plans",
        headers=headers,
        params={"task_id": task_id},
    )
    assert listed.json()["total"] == 0

    generation = await session.scalar(
        select(WeeklyPlanGeneration).where(
            WeeklyPlanGeneration.request_id == "failed-ai-request"
        )
    )
    assert generation is not None
    assert generation.status == "failed"

    # A failed generation can be retried with the same idempotency key.
    async def succeeding(context):
        calls["count"] += 1
        return GeneratedWeeklyPlans(
            result=ai_result(
                task_group(
                    task_id,
                    [
                        week(
                            "2026-11-09",
                            "2026-11-13",
                            "Yeniden deneme hedefi",
                            50,
                        )
                    ],
                )
            ),
            model="gemini-test-model",
        )

    monkeypatch.setattr(
        weekly_plan_service,
        "generate_weekly_plan_drafts",
        succeeding,
    )

    retried = await client.post(
        "/api/weekly-plans/ai/generate",
        headers=headers,
        json={
            "task_ids": [task_id],
            "request_id": "failed-ai-request",
        },
    )
    assert retried.status_code == 201, retried.text
    assert retried.json()["plan_count"] == 1
    assert calls["count"] == 2


async def test_ai_requires_task_dates(client):
    headers = await auth_headers(client)
    project_id = await create_project(client, headers)
    task_id = await create_task(
        client,
        headers,
        project_id,
        start=None,
        due=None,
    )

    response = await client.post(
        "/api/weekly-plans/ai/generate",
        headers=headers,
        json={
            "task_ids": [task_id],
            "request_id": "missing-dates-request",
        },
    )
    assert response.status_code == 422
    assert "tarihleri" in response.json()["detail"]


async def test_ai_endpoints_require_authentication(client):
    response = await client.post(
        "/api/weekly-plans/ai/generate",
        json={
            "task_ids": [1],
            "request_id": "unauthenticated-request",
        },
    )
    assert response.status_code == 401

    approve = await client.post("/api/weekly-plans/1/approve")
    assert approve.status_code == 401

    reject = await client.post("/api/weekly-plans/1/reject")
    assert reject.status_code == 401

    delete = await client.delete("/api/weekly-plans/1")
    assert delete.status_code == 401


def test_ai_plan_schema_is_compatible_with_gemini_sdk():
    """Regression: unsupported JSON Schema keywords must not reach Gemini.

    ``task_id`` previously used ``gt=0``, which Pydantic emits as
    ``exclusiveMinimum``. The Gemini SDK's ``Schema`` model does not
    accept that keyword, so request building raised a Pydantic
    ``ValidationError`` before any Gemini call was made.
    """

    from google.genai import _transformers as genai_transformers

    json_schema = json.dumps(AIWeeklyPlanResult.model_json_schema())
    assert "exclusiveMinimum" not in json_schema
    assert "exclusiveMaximum" not in json_schema

    gemini_schema = genai_transformers.t_schema(
        None,
        AIWeeklyPlanResult,
    )

    assert gemini_schema is not None
    task_id_schema = (
        gemini_schema.properties["tasks"]
        .items.properties["task_id"]
    )
    assert task_id_schema.minimum == 1
    assert task_id_schema.type.value == "INTEGER"


async def test_pydantic_error_is_logged_without_request_data(
    client,
    session,
    monkeypatch,
    caplog,
):
    headers = await auth_headers(client)
    project_id = await create_project(client, headers)
    task_id = await create_task(
        client,
        headers,
        project_id,
        start="2026-11-09",
        due="2026-11-13",
    )

    secret_marker = "GIZLI-ADMIN-TALIMATI"

    async def failing(context):
        # Mirrors a schema failure raised while the SDK builds the
        # request: Pydantic includes the rejected input in the error.
        AIWeeklyPlanResult.model_validate(
            {"tasks": [{"task_id": 0, "weeks": []}]}
        )

    monkeypatch.setattr(
        weekly_plan_service,
        "generate_weekly_plan_drafts",
        failing,
    )

    caplog.set_level(
        logging.WARNING,
        logger="worktrack.weekly_plans",
    )

    response = await client.post(
        "/api/weekly-plans/ai/generate",
        headers=headers,
        json={
            "task_ids": [task_id],
            "extra_instructions": secret_marker,
            "request_id": "pydantic-failure-request",
        },
    )

    assert response.status_code == 503
    assert secret_marker not in response.text

    generation = await session.scalar(
        select(WeeklyPlanGeneration).where(
            WeeklyPlanGeneration.request_id
            == "pydantic-failure-request"
        )
    )
    assert generation is not None
    assert generation.status == "failed"

    log_text = caplog.text
    assert "Pydantic validation failed" in log_text
    assert "tasks.0.task_id" in log_text
    assert "greater_than_equal" in log_text
    assert secret_marker not in log_text
    # Neither the rejected value nor Pydantic's docs URL is logged.
    assert "input_value" not in log_text
    assert "errors.pydantic.dev" not in log_text


async def test_unexpected_ai_error_logs_safe_traceback(
    client,
    session,
    monkeypatch,
    caplog,
):
    headers = await auth_headers(client)
    project_id = await create_project(client, headers)
    task_id = await create_task(
        client,
        headers,
        project_id,
        start="2026-11-09",
        due="2026-11-13",
    )

    async def failing(context):
        raise RuntimeError("simulated unexpected failure")

    monkeypatch.setattr(
        weekly_plan_service,
        "generate_weekly_plan_drafts",
        failing,
    )

    caplog.set_level(
        logging.WARNING,
        logger="worktrack.weekly_plans",
    )

    response = await client.post(
        "/api/weekly-plans/ai/generate",
        headers=headers,
        json={
            "task_ids": [task_id],
            "request_id": "unexpected-failure-request",
        },
    )

    assert response.status_code == 503
    assert "simulated unexpected failure" not in response.text

    records = [
        record
        for record in caplog.records
        if record.name == "worktrack.weekly_plans"
        and "Unexpected AI weekly plan error" in record.getMessage()
    ]
    assert records, caplog.text
    assert records[0].exc_info is not None
