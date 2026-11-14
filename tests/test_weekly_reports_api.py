import asyncio
import json
from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select

from app.database.models import (
    Employee,
    Project,
    Task,
    TaskAssignment,
    TaskUpdate,
    WeeklyManagerReport,
)
from app.schemas.ai_weekly_report import (
    AIEmployeeAnalysis,
    AIProjectAnalysis,
    AIProjectMapResult,
    AIReportItem,
    AITaskAssessment,
    AIWeeklyManagerReport,
)
from app.services import weekly_report_service
from app.services.ai_service import (
    GeneratedWeeklyManagerReport,
    WeeklyReportGenerationError,
)
from app.services.week_utils import istanbul_today, monday_of
from tests.conftest import auth_headers
from tests.test_weekly_report_metrics import (
    add_employee,
    add_plan,
    add_project,
    add_task,
    add_update,
    assign,
    at,
)


TODAY = istanbul_today()
CURRENT_WEEK_START = monday_of(TODAY)
LAST_WEEK_START = CURRENT_WEEK_START - timedelta(days=7)
LAST_WEEK_END = LAST_WEEK_START + timedelta(days=6)


def request_id() -> str:
    return f"req-{uuid4().hex}"


def make_valid_report(payload: dict) -> AIWeeklyManagerReport:
    tasks = payload.get("tasks", [])
    projects = payload.get("projects", [])
    employees = payload.get("employees", [])
    sources: list[str] = []

    if projects:
        sources.append(projects[0]["token"])
    if tasks:
        sources.append(tasks[0]["token"])
    if employees:
        sources.append(employees[0]["token"])

    highlights = (
        [
            AIReportItem(
                text=(
                    "Haftanın genel görünümü kaynak kayıtlarıyla "
                    "birlikte değerlendirildi."
                ),
                source_tokens=sources,
            )
        ]
        if sources
        else []
    )

    return AIWeeklyManagerReport(
        general_summary=(
            "Seçilen hafta için kaynak kayıtlarına dayalı genel "
            "değerlendirme."
        ),
        general_highlights=highlights,
        general_issues=[],
        project_analyses=[
            AIProjectAnalysis(
                project_token=project["token"],
                summary="Proje kapsamında değerlendirme.",
                highlights=[
                    AIReportItem(
                        text="Proje kaydı incelendi.",
                        source_tokens=[project["token"]],
                    )
                ],
                risks=[],
            )
            for project in projects
        ],
        employee_analyses=[
            AIEmployeeAnalysis(
                employee_token=employee["token"],
                summary="Çalışan faaliyet kaydı incelendi.",
                observations=[
                    AIReportItem(
                        text="Faaliyet kaydı mevcut.",
                        source_tokens=[employee["token"]],
                    )
                ],
            )
            for employee in employees
        ],
        task_assessments=[
            AITaskAssessment(
                task_token=task["token"],
                assessment="Görev kaydı değerlendirildi.",
                classification=task["classification"],
                source_tokens=[task["token"]],
            )
            for task in tasks
        ],
        unmet_work_analysis=[],
        history_comparison=[],
        recommendations=[],
        data_quality_notes=[],
        manager_interventions=[],
        partial_week_note=(
            "Kısmi değerlendirme: hafta henüz tamamlanmadı."
            if payload["week"]["is_partial_week"]
            else None
        ),
    )


async def seed_week(session, week_start: date, *, completion: int = 60):
    week_end = week_start + timedelta(days=6)
    project = await add_project(session, "Test Projesi")
    employee = await add_employee(session, "Test Çalışanı")
    task = await add_task(
        session,
        project,
        title="Test görevi",
        start=week_start - timedelta(days=3),
        due=week_end + timedelta(days=7),
    )
    await assign(session, task, employee)
    await add_plan(
        session,
        task,
        week_start=week_start,
        week_end=week_end,
        target=80,
        approved_at=at(week_start, 9),
    )
    update = await add_update(
        session,
        task=task,
        employee=employee,
        received_at=at(week_start + timedelta(days=1), 10),
        completion=completion,
    )
    await session.commit()
    return project, employee, task, update


