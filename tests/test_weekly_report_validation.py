import json
from datetime import date

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.ai_weekly_report import (
    AIEmployeeAnalysis,
    AIManagerIntervention,
    AIProjectAnalysis,
    AIProjectMapResult,
    AIReportItem,
    AITaskAssessment,
    AIWeeklyManagerReport,
)
from app.services.weekly_report_metrics import build_weekly_metrics
from app.services.weekly_report_validation import (
    WeeklyReportValidationError,
    validate_project_map_result,
    validate_weekly_manager_report,
)
from tests.test_weekly_report_metrics import (
    AFTER_WEEK,
    WEEK_START,
    add_employee,
    add_plan,
    add_project,
    add_task,
    add_update,
    assign,
    at,
)


async def seeded_metrics(session, *, today: date = AFTER_WEEK):
    project = await add_project(session, "Validasyon Projesi")
    employee = await add_employee(session, "Test Çalışanı")
    task = await add_task(session, project, title="Validasyon görevi")
    await assign(session, task, employee)
    await add_plan(session, task, target=80)
    await add_update(
        session,
        task=task,
        employee=employee,
        received_at=at(date(2026, 11, 3), 10),
        completion=60,
    )
    await session.commit()
    return await build_weekly_metrics(session, WEEK_START, today=today)


def valid_report(metrics) -> AIWeeklyManagerReport:
    task_token = next(iter(metrics.task_classifications))
    project_token = next(iter(metrics.references["projects"]))
    employee_token = next(iter(metrics.references["employees"]))
    classification = metrics.task_classifications[task_token]

    return AIWeeklyManagerReport(
        general_summary=(
            "Hafta kaynak kayıtlarıyla değerlendirildi."
        ),
        general_highlights=[
            AIReportItem(
                text="Genel görünüm kaynaklarla değerlendirildi.",
                source_tokens=[project_token, task_token],
            )
        ],
        general_issues=[],
        project_analyses=[
            AIProjectAnalysis(
                project_token=project_token,
                summary="Proje kapsamında değerlendirme.",
                highlights=[
                    AIReportItem(
                        text="Proje kaydı incelendi.",
                        source_tokens=[project_token],
                    )
                ],
                risks=[],
            )
        ],
        employee_analyses=[
            AIEmployeeAnalysis(
                employee_token=employee_token,
                summary="Çalışan faaliyeti değerlendirildi.",
                observations=[
                    AIReportItem(
                        text="Faaliyet kaydı incelendi.",
                        source_tokens=[employee_token],
                    )
                ],
            )
        ],
        task_assessments=[
            AITaskAssessment(
                task_token=task_token,
                assessment="Görev kaydı değerlendirildi.",
                classification=classification,
                source_tokens=[task_token],
            )
        ],
        unmet_work_analysis=[],
        history_comparison=[],
        recommendations=[],
        data_quality_notes=[],
        manager_interventions=[],
        partial_week_note=(
            "Kısmi değerlendirme: hafta henüz tamamlanmadı."
            if metrics.is_partial_week
            else None
        ),
    )


async def test_valid_report_passes(session):
    metrics = await seeded_metrics(session)

    validate_weekly_manager_report(valid_report(metrics), metrics)


async def test_unknown_token_is_rejected(session):
    metrics = await seeded_metrics(session)
    report = valid_report(metrics)
    report.general_highlights[0].source_tokens = ["P99"]

    with pytest.raises(WeeklyReportValidationError):
        validate_weekly_manager_report(report, metrics)


async def test_classification_mismatch_is_rejected(session):
    metrics = await seeded_metrics(session)
    report = valid_report(metrics)
    current = report.task_assessments[0].classification
    report.task_assessments[0].classification = (
        "met" if current != "met" else "no_report"
    )

    with pytest.raises(WeeklyReportValidationError):
        validate_weekly_manager_report(report, metrics)


async def test_invented_number_is_rejected(session):
    metrics = await seeded_metrics(session)
    report = valid_report(metrics)
    report.general_summary = "Bu hafta 999 görev tamamlandı."

    with pytest.raises(WeeklyReportValidationError):
        validate_weekly_manager_report(report, metrics)


async def test_invented_date_is_rejected(session):
    metrics = await seeded_metrics(session)
    report = valid_report(metrics)
    report.general_summary = "Teslim 03.12.2026 tarihinde."

    with pytest.raises(WeeklyReportValidationError):
        validate_weekly_manager_report(report, metrics)


async def test_employee_name_is_rejected(session):
    metrics = await seeded_metrics(session)
    report = valid_report(metrics)
    report.general_summary = "Test Çalışanı iyi bir hafta geçirdi."

    with pytest.raises(WeeklyReportValidationError):
        validate_weekly_manager_report(report, metrics)


async def test_banned_phrase_is_rejected(session):
    metrics = await seeded_metrics(session)
    report = valid_report(metrics)
    report.general_summary = "Görev Yapılmadı."

    with pytest.raises(WeeklyReportValidationError):
        validate_weekly_manager_report(report, metrics)


async def test_partial_week_requires_label(session):
    metrics = await seeded_metrics(
        session,
        today=date(2026, 11, 4),
    )
    assert metrics.is_partial_week is True

    report = valid_report(metrics)
    report.partial_week_note = None

    with pytest.raises(WeeklyReportValidationError):
        validate_weekly_manager_report(report, metrics)

    report.partial_week_note = "Kısmi değerlendirme: hafta sürüyor."
    validate_weekly_manager_report(report, metrics)


async def test_intervention_without_source_is_rejected(session):
    metrics = await seeded_metrics(session)
    report = valid_report(metrics)
    project_token = next(iter(metrics.references["projects"]))

    invalid = AIManagerIntervention.model_construct(
        title="Müdahale",
        problem="Kanıtsız sorun",
        affected_project_tokens=[project_token],
        affected_task_tokens=[],
        source_tokens=[],
        priority="high",
        recommended_action="Aksiyon alınmalı.",
    )
    report.manager_interventions = [invalid]

    with pytest.raises(WeeklyReportValidationError):
        validate_weekly_manager_report(report, metrics)


async def test_more_than_eight_interventions_are_rejected(session):
    metrics = await seeded_metrics(session)
    project_token = next(iter(metrics.references["projects"]))
    intervention = AIManagerIntervention(
        title="Müdahale",
        problem="Sorun",
        affected_project_tokens=[project_token],
        affected_task_tokens=[],
        source_tokens=[project_token],
        priority="medium",
        recommended_action="Aksiyon alınmalı.",
    )

    with pytest.raises(PydanticValidationError):
        AIWeeklyManagerReport(
            general_summary="Özet.",
            manager_interventions=[intervention] * 9,
        )


async def test_project_map_validation(session):
    metrics = await seeded_metrics(session)
    task_token = next(iter(metrics.task_classifications))
    project_token = next(iter(metrics.references["projects"]))
    classification = metrics.task_classifications[task_token]

    result = AIProjectMapResult(
        project_token=project_token,
        summary="Proje kapsamında değerlendirme.",
        highlights=[
            AIReportItem(
                text="Proje kaydı incelendi.",
                source_tokens=[project_token],
            )
        ],
        risks=[],
        task_assessments=[
            AITaskAssessment(
                task_token=task_token,
                assessment="Görev kaydı değerlendirildi.",
                classification=classification,
                source_tokens=[task_token],
            )
        ],
        interventions=[],
    )

    validate_project_map_result(
        result,
        metrics,
        project_token=project_token,
    )

    with pytest.raises(WeeklyReportValidationError):
        validate_project_map_result(
            result,
            metrics,
            project_token="P99",
        )

    result.task_assessments[0].classification = (
        "met" if classification != "met" else "no_report"
    )

    with pytest.raises(WeeklyReportValidationError):
        validate_project_map_result(
            result,
            metrics,
            project_token=project_token,
        )


def test_weekly_report_schemas_are_gemini_compatible():
    from google.genai import _transformers as genai_transformers

    for schema in (AIWeeklyManagerReport, AIProjectMapResult):
        json_schema = json.dumps(schema.model_json_schema())
        assert "exclusiveMinimum" not in json_schema
        assert "exclusiveMaximum" not in json_schema
        assert genai_transformers.t_schema(None, schema) is not None
