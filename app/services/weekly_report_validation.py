"""Validation gates for AI weekly manager report output.

The AI may only *interpret* deterministic facts. This module enforces that
contract before a narrative is stored:

* every source token exists in the deterministic reference map;
* task classifications echo the deterministic classification exactly;
* no invented number or date appears in the text;
* no employee name, database id, Telegram id, URL or secret leaks;
* banned phrasing is rejected;
* manager interventions are evidence-backed and limited;
* partial weeks carry the required label.

Any failure raises :class:`WeeklyReportValidationError`; the service then
stores a failed report without a narrative. A partial or unvalidated
narrative is never marked completed.
"""

from __future__ import annotations

import re

from app.schemas.ai_weekly_report import (
    AIProjectMapResult,
    AIWeeklyManagerReport,
)
from app.services.weekly_report_metrics import (
    WeeklyMetrics,
    allowed_dates,
    allowed_numbers,
)

TOKEN_PATTERN = re.compile(r"^(?:E|T|P|U|W|WEEK)\d+$")
ISO_DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
DOTTED_DATE_PATTERN = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b")
URL_PATTERN = re.compile(r"(?:https?://|www\.)", re.IGNORECASE)
DATABASE_ID_PATTERN = re.compile(
    r"(?:#\s*\d+|\b(?:id|kimlik)\s*[:#]?\s*\d+)",
    re.IGNORECASE,
)
TELEGRAM_ID_PATTERN = re.compile(r"\b\d{6,}\b")

BANNED_PHRASES = (
    "yapılmadı",
    "yapilmadi",
    "başarısız",
    "basarisiz",
    "ihmal edildi",
)

PARTIAL_WEEK_LABEL = "kısmi değerlendirme"

TURKISH_MONTHS = {
    "ocak": 1,
    "şubat": 2,
    "subat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5,
    "mayis": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8,
    "agustos": 8,
    "eylül": 9,
    "eylul": 9,
    "ekim": 10,
    "kasım": 11,
    "kasim": 11,
    "aralık": 12,
    "aralik": 12,
}

MONTH_NAME_PATTERN = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(TURKISH_MONTHS) + r")\s+(\d{4})\b",
    re.IGNORECASE,
)


class WeeklyReportValidationError(RuntimeError):
    """Raised when AI output violates the weekly report contract."""


def _all_strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_all_strings(item))
        return result
    if isinstance(value, (list, tuple, set)):
        result = []
        for item in value:
            result.extend(_all_strings(item))
        return result
    return []


def _all_tokens(value) -> list[str]:
    tokens: list[str] = []
    for text in _all_strings(value):
        if TOKEN_PATTERN.fullmatch(text):
            tokens.append(text)
    return tokens


def _collect_source_tokens(result) -> list[str]:
    tokens: list[str] = []

    for item in result.general_highlights:
        tokens.extend(item.source_tokens)
    for item in result.general_issues:
        tokens.extend(item.source_tokens)

    for project in result.project_analyses:
        for item in project.highlights:
            tokens.extend(item.source_tokens)
        for item in project.risks:
            tokens.extend(item.source_tokens)

    for employee in result.employee_analyses:
        for item in employee.observations:
            tokens.extend(item.source_tokens)

    for task in result.task_assessments:
        tokens.extend(task.source_tokens)

    for collection in (
        result.unmet_work_analysis,
        result.history_comparison,
        result.recommendations,
        result.data_quality_notes,
    ):
        for item in collection:
            tokens.extend(item.source_tokens)

    for intervention in result.manager_interventions:
        tokens.extend(intervention.source_tokens)
        tokens.extend(intervention.affected_project_tokens)
        tokens.extend(intervention.affected_task_tokens)

    return tokens


def _collect_map_source_tokens(result: AIProjectMapResult) -> list[str]:
    tokens: list[str] = []

    for item in result.highlights:
        tokens.extend(item.source_tokens)
    for item in result.risks:
        tokens.extend(item.source_tokens)
    for task in result.task_assessments:
        tokens.extend(task.source_tokens)
    for intervention in result.interventions:
        tokens.extend(intervention.source_tokens)
        tokens.extend(intervention.affected_project_tokens)
        tokens.extend(intervention.affected_task_tokens)

    return tokens