def patch_single_success(monkeypatch):
    calls = {"count": 0}

    async def fake(payload):
        calls["count"] += 1
        return GeneratedWeeklyManagerReport(
            result=make_valid_report(payload),
            model="gemini-test",
        )

    monkeypatch.setattr(
        weekly_report_service,
        "generate_weekly_manager_report_single",
        fake,
    )
    return calls


def patch_single_failure(monkeypatch):
    calls = {"count": 0}

    async def fake(payload):
        calls["count"] += 1
        raise WeeklyReportGenerationError("provider down")

    monkeypatch.setattr(
        weekly_report_service,
        "generate_weekly_manager_report_single",
        fake,
    )
    return calls


async def test_periods_requires_auth_and_returns_backend_periods(client):
    unauthorized = await client.get("/api/weekly-reports/periods")
    assert unauthorized.status_code == 401

    headers = await auth_headers(client)
    response = await client.get(
        "/api/weekly-reports/periods",
        headers=headers,
        params={"weeks": 3},
    )

    assert response.status_code == 200
    body = response.json()
    starts = [item["week_start_date"] for item in body["periods"]]

    assert body["default_week_start_date"] == (
        LAST_WEEK_START.isoformat()
    )
    assert body["current_week_start_date"] == (
        CURRENT_WEEK_START.isoformat()
    )
    assert LAST_WEEK_START.isoformat() in starts
    assert CURRENT_WEEK_START.isoformat() in starts

    default = next(
        item
        for item in body["periods"]
        if item["is_default"]
    )
    assert default["is_completed"] is True

    current = next(
        item
        for item in body["periods"]
        if item["is_current_week"]
    )
    assert current["is_partial_week"] is True


