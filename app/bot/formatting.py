"""Turkish message and keyboard builders for the report flow.

Formatting is kept separate from Telegram handlers so the preview can
be tested without a bot. The weekly target and the employee's current
overall progress are always shown with distinct labels.
"""

from datetime import date
from typing import Iterable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.drafts import (
    EDITABLE_FIELDS,
    WORK_STATUS_LABELS,
    FieldSpec,
)
from app.schemas.work_update import WorkStatus
from app.services.employee_work_service import EmployeeTaskContext

WEEKDAY_LABELS = (
    "pazartesi",
    "salı",
    "çarşamba",
    "perşembe",
    "cuma",
    "cumartesi",
    "pazar",
)

MAX_LISTED_TASKS = 10
MAX_ORIGINAL_IN_PREVIEW = 1200
MAX_SUMMARY_IN_PREVIEW = 900
MAX_PREVIEW_LENGTH = 3900

NO_PLAN_NOTE = (
    "Bu görev için bu hafta onaylanmış bir haftalık hedef "
    "bulunmuyor. Yine de çalışma raporu gönderebilirsiniz."
)

CONFLICT_NOTE = (
    "Bu görev için geçerli tarihlerde birden fazla onaylı "
    "haftalık plan bulundu. Sistem yanlış hedef seçmemek için "
    "herhangi birini ilişkilendirmedi. Raporunuzu yine de "
    "gönderebilirsiniz."
)

REGISTER_GUIDANCE = (
    "Bu Telegram hesabı aktif çalışan olarak kayıtlı değil.\n\n"
    "Kayıt için /register İsim Soyisim komutunu kullanın."
)

PRIVATE_ONLY = (
    "Çalışan raporlama yalnızca botla özel sohbette "
    "kullanılabilir."
)

PROGRESS_SCOPE_LABELS = {
    "overall_task": "Tüm görev",
    "weekly_plan": "Bu haftanın planlanan çalışmaları",
    "personal_contribution": "Çalışanın kişisel katkısı",
    "unclear": "Belirsiz",
}

RESTART_HINT = (
    "Rapor akışını /gorevlerim komutuyla yeniden "
    "başlatabilirsiniz."
)


def format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def format_week_range(start: date, end: date) -> str:
    return f"{format_date(start)} - {format_date(end)}"


def week_range_from_data(start: str, end: str) -> str:
    return format_week_range(
        date.fromisoformat(start),
        date.fromisoformat(end),
    )


def weekday_label(value: date) -> str:
    return WEEKDAY_LABELS[value.weekday()]


def _shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)].rstrip() + "…"


def _plan_lines(context: EmployeeTaskContext) -> list[str]:
    if context.plan_conflict:
        return [CONFLICT_NOTE]

    plan = context.weekly_plan

    if plan is None:
        return [NO_PLAN_NOTE]

    if plan.target_completion_percentage is None:
        percentage = "belirtilmedi"
    else:
        percentage = f"%{plan.target_completion_percentage}"

    return [
        f"Haftalık hedef: {_shorten(plan.target_description, 120)}",
        f"Hedef tamamlanma: {percentage}",
        "Hafta: "
        + format_week_range(
            plan.week_start_date,
            plan.week_end_date,
        ),
    ]


def format_task_list_text(
    contexts: Iterable[EmployeeTaskContext],
    today: date,
) -> str:
    items = list(contexts)
    shown = items[:MAX_LISTED_TASKS]

    lines = [
        f"GÖREVLERİM — {format_date(today)}",
        "",
    ]

    for index, context in enumerate(shown, start=1):
        lines.append(f"{index}) {_shorten(context.title, 100)}")
        lines.append(f"Proje: {_shorten(context.project_name, 80)}")
        lines.extend(_plan_lines(context))
        lines.append("")

    if len(items) > len(shown):
        lines.append(
            f"Not: İlk {MAX_LISTED_TASKS} görev gösteriliyor."
        )
        lines.append("")

    lines.append(
        "Rapor göndermek için aşağıdaki butonlardan bir görev seçin."
    )

    return "\n".join(lines).strip()


def task_list_keyboard(
    contexts: Iterable[EmployeeTaskContext],
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{index}. {_shorten(context.title, 40)}",
                callback_data=f"task:{context.task_id}",
            )
        ]
        for index, context in enumerate(
            list(contexts)[:MAX_LISTED_TASKS],
            start=1,
        )
    ]

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _task_header(data: dict) -> list[str]:
    lines = [
        f"Görev: {data.get('task_title') or 'Belirtilmedi'}",
        f"Proje: {data.get('project_name') or 'Belirtilmedi'}",
        "",
    ]

    if data.get("plan_conflict"):
        lines.append(CONFLICT_NOTE)
    elif data.get("plan") is None:
        lines.append(NO_PLAN_NOTE)
    else:
        plan = data["plan"]
        percentage = plan.get("target_completion_percentage")
        percentage_text = (
            "belirtilmedi" if percentage is None else f"%{percentage}"
        )
        lines.append(
            "Haftalık hedef: "
            f"{plan.get('target_description') or 'Belirtilmedi'}"
        )
        lines.append(f"Hedef tamamlanma: {percentage_text}")
        lines.append(
            "Hafta: "
            + week_range_from_data(
                plan["week_start_date"],
                plan["week_end_date"],
            )
        )

    return lines


def format_selected_task_prompt(data: dict) -> str:
    lines = _task_header(data)
    lines.extend(
        [
            "",
            "Lütfen bu görev için çalışma raporunuzu tek mesaj "
            "halinde yazın.",
            "Akışı iptal etmek için /gorevlerim komutunu "
            "kullanabilirsiniz.",
        ]
    )
    return "\n".join(lines)


def _status_label(value: str) -> str:
    try:
        return WORK_STATUS_LABELS[WorkStatus(value)]
    except (ValueError, KeyError):
        return "Belirsiz"


def _scope_label(value: str) -> str:
    return PROGRESS_SCOPE_LABELS.get(value, "Belirsiz")


def _eta_lines(draft: dict, data: dict) -> list[str]:
    eta_text = draft.get("reported_eta_text")
    eta_date_raw = data.get("reported_eta_date")

    if not eta_text:
        return ["Tahmini bitiş: Çalışan tarafından belirtilmedi."]

    lines = [f"Çalışanın bitiş ifadesi: {eta_text}"]

    if not eta_date_raw:
        lines.append("Tahmini bitiş tarihi netleştirilmeli.")
        return lines

    eta_date = date.fromisoformat(eta_date_raw)
    lines.append(
        "Normalize edilmiş tahmini bitiş: "
        f"{format_date(eta_date)} ({weekday_label(eta_date)})"
    )
    return lines


def _comparison_lines(data: dict, draft: dict) -> list[str]:
    plan = data.get("plan")

    if plan is None:
        return []

    target = plan.get("target_completion_percentage")
    target_text = "belirtilmedi" if target is None else f"%{target}"

    completion = draft.get("completion_percentage")
    completion_text = (
        "belirtilmedi" if completion is None else f"%{completion}"
    )

    return [
        "",
        "HAFTALIK HEDEF VE GERÇEKLEŞEN İLERLEME",
        f"Hafta sonu için onaylanan hedef: {target_text}",
        "Rapor anındaki toplam görev ilerlemesi: "
        f"{completion_text}",
        "",
        "Haftalık hedef, hafta sonunda ulaşılması beklenen "
        "kümülatif görev tamamlanma yüzdesidir. Rapor hafta "
        "devam ederken alınmışsa iki değer arasındaki fark "
        "otomatik olarak gecikme sayılmaz.",
    ]


def format_preview_text(data: dict) -> str:
    draft = data.get("draft") or {}

    original = data.get("original_message") or ""

    if len(original) > MAX_ORIGINAL_IN_PREVIEW:
        original = (
            original[:MAX_ORIGINAL_IN_PREVIEW].rstrip()
            + "\n… (orijinal mesaj önizlemede kısaltıldı)"
        )

    summary = draft.get("summary") or "Belirtilmedi"

    if len(summary) > MAX_SUMMARY_IN_PREVIEW:
        summary = (
            summary[:MAX_SUMMARY_IN_PREVIEW].rstrip()
            + "… (özet kısaltıldı)"
        )

    lines = [
        "İŞ GÜNCELLEMESİ ÖNİZLEMESİ",
        "",
    ]

    lines.extend(_task_header(data))
    lines.extend(
        [
            "",
            "ÇALIŞANIN MESAJI",
            original,
            "",
            "AI ANALİZİ",
            "İş: "
            f"{draft.get('task_reference_text') or 'Belirtilmedi'}",
            "Durum: " + _status_label(draft.get("status", "")),
        ]
    )

    scope = draft.get("progress_scope") or "unclear"
    reported = draft.get("reported_progress_percentage")

    if reported is not None:
        lines.append(f"AI'nın yorumladığı ilerleme: %{reported}")

    lines.append(f"İlerleme kapsamı: {_scope_label(scope)}")

    completion = draft.get("completion_percentage")

    if completion is not None:
        lines.append(f"Toplam görev ilerlemesi: %{completion}")
    elif scope == "weekly_plan":
        lines.append(
            "Toplam görev ilerlemesi: Hesaplanamadı "
            "(hafta başındaki gerçek ilerleme bilinmiyor)"
        )
    elif scope == "personal_contribution":
        lines.append(
            "Toplam görev ilerlemesi: Belirtilmedi "
            "(rapor yalnızca kişisel katkıyı gösteriyor)"
        )
    else:
        lines.append("Toplam görev ilerlemesi: Belirtilmedi")

    for label, key in (
        ("Engel", "blocker"),
        ("Gecikme nedeni", "delay_reason"),
        ("Sonraki adım", "next_step"),
    ):
        value = draft.get(key)
        if value:
            lines.append(f"{label}: {value}")

    lines.extend(_eta_lines(draft, data))
    lines.extend(
        [
            "",
            "ÖZET",
            summary,
        ]
    )

    lines.extend(_comparison_lines(data, draft))
    lines.extend(
        [
            "",
            "Bu rapor henüz kaydedilmedi. Kaydetmek için "
            "aşağıdaki butonu kullanın.",
        ]
    )

    text = "\n".join(lines)

    if len(text) > MAX_PREVIEW_LENGTH:
        text = (
            text[:MAX_PREVIEW_LENGTH].rstrip()
            + "\n\n… (önizleme kısaltıldı)"
        )

    return text


def preview_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Onayla ve kaydet",
                    callback_data=f"rep:confirm:{token}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Bilgileri düzenle",
                    callback_data="rep:edit",
                )
            ],
            [
                InlineKeyboardButton(
                    text="İptal et",
                    callback_data="rep:cancel",
                )
            ],
        ]
    )


def edit_menu_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=spec.label,
                callback_data=f"rep:field:{spec.key}",
            )
        ]
        for spec in EDITABLE_FIELDS.values()
    ]

    rows.append(
        [
            InlineKeyboardButton(
                text="Geri",
                callback_data="rep:back",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def status_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=label,
                callback_data=f"rep:status:{status.value}",
            )
        ]
        for status, label in WORK_STATUS_LABELS.items()
    ]

    rows.append(
        [
            InlineKeyboardButton(
                text="Vazgeç",
                callback_data="rep:back",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_field_prompt(spec: FieldSpec) -> str:
    if spec.kind == "status":
        return (
            "Durum için aşağıdaki butonlardan birini seçin."
        )

    if spec.kind == "integer":
        return (
            "Toplam görev ilerlemesini 0 ile 100 arasında bir "
            "tam sayı olarak yazın. Temizlemek için - yazın."
        )

    if spec.key == "reported_eta_text":
        return (
            "Tahmini bitiş ifadesini yazın (örn. "
            "'cuma gününe kadar'). Temizlemek için - yazın."
        )

    if spec.optional:
        return (
            f"{spec.label} için yeni değeri yazın. "
            "Temizlemek için - yazın."
        )

    return f"{spec.label} için yeni değeri yazın."