def _check_tokens(
    result,
    metrics: WeeklyMetrics,
) -> None:
    tokens = _collect_source_tokens(result)

    for token in tokens:
        if not TOKEN_PATTERN.fullmatch(token):
            raise WeeklyReportValidationError(
                f"Geçersiz kaynak token'ı: {token!r}"
            )

        if token not in metrics.allowed_tokens:
            raise WeeklyReportValidationError(
                f"Bilinmeyen kaynak token'ı: {token!r}"
            )

    for project in result.project_analyses:
        if project.project_token not in metrics.references["projects"]:
            raise WeeklyReportValidationError(
                "Bilinmeyen proje token'ı."
            )

    for employee in result.employee_analyses:
        if employee.employee_token not in metrics.references["employees"]:
            raise WeeklyReportValidationError(
                "Bilinmeyen çalışan token'ı."
            )

    for intervention in result.manager_interventions:
        for token in intervention.affected_project_tokens:
            if token not in metrics.references["projects"]:
                raise WeeklyReportValidationError(
                    "Müdahale kaydında bilinmeyen proje token'ı."
                )
        for token in intervention.affected_task_tokens:
            if token not in metrics.references["tasks"]:
                raise WeeklyReportValidationError(
                    "Müdahale kaydında bilinmeyen görev token'ı."
                )


def _check_classifications(
    result,
    metrics: WeeklyMetrics,
) -> None:
    seen: set[str] = set()

    for assessment in result.task_assessments:
        token = assessment.task_token

        if token in seen:
            raise WeeklyReportValidationError(
                "Aynı görev için birden fazla değerlendirme döndürüldü."
            )

        seen.add(token)

        if token not in metrics.task_classifications:
            raise WeeklyReportValidationError(
                "Değerlendirme, haftanın görev listesinde olmayan bir "
                "görevi işaret ediyor."
            )

        expected = metrics.task_classifications[token]

        if assessment.classification != expected:
            raise WeeklyReportValidationError(
                "AI görev sınıflandırması deterministik sonuçla "
                "uyuşmuyor."
            )


def _normalize_dotted_date(day: str, month: str, year: str) -> str:
    day_value = int(day)
    month_value = int(month)
    year_value = int(year)

    if year_value < 100:
        year_value += 2000

    return f"{year_value:04d}-{month_value:02d}-{day_value:02d}"


def _check_dates_and_numbers(
    result,
    metrics: WeeklyMetrics,
) -> None:
    allowed_date_values = allowed_dates(metrics)
    allowed_number_values = allowed_numbers(metrics)

    for text in _all_strings(result.model_dump()):
        for match in ISO_DATE_PATTERN.findall(text):
            if match not in allowed_date_values:
                raise WeeklyReportValidationError(
                    "AI metni doğrulanmış verilerde bulunmayan bir tarih "
                    "içeriyor."
                )

        for day, month, year in DOTTED_DATE_PATTERN.findall(text):
            normalized = _normalize_dotted_date(day, month, year)

            if normalized not in allowed_date_values:
                raise WeeklyReportValidationError(
                    "AI metni doğrulanmış verilerde bulunmayan bir tarih "
                    "içeriyor."
                )

        for day, month_name, year in MONTH_NAME_PATTERN.findall(text):
            month = TURKISH_MONTHS[month_name.casefold()]
            normalized = (
                f"{int(year):04d}-{month:02d}-{int(day):02d}"
            )

            if normalized not in allowed_date_values:
                raise WeeklyReportValidationError(
                    "AI metni doğrulanmış verilerde bulunmayan bir tarih "
                    "içeriyor."
                )

        # Remove date strings and reference tokens before scanning digits.
        scrubbed = ISO_DATE_PATTERN.sub(" ", text)
        scrubbed = DOTTED_DATE_PATTERN.sub(" ", scrubbed)
        scrubbed = MONTH_NAME_PATTERN.sub(" ", scrubbed)
        scrubbed = re.sub(
            r"\b(?:E|T|P|U|W|WEEK)\d+\b",
            " ",
            scrubbed,
        )

        for match in re.findall(r"\d+", scrubbed):
            if str(int(match)) not in allowed_number_values:
                raise WeeklyReportValidationError(
                    "AI metni deterministik metriklerde bulunmayan bir "
                    "sayı içeriyor."
                )