async def test_preview_uses_real_counts_without_ai(
    client,
    session,
    monkeypatch,
):
    await seed_week(session, LAST_WEEK_START)

    async def forbidden(payload):  # pragma: no cover - must not run
        raise AssertionError("preview must not call the AI")

    monkeypatch.setattr(
        weekly_report_service,
        "generate_weekly_manager_report_single",
        forbidden,
    )

    headers = await auth_headers(client)
    response = await client.get(
        "/api/weekly-reports/preview",
        headers=headers,
        params={
            "week_start_date": LAST_WEEK_START.isoformat()
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["project_count"] == 1
    assert body["task_count"] == 1
    assert body["plan_count"] == 1
    assert body["report_count"] == 1
    assert body["has_data"] is True
    assert body["is_partial_week"] is False
    assert body["projects"][0]["name"] == "Test Projesi"


async def test_preview_rejects_future_and_non_monday(client):
    headers = await auth_headers(client)

    future = CURRENT_WEEK_START + timedelta(days=7)
    future_response = await client.get(
        "/api/weekly-reports/preview",
        headers=headers,
        params={"week_start_date": future.isoformat()},
    )
    assert future_response.status_code == 422

    not_monday = CURRENT_WEEK_START + timedelta(days=1)
    monday_response = await client.get(
        "/api/weekly-reports/preview",
        headers=headers,
        params={"week_start_date": not_monday.isoformat()},
    )
    assert monday_response.status_code == 422


async def test_create_report_completes_and_persists(
    client,
    session,
    monkeypatch,
):
    await seed_week(session, LAST_WEEK_START)
    calls = patch_single_success(monkeypatch)

    headers = await auth_headers(client)
    response = await client.post(
        "/api/weekly-reports",
        headers=headers,
        json={
            "week_start_date": LAST_WEEK_START.isoformat(),
            "request_id": request_id(),
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["status"] == "completed"
    assert body["version"] == 1
    assert body["model"] == "gemini-test"
    assert body["narrative"] is not None
    assert body["narrative"]["source"] == "ai"
    assert body["narrative_view"]["source"] == "ai"
    assert body["metrics_snapshot"]["summary"]["report_count"] == 1
    assert body["references"]["projects"]["P1"]["label"] == (
        "Test Projesi"
    )
    assert isinstance(body["intervention_candidates"], list)
    assert calls["count"] == 1

    stored = await session.get(WeeklyManagerReport, body["id"])
    assert stored is not None
    assert stored.status == "completed"
    assert stored.narrative["source"] == "ai"
    assert stored.metrics_snapshot["summary"]["task_count"] == 1


async def test_idempotent_request_returns_existing_without_ai(
    client,
    session,
    monkeypatch,
):
    await seed_week(session, LAST_WEEK_START)
    calls = patch_single_success(monkeypatch)

    headers = await auth_headers(client)
    payload = {
        "week_start_date": LAST_WEEK_START.isoformat(),
        "request_id": request_id(),
        "extra_instructions": "Riskli işlere odaklan.",
    }

    first = await client.post(
        "/api/weekly-reports",
        headers=headers,
        json=payload,
    )
    second = await client.post(
        "/api/weekly-reports",
        headers=headers,
        json=payload,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert calls["count"] == 1


async def test_same_request_id_different_content_conflicts(
    client,
    session,
    monkeypatch,
):
    await seed_week(session, LAST_WEEK_START)
    patch_single_success(monkeypatch)

    headers = await auth_headers(client)
    payload = {
        "week_start_date": LAST_WEEK_START.isoformat(),
        "request_id": request_id(),
    }

    first = await client.post(
        "/api/weekly-reports",
        headers=headers,
        json=payload,
    )
    assert first.status_code == 201

    conflict = await client.post(
        "/api/weekly-reports",
        headers=headers,
        json={
            **payload,
            "extra_instructions": "Farklı içerik",
        },
    )

    assert conflict.status_code == 409


async def test_new_request_id_creates_new_version(
    client,
    session,
    monkeypatch,
):
    await seed_week(session, LAST_WEEK_START)
    patch_single_success(monkeypatch)

    headers = await auth_headers(client)
    first = await client.post(
        "/api/weekly-reports",
        headers=headers,
        json={
            "week_start_date": LAST_WEEK_START.isoformat(),
            "request_id": request_id(),
        },
    )
    second = await client.post(
        "/api/weekly-reports",
        headers=headers,
        json={
            "week_start_date": LAST_WEEK_START.isoformat(),
            "request_id": request_id(),
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["version"] == 1
    assert second.json()["version"] == 2
    assert first.json()["id"] != second.json()["id"]

    first_detail = await client.get(
        f"/api/weekly-reports/{first.json()['id']}",
        headers=headers,
    )
    assert first_detail.status_code == 200
    assert first_detail.json()["version"] == 1


async def test_failed_generation_and_retry_reuse_version(
    client,
    session,
    monkeypatch,
):
    await seed_week(session, LAST_WEEK_START)
    failing = patch_single_failure(monkeypatch)

    headers = await auth_headers(client)
    payload = {
        "week_start_date": LAST_WEEK_START.isoformat(),
        "request_id": request_id(),
    }

    failed = await client.post(
        "/api/weekly-reports",
        headers=headers,
        json=payload,
    )

    assert failed.status_code == 503
    assert failing["count"] == 1
    assert "postgres" not in failed.text.casefold()

    listing = await client.get(
        "/api/weekly-reports",
        headers=headers,
    )
    item = listing.json()["items"][0]

    assert item["status"] == "failed"
    assert item["has_narrative"] is False
    assert item["version"] == 1

    patch_single_success(monkeypatch)

    retried = await client.post(
        f"/api/weekly-reports/{item['id']}/retry",
        headers=headers,
    )

    assert retried.status_code == 200, retried.text
    body = retried.json()

    assert body["id"] == item["id"]
    assert body["version"] == 1
    assert body["status"] == "completed"
    assert body["narrative"] is not None

    retry_completed = await client.post(
        f"/api/weekly-reports/{item['id']}/retry",
        headers=headers,
    )
    assert retry_completed.status_code == 409


async def test_validation_failure_stores_no_narrative(
    client,
    session,
    monkeypatch,
):
    await seed_week(session, LAST_WEEK_START)

    async def invalid(payload):
        report = make_valid_report(payload)
        report.general_summary = "Bilinmeyen kaynak P99 kullanıldı."
        report.general_highlights = [
            AIReportItem(
                text="Bilinmeyen kaynak P99.",
                source_tokens=["P99"],
            )
        ]
        return GeneratedWeeklyManagerReport(
            result=report,
            model="gemini-test",
        )

    monkeypatch.setattr(
        weekly_report_service,
        "generate_weekly_manager_report_single",
        invalid,
    )

    headers = await auth_headers(client)
    response = await client.post(
        "/api/weekly-reports",
        headers=headers,
        json={
            "week_start_date": LAST_WEEK_START.isoformat(),
            "request_id": request_id(),
        },
    )

    assert response.status_code == 503

    stored = (
        await session.execute(
            select(WeeklyManagerReport).order_by(
                WeeklyManagerReport.id.desc()
            )
        )
    ).scalars().first()

    assert stored is not None
    assert stored.status == "failed"
    assert stored.narrative is None


async def test_empty_week_does_not_call_ai(client, monkeypatch):
    async def forbidden(payload):  # pragma: no cover - must not run
        raise AssertionError("empty week must not call the AI")

    monkeypatch.setattr(
        weekly_report_service,
        "generate_weekly_manager_report_single",
        forbidden,
    )

    headers = await auth_headers(client)
    empty_week = LAST_WEEK_START - timedelta(days=35)
    response = await client.post(
        "/api/weekly-reports",
        headers=headers,
        json={
            "week_start_date": empty_week.isoformat(),
            "request_id": request_id(),
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["status"] == "completed"
    assert body["model"] == "deterministic-empty"
    assert body["narrative"]["source"] == "deterministic_empty"
    assert body["narrative_view"]["source"] == "deterministic_empty"
    assert body["metrics_snapshot"]["summary"]["task_count"] == 0


async def test_current_partial_week_is_labelled(
    client,
    session,
    monkeypatch,
):
    await seed_week(session, CURRENT_WEEK_START)
    patch_single_success(monkeypatch)

    headers = await auth_headers(client)
    response = await client.post(
        "/api/weekly-reports",
        headers=headers,
        json={
            "week_start_date": CURRENT_WEEK_START.isoformat(),
            "request_id": request_id(),
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["is_partial_week"] is True
    assert body["narrative"]["partial_week_note"]
    assert "Kısmi değerlendirme" in (
        body["narrative"]["partial_week_note"]
    )
    assert body["narrative_view"]["partial_week_note"]


async def test_stale_pending_is_failed_and_reused(
    client,
    session,
    monkeypatch,
):
    patch_single_success(monkeypatch)

    week_start = LAST_WEEK_START
    rid = request_id()
    fingerprint = weekly_report_service._fingerprint(week_start, None)

    stale = WeeklyManagerReport(
        week_start_date=week_start,
        week_end_date=week_start + timedelta(days=6),
        version=1,
        status="pending",
        request_id=rid,
        request_fingerprint=fingerprint,
        is_partial_week=False,
        metrics_snapshot={},
        data_quality=[],
        references={},
        created_at=at(week_start, 9) - timedelta(days=3),
    )
    session.add(stale)
    await session.commit()
    stale_id = stale.id

    headers = await auth_headers(client)
    response = await client.post(
        "/api/weekly-reports",
        headers=headers,
        json={
            "week_start_date": week_start.isoformat(),
            "request_id": rid,
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["id"] == stale_id
    assert body["version"] == 1
    assert body["status"] == "completed"


async def test_fresh_pending_blocks_duplicate_generation(
    client,
    session,
    monkeypatch,
):
    patch_single_success(monkeypatch)

    rid = request_id()
    pending = WeeklyManagerReport(
        week_start_date=LAST_WEEK_START,
        week_end_date=LAST_WEEK_END,
        version=1,
        status="pending",
        request_id=rid,
        request_fingerprint=weekly_report_service._fingerprint(
            LAST_WEEK_START,
            None,
        ),
        is_partial_week=False,
        metrics_snapshot={},
        data_quality=[],
        references={},
    )
    session.add(pending)
    await session.commit()

    headers = await auth_headers(client)
    response = await client.post(
        "/api/weekly-reports",
        headers=headers,
        json={
            "week_start_date": LAST_WEEK_START.isoformat(),
            "request_id": rid,
        },
    )

    assert response.status_code == 409


async def test_delete_removes_only_the_report_document(
    client,
    session,
    monkeypatch,
):
    await seed_week(session, LAST_WEEK_START)
    patch_single_success(monkeypatch)

    headers = await auth_headers(client)
    created = await client.post(
        "/api/weekly-reports",
        headers=headers,
        json={
            "week_start_date": LAST_WEEK_START.isoformat(),
            "request_id": request_id(),
        },
    )
    assert created.status_code == 201

    report_id = created.json()["id"]
    response = await client.delete(
        f"/api/weekly-reports/{report_id}",
        headers=headers,
    )
    assert response.status_code == 204

    missing = await client.get(
        f"/api/weekly-reports/{report_id}",
        headers=headers,
    )
    assert missing.status_code == 404

    task_count = (
        await session.execute(select(func.count(Task.id)))
    ).scalar_one()
    update_count = (
        await session.execute(select(func.count(TaskUpdate.id)))
    ).scalar_one()

    assert task_count == 1
    assert update_count == 1

    pending = WeeklyManagerReport(
        week_start_date=LAST_WEEK_START,
        week_end_date=LAST_WEEK_END,
        version=2,
        status="pending",
        request_id=request_id(),
        request_fingerprint="x" * 64,
        is_partial_week=False,
        metrics_snapshot={},
        data_quality=[],
        references={},
    )
    session.add(pending)
    await session.commit()

    blocked = await client.delete(
        f"/api/weekly-reports/{pending.id}",
        headers=headers,
    )
    assert blocked.status_code == 409


async def test_stored_report_survives_source_deletion(
    client,
    session,
    monkeypatch,
):
    project, employee, task, update = await seed_week(
        session,
        LAST_WEEK_START,
    )
    patch_single_success(monkeypatch)

    headers = await auth_headers(client)
    created = await client.post(
        "/api/weekly-reports",
        headers=headers,
        json={
            "week_start_date": LAST_WEEK_START.isoformat(),
            "request_id": request_id(),
        },
    )
    assert created.status_code == 201
    report_id = created.json()["id"]

    await session.execute(
        delete(TaskUpdate).where(TaskUpdate.id == update.id)
    )
    await session.execute(
        delete(TaskAssignment).where(
            TaskAssignment.task_id == task.id
        )
    )
    await session.delete(task)
    await session.delete(employee)
    await session.delete(project)
    await session.commit()

    detail = await client.get(
        f"/api/weekly-reports/{report_id}",
        headers=headers,
    )

    assert detail.status_code == 200, detail.text
    body = detail.json()

    assert body["references"]["projects"]["P1"]["label"] == (
        "Test Projesi"
    )
    assert body["narrative_view"] is not None
    assert body["metrics_snapshot"]["summary"]["report_count"] == 1


async def test_ai_payload_privacy_on_real_request(
    client,
    session,
    monkeypatch,
):
    captured: dict = {}

    async def capture(payload):
        captured["payload"] = payload
        return GeneratedWeeklyManagerReport(
            result=make_valid_report(payload),
            model="gemini-test",
        )

    monkeypatch.setattr(
        weekly_report_service,
        "generate_weekly_manager_report_single",
        capture,
    )

    project = await add_project(session, "Gizli Proje")
    employee = await add_employee(
        session,
        "Gizli Çalışan",
        telegram_user_id=123456789,
    )
    task = await add_task(session, project, title="Gizli görev")
    await assign(session, task, employee)
    await add_update(
        session,
        task=task,
        employee=employee,
        received_at=at(LAST_WEEK_START + timedelta(days=1), 10),
        completion=40,
        summary="Ham mesaj özeti",
    )
    await session.commit()

    headers = await auth_headers(client)
    response = await client.post(
        "/api/weekly-reports",
        headers=headers,
        json={
            "week_start_date": LAST_WEEK_START.isoformat(),
            "request_id": request_id(),
        },
    )

    assert response.status_code == 201, response.text

    serialized = json.dumps(
        captured["payload"],
        ensure_ascii=False,
    )

    assert "Gizli Çalışan" not in serialized
    assert "123456789" not in serialized
    assert "gizli ham mesaj" not in serialized.casefold()
    assert "original_message" not in serialized
    assert "Ham mesaj özeti" in serialized


async def test_large_week_uses_project_map_reduce(
    client,
    session,
    monkeypatch,
):
    monkeypatch.setenv("WEEKLY_REPORT_PROMPT_CHAR_BUDGET", "5000")

    for project_index in range(2):
        project = await add_project(
            session,
            f"Büyük Proje {project_index}",
        )

        for task_index in range(12):
            task = await add_task(
                session,
                project,
                title=f"Görev {project_index}-{task_index}",
                start=LAST_WEEK_START - timedelta(days=2),
                due=LAST_WEEK_END + timedelta(days=5),
                description="Uzun açıklama " * 30,
            )
            await add_plan(
                session,
                task,
                week_start=LAST_WEEK_START,
                week_end=LAST_WEEK_END,
                target=80,
            )

    await session.commit()

    map_calls: list[str] = []
    synthesis_calls = {"count": 0}

    async def fake_single(payload):  # pragma: no cover - must not run
        raise AssertionError("large week must not use a single call")

    async def fake_map(payload):
        map_calls.append(payload["project_token"])
        tasks = payload["tasks"]

        return GeneratedWeeklyManagerReport(
            result=AIProjectMapResult(
                project_token=payload["project_token"],
                summary="Proje kapsamında değerlendirme.",
                highlights=[
                    AIReportItem(
                        text="Proje kaydı incelendi.",
                        source_tokens=[payload["project_token"]],
                    )
                ],
                risks=[],
                task_assessments=[
                    AITaskAssessment(
                        task_token=task["token"],
                        assessment="Görev kaydı değerlendirildi.",
                        classification=task["classification"],
                        source_tokens=[task["token"]],
                    )
                    for task in tasks
                ],
                interventions=[],
            ),
            model="gemini-map",
        )

    async def fake_synthesis(payload):
        synthesis_calls["count"] += 1
        project_results = payload["project_results"]
        task_assessments = []
        project_analyses = []

        for project_result in project_results:
            project_analyses.append(
                AIProjectAnalysis(
                    project_token=project_result["project_token"],
                    summary=project_result["summary"],
                    highlights=[
                        AIReportItem(
                            text="Proje kaydı incelendi.",
                            source_tokens=[
                                project_result["project_token"]
                            ],
                        )
                    ],
                    risks=[],
                )
            )

            for assessment in project_result["task_assessments"]:
                task_assessments.append(
                    AITaskAssessment(**assessment)
                )

        employee_analyses = [
            AIEmployeeAnalysis(
                employee_token=employee["token"],
                summary="Çalışan faaliyet kaydı incelendi.",
                observations=[],
            )
            for employee in payload.get("employees", [])
        ]

        return GeneratedWeeklyManagerReport(
            result=AIWeeklyManagerReport(
                general_summary=(
                    "Seçilen hafta için proje bazlı değerlendirme."
                ),
                general_highlights=[
                    AIReportItem(
                        text="Proje sonuçları birleştirildi.",
                        source_tokens=[
                            project_analyses[0].project_token
                        ],
                    )
                ],
                general_issues=[],
                project_analyses=project_analyses,
                employee_analyses=employee_analyses,
                task_assessments=task_assessments,
                unmet_work_analysis=[],
                history_comparison=[],
                recommendations=[],
                data_quality_notes=[],
                manager_interventions=[],
                partial_week_note=None,
            ),
            model="gemini-synthesis",
        )

    monkeypatch.setattr(
        weekly_report_service,
        "generate_weekly_manager_report_single",
        fake_single,
    )
    monkeypatch.setattr(
        weekly_report_service,
        "generate_weekly_manager_report_map",
        fake_map,
    )
    monkeypatch.setattr(
        weekly_report_service,
        "generate_weekly_manager_report_synthesis",
        fake_synthesis,
    )

    headers = await auth_headers(client)
    response = await client.post(
        "/api/weekly-reports",
        headers=headers,
        json={
            "week_start_date": LAST_WEEK_START.isoformat(),
            "request_id": request_id(),
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["status"] == "completed"
    assert body["model"] == "gemini-synthesis"
    assert len(map_calls) == 2
    assert synthesis_calls["count"] == 1


async def test_concurrent_same_request_id_generates_once(
    database,
    monkeypatch,
):
    rid = request_id()
    calls = {"count": 0}

    async with database.sessionmaker() as seed_session:
        await seed_week(seed_session, LAST_WEEK_START)

    async def slow(payload):
        calls["count"] += 1
        await asyncio.sleep(0.3)
        return GeneratedWeeklyManagerReport(
            result=make_valid_report(payload),
            model="gemini-test",
        )

    monkeypatch.setattr(
        weekly_report_service,
        "generate_weekly_manager_report_single",
        slow,
    )

    from app.schemas.weekly_report import WeeklyReportCreate

    payload = WeeklyReportCreate(
        week_start_date=LAST_WEEK_START,
        request_id=rid,
    )

    async def run_once():
        async with database.sessionmaker() as db_session:
            return await weekly_report_service.create_report(
                db_session,
                payload,
            )

    results = await asyncio.gather(
        run_once(),
        run_once(),
        return_exceptions=True,
    )

    successes = [
        result
        for result in results
        if not isinstance(result, Exception)
    ]
    conflicts = [
        result
        for result in results
        if isinstance(result, Exception)
    ]

    assert calls["count"] == 1
    assert len(successes) >= 1
    assert len(successes) + len(conflicts) == 2

    async with database.sessionmaker() as db_session:
        rows = (
            await db_session.execute(
                select(WeeklyManagerReport).where(
                    WeeklyManagerReport.request_id == rid
                )
            )
        ).scalars().all()

    assert len(rows) == 1
    assert rows[0].status == "completed"


async def test_unauthenticated_cannot_access_admin_endpoints(client):
    responses = [
        await client.get("/api/weekly-reports"),
        await client.get("/api/weekly-reports/1"),
        await client.get("/api/weekly-reports/preview"),
        await client.post(
            "/api/weekly-reports",
            json={
                "week_start_date": LAST_WEEK_START.isoformat(),
                "request_id": request_id(),
            },
        ),
        await client.post("/api/weekly-reports/1/retry"),
        await client.delete("/api/weekly-reports/1"),
    ]

    for response in responses:
        assert response.status_code == 401
