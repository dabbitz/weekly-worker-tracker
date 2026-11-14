"""Business logic for stored AI-assisted weekly manager reports.

Lifecycle and safety rules:

* Generation is manual only. There is no scheduler, queue or worker.
* A ``pending`` row is reserved and committed before Gemini is called, so
  no database transaction or connection is held during the AI request.
* The row is moved from ``pending`` to ``completed``/``failed`` with a
  conditional ``UPDATE ... WHERE status = 'pending'``. Concurrent requests
  cannot produce two completed reports for the same row.
* ``request_id`` is idempotent. Same id + same content returns the existing
  report without calling Gemini. Same id + different content is a conflict.
* A new ``request_id`` for the same week creates a new version; older
  versions are preserved.
* A pending row older than ten minutes is marked failed on the next create
  or retry request. Retry reuses the same row and version.
* An empty week never calls Gemini; a deterministic empty document is
  stored as completed.
* Any AI or validation failure stores a failed row without a narrative.

The stored report is self-contained: ``metrics_snapshot`` is the only
source of numbers, and the narrative stores tokens that are resolved
against the stored ``references`` snapshot when the report is read.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import WeeklyManagerReport
from app.schemas.common import Page
from app.schemas.weekly_report import (
    NarrativeBlock,
    NarrativeEmployeeView,
    NarrativeInterventionView,
    NarrativeProjectView,
    NarrativeSegment,
    NarrativeTaskView,
    NarrativeView,
    PreviewProject,
    PreviewWarning,
    WeekPeriod,
    WeeklyManagerReportStatus,
    WeeklyReportCreate,
    WeeklyReportDetail,
    WeeklyReportListItem,
    WeeklyReportListResponse,
    WeeklyReportPeriodsResponse,
    WeeklyReportPreview,
)
from app.services import weekly_report_metrics
from app.services.ai_service import (
    WeeklyReportGenerationError,
    generate_weekly_manager_report_map,
    generate_weekly_manager_report_single,
    generate_weekly_manager_report_synthesis,
)
from app.services.exceptions import (
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from app.services.week_utils import istanbul_today, monday_of
from app.services.weekly_report_metrics import (
    CLASSIFICATION_LABELS,
    WeeklyMetrics,
)
from app.services.weekly_report_validation import (
    WeeklyReportValidationError,
    validate_project_map_result,
    validate_weekly_manager_report,
)


logger = logging.getLogger("worktrack.weekly_reports")

STALE_PENDING_MINUTES = 10
DEFAULT_PROMPT_BUDGET = 40_000
MIN_PROMPT_BUDGET = 5_000
DETERMINISTIC_MODEL = "deterministic-empty"
TOKEN_PATTERN = re.compile(r"\b(?:E|T|P|U|W|WEEK)\d+\b")

SAFE_FAILURE_MESSAGE = (
    "Haftalık yönetici raporu oluşturulamadı. Lütfen tekrar deneyin."
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _prompt_budget() -> int:
    raw = os.getenv("WEEKLY_REPORT_PROMPT_CHAR_BUDGET")

    if not raw:
        return DEFAULT_PROMPT_BUDGET

    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_PROMPT_BUDGET

    return max(value, MIN_PROMPT_BUDGET)


def _period_label(start: date, end: date) -> str:
    return f"{start.strftime('%d.%m.%Y')} – {end.strftime('%d.%m.%Y')}"


def _validate_week_start(week_start_date: date, today: date) -> None:
    if week_start_date.weekday() != 0:
        raise ValidationError(
            "Hafta başlangıcı pazartesi olmalıdır."
        )

    if week_start_date > monday_of(today):
        raise ValidationError(
            "Gelecek haftalar için rapor oluşturulamaz."
        )


def get_periods(
    weeks: int = 12,
    *,
    today: date | None = None,
) -> WeeklyReportPeriodsResponse:
    today_value = today or istanbul_today()
    current_monday = monday_of(today_value)
    default_monday = current_monday - timedelta(days=7)
    count = max(1, min(weeks, 52))

    start_dates = [
        current_monday - timedelta(weeks=index)
        for index in range(count - 1, -1, -1)
    ]

    if default_monday not in start_dates:
        start_dates.append(default_monday)
        start_dates.sort()

    periods: list[WeekPeriod] = []

    for start in start_dates:
        end = start + timedelta(days=6)
        is_current = start == current_monday
        is_partial = today_value <= end

        periods.append(
            WeekPeriod(
                week_start_date=start,
                week_end_date=end,
                label=_period_label(start, end),
                is_current_week=is_current,
                is_partial_week=is_partial,
                is_completed=not is_partial,
                is_future=False,
                is_default=start == default_monday,
            )
        )

    return WeeklyReportPeriodsResponse(
        periods=periods,
        default_week_start_date=default_monday,
        current_week_start_date=current_monday,
    )


async def get_preview(
    session: AsyncSession,
    week_start_date: date,
    *,
    today: date | None = None,
) -> WeeklyReportPreview:
    today_value = today or istanbul_today()
    _validate_week_start(week_start_date, today_value)
    metrics = await weekly_report_metrics.build_weekly_metrics(
        session,
        week_start_date,
        today=today_value,
    )
    snapshot = metrics.snapshot
    summary = snapshot["summary"]

    return WeeklyReportPreview(
        week_start_date=metrics.week_start_date,
        week_end_date=metrics.week_end_date,
        label=_period_label(
            metrics.week_start_date,
            metrics.week_end_date,
        ),
        is_partial_week=metrics.is_partial_week,
        is_current_week=metrics.is_current_week,
        project_count=summary["project_count"],
        task_count=summary["task_count"],
        plan_count=summary["plan_count"],
        report_count=summary["report_count"],
        pending_review_report_count=summary[
            "pending_review_report_count"
        ],
        completed_task_count=summary["completed_task_count"],
        in_progress_task_count=summary["in_progress_task_count"],
        blocked_task_count=summary["blocked_task_count"],
        not_started_task_count=summary["not_started_task_count"],
        no_report_task_count=summary["no_report_task_count"],
        unassigned_task_count=summary["unassigned_task_count"],
        plan_conflict_count=summary["plan_conflict_count"],
        missing_target_percentage_count=summary[
            "missing_target_percentage_count"
        ],
        intervention_candidate_count=len(
            snapshot["intervention_candidates"]
        ),
        has_data=metrics.has_data,
        projects=[
            PreviewProject(
                project_token=project["project_token"],
                name=project["name"],
                task_count=project["task_count"],
                report_count=project["report_count"],
            )
            for project in snapshot["projects"]
        ],
        warnings=[
            PreviewWarning(
                code=item["code"],
                message=item["message"],
            )
            for item in snapshot["data_quality"]
        ],
    )


def _fingerprint(
    week_start_date: date,
    extra_instructions: str | None,
) -> str:
    payload = json.dumps(
        {
            "week_start_date": week_start_date.isoformat(),
            "extra_instructions": (extra_instructions or "").strip(),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _empty_narrative(metrics: WeeklyMetrics) -> dict:
    note = (
        "Kısmi değerlendirme: Seçilen hafta henüz tamamlanmadı."
        if metrics.is_partial_week
        else None
    )

    return {
        "source": "deterministic_empty",
        "general_summary": (
            "Seçilen hafta için değerlendirilecek kayıtlı görev, iş "
            "raporu veya haftalık plan bulunmuyor."
        ),
        "general_highlights": [],
        "general_issues": [],
        "project_analyses": [],
        "employee_analyses": [],
        "task_assessments": [],
        "unmet_work_analysis": [],
        "history_comparison": [],
        "recommendations": [],
        "data_quality_notes": [],
        "manager_interventions": [],
        "partial_week_note": note,
    }


def _list_item(report: WeeklyManagerReport) -> WeeklyReportListItem:
    snapshot = report.metrics_snapshot or {}
    summary = snapshot.get("summary", {})
    candidates = snapshot.get("intervention_candidates", [])

    return WeeklyReportListItem(
        id=report.id,
        week_start_date=report.week_start_date,
        week_end_date=report.week_end_date,
        version=report.version,
        status=WeeklyManagerReportStatus(report.status),
        model=report.model,
        is_partial_week=report.is_partial_week,
        created_at=report.created_at,
        completed_at=report.completed_at,
        error_message=report.error_message,
        has_narrative=bool(report.narrative),
        project_count=int(summary.get("project_count", 0)),
        task_count=int(summary.get("task_count", 0)),
        report_count=int(summary.get("report_count", 0)),
        intervention_count=len(candidates),
    )


def _ref_segment(token: str, references: dict) -> NarrativeSegment:
    mapping = (
        ("projects", "project"),
        ("tasks", "task"),
        ("employees", "employee"),
        ("reports", "report"),
        ("plans", "plan"),
        ("weeks", "week"),
    )

    for key, kind in mapping:
        reference = references.get(key, {}).get(token)

        if reference is None:
            continue

        return NarrativeSegment(
            type="reference",
            token=token,
            kind=kind,
            ref_id=reference.get("id"),
            label=reference.get("label"),
            href=reference.get("href"),
        )

    # Unknown tokens are rendered as plain text; they are never turned
    # into a link.
    return NarrativeSegment(type="text", text=token)


def _segments(text: str | None, references: dict) -> list[NarrativeSegment]:
    value = text or ""
    result: list[NarrativeSegment] = []
    last = 0

    for match in TOKEN_PATTERN.finditer(value):
        if match.start() > last:
            result.append(
                NarrativeSegment(
                    type="text",
                    text=value[last:match.start()],
                )
            )

        result.append(_ref_segment(match.group(0), references))
        last = match.end()

    if last < len(value):
        result.append(
            NarrativeSegment(type="text", text=value[last:])
        )

    if not result:
        result.append(NarrativeSegment(type="text", text=value))

    return result


def _source_segments(
    tokens: list[str] | None,
    references: dict,
) -> list[NarrativeSegment]:
    result: list[NarrativeSegment] = []

    for token in tokens or []:
        segment = _ref_segment(token, references)

        if segment.type == "reference":
            result.append(segment)

    return result


def _block(item: dict, references: dict) -> NarrativeBlock:
    return NarrativeBlock(
        segments=_segments(item.get("text"), references),
        sources=_source_segments(
            item.get("source_tokens"),
            references,
        ),
    )


def _blocks(items: list[dict] | None, references: dict) -> list[NarrativeBlock]:
    return [_block(item, references) for item in items or []]


def render_narrative(
    narrative: dict | None,
    references: dict,
) -> NarrativeView | None:
    """Resolve stored tokens into safe render segments."""

    if not narrative:
        return None

    is_empty = narrative.get("source") == "deterministic_empty"

    project_views = [
        NarrativeProjectView(
            project=_ref_segment(item.get("project_token", ""), references),
            summary=_segments(item.get("summary"), references),
            highlights=_blocks(item.get("highlights"), references),
            risks=_blocks(item.get("risks"), references),
        )
        for item in narrative.get("project_analyses", [])
    ]

    employee_views = [
        NarrativeEmployeeView(
            employee=_ref_segment(
                item.get("employee_token", ""),
                references,
            ),
            summary=_segments(item.get("summary"), references),
            observations=_blocks(
                item.get("observations"),
                references,
            ),
        )
        for item in narrative.get("employee_analyses", [])
    ]

    task_views = []

    for item in narrative.get("task_assessments", []):
        classification = item.get("classification", "")
        task_views.append(
            NarrativeTaskView(
                task=_ref_segment(
                    item.get("task_token", ""),
                    references,
                ),
                assessment=_segments(
                    item.get("assessment"),
                    references,
                ),
                classification=classification,
                classification_label=CLASSIFICATION_LABELS.get(
                    classification,
                    classification,
                ),
                sources=_source_segments(
                    item.get("source_tokens"),
                    references,
                ),
            )
        )

    intervention_views = [
        NarrativeInterventionView(
            title=_segments(item.get("title"), references),
            problem=_segments(item.get("problem"), references),
            recommended_action=_segments(
                item.get("recommended_action"),
                references,
            ),
            priority=item.get("priority", "medium"),
            affected_projects=_source_segments(
                item.get("affected_project_tokens"),
                references,
            ),
            affected_tasks=_source_segments(
                item.get("affected_task_tokens"),
                references,
            ),
            sources=_source_segments(
                item.get("source_tokens"),
                references,
            ),
        )
        for item in narrative.get("manager_interventions", [])
    ]

    note = narrative.get("partial_week_note")

    return NarrativeView(
        source="deterministic_empty" if is_empty else "ai",
        general_summary=_segments(
            narrative.get("general_summary"),
            references,
        ),
        general_highlights=_blocks(
            narrative.get("general_highlights"),
            references,
        ),
        general_issues=_blocks(
            narrative.get("general_issues"),
            references,
        ),
        project_analyses=project_views,
        employee_analyses=employee_views,
        task_assessments=task_views,
        unmet_work_analysis=_blocks(
            narrative.get("unmet_work_analysis"),
            references,
        ),
        history_comparison=_blocks(
            narrative.get("history_comparison"),
            references,
        ),
        recommendations=_blocks(
            narrative.get("recommendations"),
            references,
        ),
        data_quality_notes=_blocks(
            narrative.get("data_quality_notes"),
            references,
        ),
        manager_interventions=intervention_views,
        partial_week_note=(
            _segments(note, references) if note else None
        ),
    )


def _detail(report: WeeklyManagerReport) -> WeeklyReportDetail:
    snapshot = report.metrics_snapshot or {}
    base = _list_item(report)

    return WeeklyReportDetail(
        **base.model_dump(),
        request_id=report.request_id,
        extra_instructions=report.extra_instructions,
        metrics_snapshot=snapshot,
        data_quality=report.data_quality or [],
        narrative=report.narrative,
        narrative_view=render_narrative(
            report.narrative,
            report.references or {},
        ),
        references=report.references or {},
        intervention_candidates=snapshot.get(
            "intervention_candidates",
            [],
        ),
    )


async def _get_by_request_id(
    session: AsyncSession,
    request_id: str,
) -> WeeklyManagerReport | None:
    return (
        await session.execute(
            select(WeeklyManagerReport).where(
                WeeklyManagerReport.request_id == request_id
            )
        )
    ).scalar_one_or_none()


async def _next_version(
    session: AsyncSession,
    week_start_date: date,
) -> int:
    current = (
        await session.execute(
            select(func.max(WeeklyManagerReport.version)).where(
                WeeklyManagerReport.week_start_date
                == week_start_date
            )
        )
    ).scalar_one_or_none()

    return int(current or 0) + 1


async def _mark_stale_pending(
    session: AsyncSession,
    *,
    week_start_date: date | None = None,
    report_id: int | None = None,
) -> None:
    threshold = _now() - timedelta(minutes=STALE_PENDING_MINUTES)
    statement = update(WeeklyManagerReport).where(
        WeeklyManagerReport.status == "pending",
        WeeklyManagerReport.created_at < threshold,
    )

    if week_start_date is not None:
        statement = statement.where(
            WeeklyManagerReport.week_start_date == week_start_date
        )

    if report_id is not None:
        statement = statement.where(
            WeeklyManagerReport.id == report_id
        )

    result = await session.execute(
        statement.values(
            status="failed",
            error_message=(
                "Önceki deneme zaman aşımına uğradı. Rapor yeniden "
                "denenebilir."
            ),
            completed_at=_now(),
        )
    )

    if result.rowcount:
        await session.commit()
    else:
        await session.rollback()


async def _reserve(
    session: AsyncSession,
    *,
    week_start_date: date,
    metrics: WeeklyMetrics,
    request_id: str,
    fingerprint: str,
    extra_instructions: str | None,
) -> WeeklyManagerReport:
    for _ in range(4):
        version = await _next_version(session, week_start_date)
        report = WeeklyManagerReport(
            week_start_date=week_start_date,
            week_end_date=week_start_date + timedelta(days=6),
            version=version,
            status="pending",
            request_id=request_id,
            request_fingerprint=fingerprint,
            model=None,
            is_partial_week=metrics.is_partial_week,
            extra_instructions=extra_instructions,
            metrics_snapshot={},
            data_quality=[],
            narrative=None,
            references={},
            error_message=None,
        )
        session.add(report)

        try:
            await session.commit()
            return report
        except IntegrityError:
            await session.rollback()
            existing = await _get_by_request_id(session, request_id)

            if existing is not None:
                raise ConflictError(
                    "Bu istek kimliği zaten kullanılıyor."
                )

            # Version race: another request took this version. Retry.

    raise ConflictError(
        "Rapor sürümü oluşturulamadı. Lütfen tekrar deneyin."
    )


async def _complete(
    session: AsyncSession,
    *,
    report_id: int,
    metrics: WeeklyMetrics,
    narrative: dict,
    model: str,
) -> None:
    result = await session.execute(
        update(WeeklyManagerReport)
        .where(
            WeeklyManagerReport.id == report_id,
            WeeklyManagerReport.status == "pending",
        )
        .values(
            status="completed",
            narrative=narrative,
            metrics_snapshot=metrics.snapshot,
            data_quality=metrics.snapshot.get("data_quality", []),
            references=metrics.references,
            model=model,
            is_partial_week=metrics.is_partial_week,
            completed_at=_now(),
            error_message=None,
        )
    )

    if result.rowcount != 1:
        await session.rollback()
        raise ConflictError(
            "Rapor durumu bu sırada değişti. Lütfen raporu yenileyin."
        )

    await session.commit()
    session.expire_all()


async def _fail(
    session: AsyncSession,
    *,
    report_id: int,
    message: str,
    metrics: WeeklyMetrics | None = None,
) -> None:
    values = {
        "status": "failed",
        "narrative": None,
        "error_message": message,
        "completed_at": _now(),
    }

    if metrics is not None:
        # Keep the deterministic facts even when the narrative failed, so
        # the administrator can inspect the week and retry safely.
        values.update(
            metrics_snapshot=metrics.snapshot,
            data_quality=metrics.snapshot.get("data_quality", []),
            references=metrics.references,
            is_partial_week=metrics.is_partial_week,
        )

    result = await session.execute(
        update(WeeklyManagerReport)
        .where(
            WeeklyManagerReport.id == report_id,
            WeeklyManagerReport.status == "pending",
        )
        .values(**values)
    )

    if result.rowcount:
        await session.commit()
    else:
        await session.rollback()


async def _run_generation(
    session: AsyncSession,
    *,
    report_id: int,
    metrics: WeeklyMetrics,
    extra_instructions: str | None = None,
) -> WeeklyReportDetail:
    if not metrics.has_data:
        await _complete(
            session,
            report_id=report_id,
            metrics=metrics,
            narrative=_empty_narrative(metrics),
            model=DETERMINISTIC_MODEL,
        )
        return await get_report(session, report_id)

    payload = weekly_report_metrics.build_ai_payload(
        metrics,
        extra_instructions=extra_instructions,
    )
    budget = _prompt_budget()

    try:
        # Release the pooled connection before the external AI call.
        await session.close()

        if len(json.dumps(payload, ensure_ascii=False)) <= budget:
            generated = await generate_weekly_manager_report_single(
                payload
            )
            result = generated.result
            model = generated.model
            validate_weekly_manager_report(result, metrics)
        else:
            project_payloads = (
                weekly_report_metrics.build_ai_project_payloads(
                    metrics,
                    extra_instructions=extra_instructions,
                )
            )
            project_results: list[dict] = []

            for project_payload in project_payloads:
                generated_map = (
                    await generate_weekly_manager_report_map(
                        project_payload
                    )
                )
                validate_project_map_result(
                    generated_map.result,
                    metrics,
                    project_token=project_payload["project_token"],
                )
                project_results.append(
                    generated_map.result.model_dump()
                )

            synthesis_payload = (
                weekly_report_metrics.build_ai_synthesis_payload(
                    metrics,
                    project_results,
                    extra_instructions=extra_instructions,
                )
            )
            generated = (
                await generate_weekly_manager_report_synthesis(
                    synthesis_payload
                )
            )
            result = generated.result
            model = generated.model
            validate_weekly_manager_report(result, metrics)

        narrative = result.model_dump()
        narrative["source"] = "ai"

        await _complete(
            session,
            report_id=report_id,
            metrics=metrics,
            narrative=narrative,
            model=model,
        )
        return await get_report(session, report_id)
    except (WeeklyReportGenerationError, WeeklyReportValidationError) as exc:
        logger.warning(
            "Weekly manager report %s failed validation/generation: %s",
            report_id,
            exc,
        )
        await _fail(
            session,
            report_id=report_id,
            message=SAFE_FAILURE_MESSAGE,
            metrics=metrics,
        )
        raise ServiceUnavailableError(SAFE_FAILURE_MESSAGE) from exc
    except Exception as exc:  # network, SDK, unexpected
        logger.exception(
            "Weekly manager report %s failed unexpectedly.",
            report_id,
        )
        await _fail(
            session,
            report_id=report_id,
            message=SAFE_FAILURE_MESSAGE,
            metrics=metrics,
        )
        raise ServiceUnavailableError(SAFE_FAILURE_MESSAGE) from exc


async def create_report(
    session: AsyncSession,
    payload: WeeklyReportCreate,
    *,
    today: date | None = None,
) -> WeeklyReportDetail:
    today_value = today or istanbul_today()
    week_start_date = payload.week_start_date
    _validate_week_start(week_start_date, today_value)

    extra = (payload.extra_instructions or "").strip() or None
    fingerprint = _fingerprint(week_start_date, extra)

    await _mark_stale_pending(
        session,
        week_start_date=week_start_date,
    )

    existing = await _get_by_request_id(session, payload.request_id)

    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ConflictError(
                "Aynı istek kimliği farklı içerikle kullanılamaz."
            )

        if existing.status == "completed":
            return _detail(existing)

        if existing.status == "pending":
            raise ConflictError(
                "Bu rapor isteği hâlâ işleniyor. Lütfen bekleyin."
            )

        # Failed row: reuse the same row and version.
        metrics = await weekly_report_metrics.build_weekly_metrics(
            session,
            existing.week_start_date,
            today=today_value,
        )

        existing.status = "pending"
        existing.error_message = None
        existing.completed_at = None
        # Reset the stale-pending clock for this new attempt.
        existing.created_at = _now()
        await session.commit()

        return await _run_generation(
            session,
            report_id=existing.id,
            metrics=metrics,
            extra_instructions=existing.extra_instructions,
        )

    metrics = await weekly_report_metrics.build_weekly_metrics(
        session,
        week_start_date,
        today=today_value,
    )

    report = await _reserve(
        session,
        week_start_date=week_start_date,
        metrics=metrics,
        request_id=payload.request_id,
        fingerprint=fingerprint,
        extra_instructions=extra,
    )

    return await _run_generation(
        session,
        report_id=report.id,
        metrics=metrics,
        extra_instructions=extra,
    )


async def get_report(
    session: AsyncSession,
    report_id: int,
) -> WeeklyReportDetail:
    report = await session.get(WeeklyManagerReport, report_id)

    if report is None:
        raise NotFoundError("Haftalık yönetici raporu bulunamadı.")

    return _detail(report)


async def list_reports(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    week_start_date: date | None = None,
    status: WeeklyManagerReportStatus | None = None,
) -> WeeklyReportListResponse:
    filters = []

    if week_start_date is not None:
        filters.append(
            WeeklyManagerReport.week_start_date == week_start_date
        )

    if status is not None:
        filters.append(WeeklyManagerReport.status == status.value)

    total = int(
        (
            await session.execute(
                select(func.count(WeeklyManagerReport.id)).where(
                    *filters
                )
            )
        ).scalar_one()
    )

    rows = (
        await session.execute(
            select(WeeklyManagerReport)
            .where(*filters)
            .order_by(
                WeeklyManagerReport.week_start_date.desc(),
                WeeklyManagerReport.version.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    pages = (total + page_size - 1) // page_size if total else 0

    return WeeklyReportListResponse(
        items=[_list_item(report) for report in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


async def retry_report(
    session: AsyncSession,
    report_id: int,
    *,
    today: date | None = None,
) -> WeeklyReportDetail:
    today_value = today or istanbul_today()

    await _mark_stale_pending(session, report_id=report_id)

    report = await session.get(WeeklyManagerReport, report_id)

    if report is None:
        raise NotFoundError("Haftalık yönetici raporu bulunamadı.")

    if report.status == "pending":
        raise ConflictError(
            "Rapor hâlâ işleniyor. Lütfen bekleyin."
        )

    if report.status == "completed":
        raise ConflictError(
            "Yalnızca başarısız raporlar yeniden denenebilir."
        )

    metrics = await weekly_report_metrics.build_weekly_metrics(
        session,
        report.week_start_date,
        today=today_value,
    )

    report.status = "pending"
    report.error_message = None
    report.completed_at = None
    # Reset the stale-pending clock for this new attempt.
    report.created_at = _now()
    await session.commit()

    return await _run_generation(
        session,
        report_id=report.id,
        metrics=metrics,
        extra_instructions=report.extra_instructions,
    )


async def delete_report(
    session: AsyncSession,
    report_id: int,
) -> None:
    report = await session.get(WeeklyManagerReport, report_id)

    if report is None:
        raise NotFoundError("Haftalık yönetici raporu bulunamadı.")

    if report.status == "pending":
        raise ConflictError(
            "İşlenmekte olan bir rapor silinemez."
        )

    await session.delete(report)
    await session.commit()


def build_page(
    items: list[WeeklyReportListItem],
    *,
    page: int,
    page_size: int,
    total: int,
) -> Page[WeeklyReportListItem]:
    """Kept for symmetry with other services that return ``Page``."""

    pages = (total + page_size - 1) // page_size if total else 0

    return Page(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )
