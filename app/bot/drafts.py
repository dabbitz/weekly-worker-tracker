"""JSON-safe report draft handling for the Telegram FSM.

Aiogram's in-memory storage keeps Python objects, but drafts must be
serializable. A ``WorkUpdate`` is therefore stored as
``model_dump(mode="json")`` and re-validated before every use.

All edits are validated against ``WorkUpdate`` itself so an invalid
field can never replace a valid draft.
"""

from dataclasses import dataclass
from datetime import date, datetime

from pydantic import ValidationError as PydanticValidationError

from app.schemas.work_update import ProgressScope, WorkStatus, WorkUpdate
from app.services.date_normalizer import normalize_eta_date
from app.services.progress import compute_overall_progress


WORK_STATUS_LABELS: dict[WorkStatus, str] = {
    WorkStatus.COMPLETED: "Tamamlandı",
    WorkStatus.IN_PROGRESS: "Devam ediyor",
    WorkStatus.BLOCKED: "Engellendi",
    WorkStatus.NOT_STARTED: "Henüz başlanmadı",
    WorkStatus.UNKNOWN: "Belirsiz",
}

_STATUS_BY_LABEL = {
    label.casefold(): status.value
    for status, label in WORK_STATUS_LABELS.items()
}

_CLEAR_TOKENS = {"-", "temizle", "sil"}

# DB column limits. Text columns have no practical limit, so a generous
# display/storage guard is applied instead.
TASK_REFERENCE_MAX = 250
ETA_TEXT_MAX = 255
LONG_TEXT_MAX = 2000


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    kind: str  # "status" | "integer" | "text"
    optional: bool = True
    max_length: int | None = None


EDITABLE_FIELDS: dict[str, FieldSpec] = {
    "status": FieldSpec(
        key="status",
        label="Durum",
        kind="status",
        optional=False,
    ),
    "completion_percentage": FieldSpec(
        key="completion_percentage",
        label="Toplam görev ilerlemesi (%)",
        kind="integer",
    ),
    "blocker": FieldSpec(
        key="blocker",
        label="Engel",
        kind="text",
        max_length=LONG_TEXT_MAX,
    ),
    "delay_reason": FieldSpec(
        key="delay_reason",
        label="Gecikme nedeni",
        kind="text",
        max_length=LONG_TEXT_MAX,
    ),
    "next_step": FieldSpec(
        key="next_step",
        label="Sonraki adım",
        kind="text",
        max_length=LONG_TEXT_MAX,
    ),
    "reported_eta_text": FieldSpec(
        key="reported_eta_text",
        label="Tahmini bitiş",
        kind="text",
        max_length=ETA_TEXT_MAX,
    ),
    "summary": FieldSpec(
        key="summary",
        label="Özet",
        kind="text",
        optional=False,
        max_length=LONG_TEXT_MAX,
    ),
    "task_reference_text": FieldSpec(
        key="task_reference_text",
        label="Görev referansı",
        kind="text",
        max_length=TASK_REFERENCE_MAX,
    ),
}


@dataclass(frozen=True)
class EditOutcome:
    """Result of one field edit.

    On success ``draft`` contains the re-validated JSON draft. On
    failure ``draft`` is None and ``error`` explains the problem; the
    caller must keep the previous draft untouched.
    """

    draft: dict | None
    eta_date: date | None
    error: str | None = None


def draft_to_data(draft: WorkUpdate) -> dict:
    return draft.model_dump(mode="json")


def draft_from_data(data: dict) -> WorkUpdate:
    return WorkUpdate.model_validate(data)


def _normalize_progress(data: dict) -> None:
    """Enforce the meaning of ``completion_percentage``.

    ``completion_percentage`` may only hold the overall task progress.
    An ``overall_task`` report keeps its reported value. A weekly or
    personal percentage is kept only in ``reported_progress_percentage``
    and must not leak into the overall field. The weekly conversion is
    performed later, when the approved plan and baseline are known.
    """

    try:
        scope = ProgressScope(
            data.get("progress_scope") or ProgressScope.UNCLEAR.value
        )
    except ValueError:
        scope = ProgressScope.UNCLEAR

    reported = data.get("reported_progress_percentage")
    existing_completion = data.get("completion_percentage")

    if (
        reported is None
        and scope is ProgressScope.OVERALL_TASK
        and existing_completion is not None
    ):
        reported = existing_completion
        data["reported_progress_percentage"] = reported

    data["progress_scope"] = scope.value

    if scope is ProgressScope.OVERALL_TASK:
        data["completion_percentage"] = reported
    else:
        data["completion_percentage"] = None


def clamp_ai_draft(draft: WorkUpdate) -> WorkUpdate:
    """Keep AI output inside the DB column limits.

    The AI schema has no max length, so only the two length-limited
    columns are truncated. Optional blank strings become null.

    The AI is also not allowed to report ``blocked`` without a stated
    obstacle: a delay alone must not stop the work. When the AI returns
    ``blocked`` with an empty blocker, the status falls back to
    ``in_progress`` and the reported delay is preserved in
    ``delay_reason``. An explicit obstacle keeps ``blocked`` unchanged.

    Finally, a weekly or personal percentage is removed from
    ``completion_percentage`` so only the whole task progress can ever be
    persisted there.
    """

    data = draft.model_dump(mode="json")

    for field in (
        "task_reference_text",
        "blocker",
        "delay_reason",
        "next_step",
        "reported_eta_text",
    ):
        value = data.get(field)
        if isinstance(value, str) and not value.strip():
            data[field] = None

    task_reference = data.get("task_reference_text")
    if isinstance(task_reference, str):
        data["task_reference_text"] = task_reference[:TASK_REFERENCE_MAX]

    eta_text = data.get("reported_eta_text")
    if isinstance(eta_text, str):
        data["reported_eta_text"] = eta_text[:ETA_TEXT_MAX]

    if (
        data.get("status") == WorkStatus.BLOCKED.value
        and not data.get("blocker")
    ):
        data["status"] = WorkStatus.IN_PROGRESS.value

    _normalize_progress(data)

    return WorkUpdate.model_validate(data)


def apply_progress_scope(
    draft: WorkUpdate,
    *,
    baseline: int | None = None,
    weekly_target: int | None = None,
) -> WorkUpdate:
    """Replace the AI placeholder with the backend-computed overall value.

    For ``weekly_plan`` progress this applies the deterministic
    conversion using the real baseline and the approved weekly target.
    Other non-overall scopes stay without an overall percentage.
    """

    overall = compute_overall_progress(
        reported=draft.reported_progress_percentage,
        scope=draft.progress_scope,
        baseline=baseline,
        weekly_target=weekly_target,
    )

    if overall == draft.completion_percentage:
        return draft

    return draft.model_copy(
        update={"completion_percentage": overall}
    )


def _status_value(raw_value: str) -> tuple[str | None, str | None]:
    cleaned = raw_value.strip()
    normalized = cleaned.casefold()

    if normalized in _STATUS_BY_LABEL:
        return _STATUS_BY_LABEL[normalized], None

    try:
        return WorkStatus(cleaned).value, None
    except ValueError:
        labels = ", ".join(
            label for label in WORK_STATUS_LABELS.values()
        )
        return None, (
            "Geçersiz durum değeri. Şunlardan birini seçin: "
            f"{labels}."
        )


def _integer_value(raw_value: str) -> tuple[int | None, str | None]:
    cleaned = raw_value.strip()

    if cleaned in _CLEAR_TOKENS:
        return None, None

    if cleaned.startswith("%"):
        cleaned = cleaned[1:].strip()

    if not cleaned or not cleaned.isdigit():
        return None, (
            "Toplam görev ilerlemesi 0 ile 100 arasında bir tam "
            "sayı olmalıdır. Temizlemek için - yazın."
        )

    number = int(cleaned)

    if number < 0 or number > 100:
        return None, (
            "Toplam görev ilerlemesi 0 ile 100 arasında "
            "olmalıdır."
        )

    return number, None


def _text_value(
    field: str,
    spec: FieldSpec,
    raw_value: str,
) -> tuple[str | None, str | None]:
    cleaned = raw_value.strip()

    if cleaned in _CLEAR_TOKENS:
        if not spec.optional:
            return None, f"{spec.label} boş olamaz."
        return None, None

    if not cleaned:
        return None, (
            f"{spec.label} için boş bir değer gönderilemez. "
            "Temizlemek için - yazın."
        )

    if spec.max_length is not None and len(cleaned) > spec.max_length:
        return None, (
            f"{spec.label} en fazla {spec.max_length} karakter "
            "olabilir."
        )

    return cleaned, None


def apply_edit(
    *,
    draft_data: dict,
    field: str,
    raw_value: str | None,
    reference_datetime: datetime,
    current_eta_date: date | None = None,
) -> EditOutcome:
    """Apply one edit and re-validate the whole draft."""

    spec = EDITABLE_FIELDS.get(field)

    if spec is None:
        return EditOutcome(
            draft=None,
            eta_date=current_eta_date,
            error="Bu alan düzenlenemiyor.",
        )

    value = raw_value or ""
    data = dict(draft_data)

    if spec.kind == "status":
        status_value, error = _status_value(value)
        if error is not None:
            return EditOutcome(None, current_eta_date, error)
        data["status"] = status_value

    elif spec.kind == "integer":
        number, error = _integer_value(value)
        if error is not None:
            return EditOutcome(None, current_eta_date, error)
        # A manual edit of this field is by definition overall progress.
        data["completion_percentage"] = number
        data["reported_progress_percentage"] = number
        data["progress_scope"] = ProgressScope.OVERALL_TASK.value

    else:
        text_value, error = _text_value(field, spec, value)
        if error is not None:
            return EditOutcome(None, current_eta_date, error)
        data[field] = text_value

    try:
        validated = WorkUpdate.model_validate(data)
    except PydanticValidationError:
        return EditOutcome(
            draft=None,
            eta_date=current_eta_date,
            error="Girilen değer geçersiz. Taslak değiştirilmedi.",
        )

    eta_date = current_eta_date

    if field == "reported_eta_text":
        eta_result = normalize_eta_date(
            validated.reported_eta_text,
            reference_datetime,
        )
        eta_date = eta_result.normalized_date

    return EditOutcome(
        draft=validated.model_dump(mode="json"),
        eta_date=eta_date,
        error=None,
    )