def _check_privacy_and_language(
    result,
    metrics: WeeklyMetrics,
) -> None:
    texts = _all_strings(result.model_dump())
    joined = "\n".join(texts).casefold()

    for phrase in BANNED_PHRASES:
        if phrase in joined:
            raise WeeklyReportValidationError(
                "AI metni yasaklı bir ifade içeriyor."
            )

    for name in metrics.employee_names:
        normalized_name = name.strip().casefold()

        if len(normalized_name) < 3:
            continue

        if normalized_name in joined:
            raise WeeklyReportValidationError(
                "AI metni gerçek bir çalışan adı içeriyor."
            )

        parts = [
            part
            for part in normalized_name.split()
            if len(part) >= 4
        ]

        if len(parts) >= 2 and all(part in joined for part in parts):
            raise WeeklyReportValidationError(
                "AI metni gerçek bir çalışan adı içeriyor."
            )

    for text in texts:
        if URL_PATTERN.search(text):
            raise WeeklyReportValidationError(
                "AI metni bir URL içeriyor."
            )

        if DATABASE_ID_PATTERN.search(text):
            raise WeeklyReportValidationError(
                "AI metni bir veritabanı kimliği içeriyor."
            )

        if TELEGRAM_ID_PATTERN.search(text):
            raise WeeklyReportValidationError(
                "AI metni uzun bir sayısal kimlik içeriyor."
            )


def _check_interventions(
    result,
    metrics: WeeklyMetrics,
) -> None:
    if len(result.manager_interventions) > 8:
        raise WeeklyReportValidationError(
            "En fazla 8 yönetici müdahalesi önerilebilir."
        )

    for intervention in result.manager_interventions:
        if not intervention.source_tokens:
            raise WeeklyReportValidationError(
                "Her müdahale en az bir kaynak referansı içermelidir."
            )

        if not (
            intervention.affected_project_tokens
            or intervention.affected_task_tokens
        ):
            raise WeeklyReportValidationError(
                "Her müdahale en az bir proje veya görev belirtmelidir."
            )

        if not intervention.recommended_action.strip():
            raise WeeklyReportValidationError(
                "Müdahale için önerilen eylem boş olamaz."
            )


def _check_partial_week(
    result,
    metrics: WeeklyMetrics,
) -> None:
    if not metrics.is_partial_week:
        return

    note = (result.partial_week_note or "").casefold()

    if PARTIAL_WEEK_LABEL not in note:
        raise WeeklyReportValidationError(
            "Kısmi hafta için 'Kısmi değerlendirme' etiketi zorunludur."
        )


def validate_weekly_manager_report(
    result: AIWeeklyManagerReport,
    metrics: WeeklyMetrics,
) -> None:
    """Run every gate. Raises on the first contract violation."""

    if not isinstance(result, AIWeeklyManagerReport):
        raise WeeklyReportValidationError(
            "Beklenmeyen AI yanıt türü."
        )

    _check_tokens(result, metrics)
    _check_classifications(result, metrics)
    _check_dates_and_numbers(result, metrics)
    _check_privacy_and_language(result, metrics)
    _check_interventions(result, metrics)
    _check_partial_week(result, metrics)


def validate_project_map_result(
    result: AIProjectMapResult,
    metrics: WeeklyMetrics,
    *,
    project_token: str,
) -> None:
    """Validate one map-phase project result."""

    if result.project_token != project_token:
        raise WeeklyReportValidationError(
            "Proje eşleme sonucu beklenen proje token'ı ile uyuşmuyor."
        )

    for token in _collect_map_source_tokens(result):
        if not TOKEN_PATTERN.fullmatch(token):
            raise WeeklyReportValidationError(
                "Geçersiz kaynak token'ı."
            )
        if token not in metrics.allowed_tokens:
            raise WeeklyReportValidationError(
                "Bilinmeyen kaynak token'ı."
            )

    for assessment in result.task_assessments:
        if assessment.task_token not in metrics.task_classifications:
            raise WeeklyReportValidationError(
                "Proje eşlemesi haftanın dışında bir göreve atıf yapıyor."
            )

        expected = metrics.task_classifications[
            assessment.task_token
        ]

        if assessment.classification != expected:
            raise WeeklyReportValidationError(
                "AI görev sınıflandırması deterministik sonuçla "
                "uyuşmuyor."
            )

    for intervention in result.interventions:
        if not intervention.source_tokens:
            raise WeeklyReportValidationError(
                "Her müdahale en az bir kaynak referansı içermelidir."
            )

        for token in intervention.affected_project_tokens:
            if token not in metrics.references["projects"]:
                raise WeeklyReportValidationError(
                    "Bilinmeyen proje token'ı."
                )

        for token in intervention.affected_task_tokens:
            if token not in metrics.references["tasks"]:
                raise WeeklyReportValidationError(
                    "Bilinmeyen görev token'ı."
                )

    _check_dates_and_numbers(result, metrics)
    _check_privacy_and_language(result, metrics)
