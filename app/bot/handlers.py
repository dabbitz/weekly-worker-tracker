"""Telegram handlers for employee text reporting.

The flow is deliberately narrow:

* only active employees in private chats,
* the task is always re-resolved from the database,
* the AI result is only a draft held in FSM data,
* a row is inserted only after an explicit confirmation,
* the source report message id, not the callback message id, is stored.

Handlers are kept thin. Draft validation, formatting and snapshot
comparison live in separate modules so they can be tested without
Telegram or Gemini.
"""

import logging
import secrets
from datetime import date, datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from pydantic import ValidationError as PydanticValidationError

from app.bot import formatting
from app.bot.drafts import (
    EDITABLE_FIELDS,
    apply_edit,
    apply_progress_scope,
    clamp_ai_draft,
    draft_from_data,
)
from app.bot.selection import (
    PENDING_KIND_TEXT,
    PENDING_KIND_VOICE,
    context_matches_selection,
    pending_selection_data,
    pending_token_matches,
    plan_to_data,
    selection_data,
)
from app.bot.states import ReportFlow
from app.database.connection import SessionLocal
from app.schemas.work_update import WorkUpdate, WorkStatus
from app.services.date_normalizer import normalize_eta_date
from app.services.employee_work_service import (
    create_task_update,
    get_active_employee_by_telegram_id,
    get_progress_baseline,
    get_task_context,
    list_my_tasks,
)
from app.services.exceptions import (
    ConflictError,
    NotFoundError,
)
from app.services.exceptions import ValidationError as ServiceValidationError
from app.services.week_utils import istanbul_today

logger = logging.getLogger("worktrack.bot")

router = Router(name="employee_reports")

_extractor = None
_transcriber = None

# Telegram voice messages are OGG/Opus files. The audio stays in memory
# and is never written to the database or the file system.
VOICE_MIME_TYPE = "audio/ogg"
MAX_VOICE_DURATION_SECONDS = 180
MAX_VOICE_FILE_SIZE_BYTES = 5 * 1024 * 1024


class _PreservedVoice:
    """Voice metadata held in FSM data while the task is chosen.

    Only the Telegram ``file_id`` (and its small metadata) is kept; the
    audio bytes are downloaded after the employee selects a task.
    """

    def __init__(
        self,
        *,
        file_id: str,
        duration: int | None = None,
        file_size: int | None = None,
        mime_type: str = VOICE_MIME_TYPE,
    ):
        self.file_id = file_id
        self.duration = duration
        self.file_size = file_size
        self.mime_type = mime_type


class _PreservedReportMessage:
    """Message-shaped view of a report sent before task selection.

    The AI pipeline reads the original message id, date and payload.
    Replies go through the selection callback's chat, because the
    original message object is no longer available.
    """

    def __init__(
        self,
        *,
        bot,
        chat,
        from_user,
        message_id: int,
        date: datetime,
        text: str | None = None,
        voice=None,
        answer_target,
    ):
        self.bot = bot
        self.chat = chat
        self.from_user = from_user
        self.message_id = message_id
        self.date = date
        self.text = text
        self.voice = voice
        self.audio = None
        self.video_note = None
        self._answer_target = answer_target

    async def answer(self, text: str, reply_markup=None, **kwargs):
        return await self._answer_target.answer(
            text,
            reply_markup=reply_markup,
            **kwargs,
        )


def set_extractor(extractor) -> None:
    """Register the shared AI extractor in the bot process."""

    global _extractor
    _extractor = extractor


def get_extractor():
    return _extractor


def set_transcriber(transcriber) -> None:
    """Register the shared voice transcriber in the bot process."""

    global _transcriber
    _transcriber = transcriber


def get_transcriber():
    return _transcriber


def _today() -> date:
    """Patchable clock wrapper; production uses Istanbul time."""

    return istanbul_today()


def _state_is(state: str | None, expected) -> bool:
    return state == expected.state


def _extraction_context(context, today: date) -> dict:
    """Build the task/plan context sent to the AI extractor.

    The scope classifier cannot relate "bu haftaki" work to the plan
    without the selected task and the approved weekly plan.
    """

    plan = context.weekly_plan

    return {
        "task_title": context.title,
        "project_name": context.project_name,
        "planned_start_date": (
            context.planned_start_date.isoformat()
            if context.planned_start_date is not None
            else None
        ),
        "planned_due_date": (
            context.planned_due_date.isoformat()
            if context.planned_due_date is not None
            else None
        ),
        "report_date": today.isoformat(),
        "plan_conflict": context.plan_conflict,
        "weekly_plan": (
            None
            if plan is None
            else {
                "description": plan.target_description,
                "week_start_date": plan.week_start_date.isoformat(),
                "week_end_date": plan.week_end_date.isoformat(),
                "target_completion_percentage": (
                    plan.target_completion_percentage
                ),
            }
        ),
    }


def _matches_flow(data: dict, user_id: int, chat_id: int) -> bool:
    return (
        data.get("telegram_user_id") == user_id
        and data.get("chat_id") == chat_id
    )


def _callback_allowed(callback: CallbackQuery) -> bool:
    if callback.from_user is None or callback.message is None:
        return False
    if callback.message.chat.type != "private":
        return False
    return True


async def _reject_non_private(callback: CallbackQuery) -> None:
    await callback.answer(
        formatting.PRIVATE_ONLY,
        show_alert=True,
    )


async def _edit_or_send(
    callback: CallbackQuery,
    data: dict,
    text: str,
    reply_markup=None,
) -> None:
    """Edit the stored preview message, or send a fresh one."""

    message_id = data.get("preview_message_id")

    if message_id is not None:
        try:
            await callback.bot.edit_message_text(
                chat_id=data.get("chat_id"),
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
            )
            return
        except Exception:
            logger.warning("Could not edit the report preview message.")

    if callback.message is not None:
        await callback.message.answer(
            text,
            reply_markup=reply_markup,
        )


async def _clear_and_replace(
    callback: CallbackQuery,
    state: FSMContext,
    data: dict,
    text: str,
) -> None:
    await state.clear()
    await _edit_or_send(callback, data, text, reply_markup=None)


async def _replace_callback_message(
    callback: CallbackQuery,
    text: str,
) -> None:
    """Replace the tapped message and drop its inline keyboard."""

    try:
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=text,
            reply_markup=None,
        )
    except Exception:
        logger.warning("Could not replace the task selection message.")
        await callback.message.answer(text)


async def _remove_previous_keyboard(
    message: Message,
    data: dict,
) -> None:
    """Best-effort removal of the previous preview's buttons.

    The confirmation token is rotated for every edit, so the old
    buttons are already rejected. Clearing the markup also stops the
    employee from tapping them again.
    """

    previous_id = data.get("preview_message_id")

    if previous_id is None:
        return

    try:
        await message.bot.edit_message_reply_markup(
            chat_id=data.get("chat_id"),
            message_id=previous_id,
            reply_markup=None,
        )
    except Exception:
        logger.warning(
            "Could not remove the previous preview keyboard; the "
            "rotated token still blocks stale confirmations."
        )


async def _send_fresh_preview(
    message: Message,
    state: FSMContext,
    data: dict,
) -> bool:
    """Send the current draft as a brand new preview message.

    Editing the old message in place leaves the refreshed report above
    the employee's latest messages, so every successful edit is
    delivered as a new message at the end of the chat. The previous
    preview's keyboard is cleared and its token is already invalid.

    Returns ``False`` when Telegram rejects the send; the caller must
    then report the failure instead of claiming success.
    """

    text = formatting.format_preview_text(data)
    markup = formatting.preview_keyboard(
        data.get("confirmation_token") or ""
    )

    await _remove_previous_keyboard(message, data)

    try:
        sent = await message.answer(text, reply_markup=markup)
    except Exception:
        logger.exception("Could not send the updated report preview.")
        await message.answer(
            "Güncellenmiş rapor önizlemesi Telegram'a "
            "gönderilemedi. Taslağınız kaybolmadı; lütfen "
            "/gorevlerim komutuyla rapor akışını yeniden başlatın."
        )
        return False

    data["preview_message_id"] = getattr(sent, "message_id", None)
    await state.set_data(data)
    return True


@router.message(Command("gorevlerim", "rapor"))
async def gorevlerim_handler(
    message: Message,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return

    if message.chat.type != "private":
        await message.answer(formatting.PRIVATE_ONLY)
        return

    await state.clear()

    today = _today()

    async with SessionLocal() as session:
        employee = await get_active_employee_by_telegram_id(
            session,
            message.from_user.id,
        )

        if employee is None:
            await message.answer(formatting.REGISTER_GUIDANCE)
            return

        tasks = await list_my_tasks(session, employee.id, today)

    if not tasks:
        await message.answer(
            "Bu hafta için size atanmış bir görev bulunmuyor.\n\n"
            "Görev ataması yapıldığında buradan rapor "
            "gönderebilirsiniz."
        )
        return

    await message.answer(
        formatting.format_task_list_text(tasks, today),
        reply_markup=formatting.task_list_keyboard(tasks),
    )


@router.message(Command("iptal"))
async def iptal_handler(
    message: Message,
    state: FSMContext,
) -> None:
    """Cancel a pending task selection without touching other flows."""

    if message.from_user is None:
        return

    if message.chat.type != "private":
        await message.answer(formatting.PRIVATE_ONLY)
        return

    data = await state.get_data()
    current = await state.get_state()

    if (
        _state_is(current, ReportFlow.choosing_task)
        and _matches_flow(data, message.from_user.id, message.chat.id)
    ):
        await state.clear()
        await message.answer(formatting.PENDING_CANCEL_TEXT)
        return

    await message.answer(formatting.NO_PENDING_SELECTION)


@router.callback_query(F.data.startswith("task:"))
async def task_selection_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    if callback.message.chat.type != "private":
        await _reject_non_private(callback)
        return

    raw_task_id = (callback.data or "").split(":", 1)[-1]

    try:
        task_id = int(raw_task_id)
    except ValueError:
        await callback.answer(
            "Geçersiz görev seçimi.",
            show_alert=True,
        )
        return

    today = _today()

    async with SessionLocal() as session:
        employee = await get_active_employee_by_telegram_id(
            session,
            callback.from_user.id,
        )

        if employee is None:
            await state.clear()
            await callback.answer(
                "Aktif çalışan kaydı bulunamadı.",
                show_alert=True,
            )
            await callback.message.answer(formatting.REGISTER_GUIDANCE)
            return

        try:
            context = await get_task_context(
                session,
                employee.id,
                task_id,
                today,
            )
        except NotFoundError:
            await state.clear()
            await callback.answer(
                "Görev bulunamadı veya bu göreve atanmış değilsiniz.",
                show_alert=True,
            )
            return

    data = selection_data(
        context,
        telegram_user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
    )

    await state.set_data(data)
    await state.set_state(ReportFlow.waiting_for_report)

    await callback.answer("Görev seçildi.")

    prompt = formatting.format_selected_task_prompt(data)

    try:
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=prompt,
            reply_markup=None,
        )
    except Exception:
        logger.warning("Could not replace the task list message.")
        await callback.message.answer(prompt)


@router.callback_query(F.data.startswith("pending:task:"))
async def pending_task_selection_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Analyse a preserved report against the task chosen with one tap."""

    if not _callback_allowed(callback):
        await _reject_non_private(callback)
        return

    parts = (callback.data or "").split(":")
    token = parts[2] if len(parts) == 4 else ""
    raw_task_id = parts[3] if len(parts) == 4 else ""

    try:
        task_id = int(raw_task_id)
    except ValueError:
        task_id = None

    data = await state.get_data()

    if not data or not _matches_flow(
        data,
        callback.from_user.id,
        callback.message.chat.id,
    ):
        # Never clear another employee's pending selection.
        await callback.answer(
            "Bu görev seçimi bulunamadı veya size ait değil.",
            show_alert=True,
        )
        return

    if not _state_is(
        await state.get_state(),
        ReportFlow.choosing_task,
    ):
        await callback.answer(
            "Bu görev seçimi artık geçerli değil. Lütfen raporunuzu "
            "yeniden gönderin.",
            show_alert=True,
        )
        return

    if task_id is None or not pending_token_matches(data, token):
        await callback.answer(
            "Görev seçimi geçersiz veya eski. Lütfen güncel "
            "butonları kullanın.",
            show_alert=True,
        )
        return

    kind = data.get("pending_kind")
    source_message_id = data.get("source_message_id")
    source_message_date = data.get("source_message_date")

    if source_message_id is None or source_message_date is None:
        await state.clear()
        await callback.answer(
            "Bekleyen rapor bulunamadı. Lütfen raporunuzu yeniden "
            "gönderin.",
            show_alert=True,
        )
        return

    try:
        source_date = datetime.fromisoformat(source_message_date)
    except (TypeError, ValueError):
        await state.clear()
        await callback.answer(
            "Bekleyen rapor bilgisi geçersiz. Lütfen raporunuzu "
            "yeniden gönderin.",
            show_alert=True,
        )
        return

    today = _today()

    async with SessionLocal() as session:
        employee = await get_active_employee_by_telegram_id(
            session,
            callback.from_user.id,
        )

        if employee is None:
            await state.clear()
            await callback.answer(
                "Aktif çalışan kaydı bulunamadı.",
                show_alert=True,
            )
            await callback.message.answer(formatting.REGISTER_GUIDANCE)
            return

        try:
            context = await get_task_context(
                session,
                employee.id,
                task_id,
                today,
            )
        except NotFoundError:
            # Keep the pending report so another assigned task can be
            # chosen; the stale task itself is rejected.
            await callback.answer(
                "Görev bulunamadı veya bu göreve atanmış değilsiniz.",
                show_alert=True,
            )
            return

    source_text = data.get("pending_text") or ""
    voice = None

    if kind == PENDING_KIND_TEXT:
        if not source_text.strip():
            await state.clear()
            await callback.answer(
                "Bekleyen rapor metni bulunamadı. Lütfen raporunuzu "
                "yeniden gönderin.",
                show_alert=True,
            )
            return
    elif kind == PENDING_KIND_VOICE:
        file_id = data.get("pending_voice_file_id")

        if not file_id:
            await state.clear()
            await callback.answer(
                "Bekleyen sesli mesaj bulunamadı. Lütfen sesli "
                "mesajınızı yeniden gönderin.",
                show_alert=True,
            )
            return

        voice = _PreservedVoice(
            file_id=file_id,
            duration=data.get("pending_voice_duration"),
            file_size=data.get("pending_voice_file_size"),
        )
    else:
        await state.clear()
        await callback.answer(
            "Bekleyen rapor bilgisi geçersiz. Lütfen raporunuzu "
            "yeniden gönderin.",
            show_alert=True,
        )
        return

    # The pending payload is replaced by the selected task snapshot, so
    # it cannot be processed twice and no longer occupies the FSM.
    selection = selection_data(
        context,
        telegram_user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
    )

    await state.set_data(selection)
    await state.set_state(ReportFlow.waiting_for_report)

    await _replace_callback_message(
        callback,
        formatting.task_selected_text(context),
    )
    await callback.answer("Görev seçildi.")

    preserved = _PreservedReportMessage(
        bot=callback.bot,
        chat=callback.message.chat,
        from_user=callback.from_user,
        message_id=source_message_id,
        date=source_date,
        text=source_text or None,
        voice=voice,
        answer_target=callback.message,
    )

    if kind == PENDING_KIND_VOICE:
        await _transcribe_and_preview(
            preserved,
            state,
            selection,
            context,
            today,
        )
        return

    await _analyze_and_preview(
        preserved,
        state,
        selection,
        context,
        source_text,
        today,
    )


@router.callback_query(F.data.startswith("pending:cancel:"))
async def pending_cancel_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Discard a preserved report without analysing or saving it."""

    if not _callback_allowed(callback):
        await _reject_non_private(callback)
        return

    token = (callback.data or "").split(":", 2)[-1]
    data = await state.get_data()

    if not data or not _matches_flow(
        data,
        callback.from_user.id,
        callback.message.chat.id,
    ):
        await callback.answer(
            "İptal edilecek bir rapor seçimi bulunamadı.",
            show_alert=True,
        )
        return

    if not _state_is(
        await state.get_state(),
        ReportFlow.choosing_task,
    ):
        await callback.answer(
            "Bu iptal bağlantısı artık geçerli değil.",
            show_alert=True,
        )
        return

    if not pending_token_matches(data, token):
        await callback.answer(
            "Bu iptal bağlantısı artık geçerli değil.",
            show_alert=True,
        )
        return

    await state.clear()

    await _replace_callback_message(
        callback,
        formatting.PENDING_CANCEL_TEXT,
    )
    await callback.answer("Görev seçimi iptal edildi.")


@router.message(F.text)
async def report_text_handler(
    message: Message,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return

    if message.chat.type != "private":
        await message.answer(formatting.PRIVATE_ONLY)
        return

    current = await state.get_state()

    if _state_is(current, ReportFlow.choosing_task):
        # A pending report must not be silently replaced.
        await message.answer(formatting.PENDING_INPUT_GUIDANCE)
        return

    if _state_is(current, ReportFlow.waiting_for_report):
        await _handle_report_text(message, state)
        return

    if _state_is(current, ReportFlow.waiting_for_field_edit):
        await _handle_field_edit_text(message, state)
        return

    if _state_is(current, ReportFlow.reviewing):
        await message.answer(
            "Rapor önizlemesi hazır. Lütfen yukarıdaki "
            "'Onayla ve kaydet', 'Bilgileri düzenle' veya "
            "'İptal et' butonlarını kullanın."
        )
        return

    # No active draft. Keep other FSM flows (registration, edits) intact.
    if current is not None:
        return

    await _handle_unprompted_text(message, state)


def _has_work_content(draft: WorkUpdate) -> bool:
    """Return True when the AI draft contains a real work update.

    Greetings and unrelated chat usually come back with ``unknown`` and
    no progress, blocker, delay, next step or ETA. Such a message must
    not reach a save preview; the employee is asked for details instead.
    """

    if draft.status is not WorkStatus.UNKNOWN:
        return True

    if draft.reported_progress_percentage is not None:
        return True

    if draft.completion_percentage is not None:
        return True

    return any(
        (
            draft.blocker,
            draft.delay_reason,
            draft.next_step,
            draft.reported_eta_text,
        )
    )


async def _start_pending_selection(
    message: Message,
    state: FSMContext,
    tasks,
    *,
    kind: str,
    text: str | None = None,
) -> None:
    """Preserve the report and ask which assigned task it belongs to.

    Nothing is analysed yet. For a voice note only its Telegram file id
    and metadata are held, so the audio is fetched after the selection.
    """

    voice_file_id = None
    voice_duration = None
    voice_file_size = None

    if kind == PENDING_KIND_VOICE:
        voice = message.voice
        limit_message = _voice_limit_message(voice)

        if limit_message is not None:
            await message.answer(limit_message)
            return

        voice_file_id = getattr(voice, "file_id", None)

        if not voice_file_id:
            await message.answer(formatting.VOICE_DOWNLOAD_FAILED)
            return

        voice_duration = getattr(voice, "duration", None)
        voice_file_size = getattr(voice, "file_size", None)

    token = secrets.token_hex(4)
    today = _today()

    data = pending_selection_data(
        telegram_user_id=message.from_user.id,
        chat_id=message.chat.id,
        token=token,
        source_message_id=message.message_id,
        source_message_date=message.date.isoformat(),
        kind=kind,
        text=text,
        voice_file_id=voice_file_id,
        voice_duration=voice_duration,
        voice_file_size=voice_file_size,
    )

    await state.set_data(data)
    await state.set_state(ReportFlow.choosing_task)

    await message.answer(
        formatting.format_pending_task_choice_text(tasks, today),
        reply_markup=formatting.pending_task_keyboard(tasks, token),
    )


async def _handle_unprompted_text(
    message: Message,
    state: FSMContext,
) -> None:
    """Route a plain private-chat message without a selected task.

    With exactly one assigned task the message is analysed for that
    task directly, so employees never have to use a command for their
    regular report. Several tasks keep the message in FSM data and ask
    for one tap on an inline task button; no task means there is
    nothing to report against.
    """

    text = (message.text or "").strip()

    if not text:
        return

    if text.startswith("/"):
        await message.answer(
            "Bu komut desteklenmiyor. Kullanılabilir komutlar için "
            "/help yazabilirsiniz."
        )
        return

    today = _today()

    async with SessionLocal() as session:
        employee = await get_active_employee_by_telegram_id(
            session,
            message.from_user.id,
        )

        if employee is None:
            await message.answer(formatting.REGISTER_GUIDANCE)
            return

        tasks = await list_my_tasks(session, employee.id, today)

    if not tasks:
        await message.answer(
            "Bu hafta için size atanmış bir görev bulunmuyor.\n\n"
            "Görev ataması yapıldığında buradan rapor "
            "gönderebilirsiniz."
        )
        return

    if len(tasks) > 1:
        await _start_pending_selection(
            message,
            state,
            tasks,
            kind=PENDING_KIND_TEXT,
            text=text,
        )
        return

    context = tasks[0]

    data = selection_data(
        context,
        telegram_user_id=message.from_user.id,
        chat_id=message.chat.id,
    )

    await _analyze_and_preview(
        message,
        state,
        data,
        context,
        text,
        today,
    )


async def _handle_report_text(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    if not data or data.get("task_id") is None:
        await state.clear()
        await message.answer(
            "Rapor akışı bulunamadı. "
            + formatting.RESTART_HINT
        )
        return

    if not _matches_flow(
        data,
        message.from_user.id,
        message.chat.id,
    ):
        await state.clear()
        await message.answer(
            "Bu rapor akışı size ait değil. "
            + formatting.RESTART_HINT
        )
        return

    text = message.text or ""

    if not text.strip():
        await message.answer(
            "Lütfen boş olmayan bir rapor metni gönderin."
        )
        return

    if text.strip().startswith("/"):
        await message.answer(
            "Komutlar rapor metni olarak işlenmez. Lütfen raporunuzu "
            "düz metin olarak yazın veya /gorevlerim komutunu "
            "kullanın."
        )
        return

    extractor = _extractor

    if extractor is None:
        await message.answer(
            "Yapay zekâ servisi henüz hazır değil. "
            "Lütfen daha sonra tekrar deneyin."
        )
        return

    today = _today()

    async with SessionLocal() as session:
        employee = await get_active_employee_by_telegram_id(
            session,
            message.from_user.id,
        )

        if employee is None:
            await state.clear()
            await message.answer(formatting.REGISTER_GUIDANCE)
            return

        try:
            context = await get_task_context(
                session,
                employee.id,
                data["task_id"],
                today,
            )
        except NotFoundError:
            await state.clear()
            await message.answer(
                "Görev atamanız bulunamadı veya kaldırıldı. "
                + formatting.RESTART_HINT
            )
            return

    await _analyze_and_preview(
        message,
        state,
        data,
        context,
        text,
        today,
    )


async def _analyze_and_preview(
    message: Message,
    state: FSMContext,
    data: dict,
    context,
    text: str,
    today: date,
) -> None:
    """Run the existing AI report pipeline and render the preview.

    Both an explicitly selected task and a message routed automatically
    to the employee's single task use this function, so there is only
    one analysis, draft and confirmation path.
    """

    extractor = _extractor

    if extractor is None:
        await message.answer(
            "Yapay zekâ servisi henüz hazır değil. "
            "Lütfen daha sonra tekrar deneyin."
        )
        return

    async with SessionLocal() as session:
        progress_baseline = None

        if context.weekly_plan is not None:
            progress_baseline = await get_progress_baseline(
                session,
                task_id=context.task_id,
                week_start_date=(
                    context.weekly_plan.week_start_date
                ),
                task_planned_start_date=(
                    context.planned_start_date
                ),
            )

    weekly_target = (
        context.weekly_plan.target_completion_percentage
        if context.weekly_plan is not None
        else None
    )

    # Refresh the plan snapshot so the preview reflects the current
    # database state, including a newly appearing conflict.
    data["task_title"] = context.title
    data["project_name"] = context.project_name
    data["plan"] = plan_to_data(context.weekly_plan)
    data["plan_conflict"] = context.plan_conflict
    await state.set_data(data)

    await message.answer("Mesajınız analiz ediliyor...")

    try:
        result = await extractor.extract(
            text,
            task_context=_extraction_context(context, today),
        )

        if isinstance(result, WorkUpdate):
            draft = result
        else:
            draft = WorkUpdate.model_validate(result)

        draft = clamp_ai_draft(draft)
        draft = apply_progress_scope(
            draft,
            baseline=progress_baseline,
            weekly_target=weekly_target,
        )

        if not draft.summary or not draft.summary.strip():
            raise ValueError("AI returned an empty summary.")

        if not _has_work_content(draft):
            await message.answer(
                "Mesajınızdan yeterli bir iş güncellemesi "
                "çıkaramadım. Hiçbir kayıt oluşturulmadı.\n\n"
                "Lütfen ne yaptığınızı, işin durumunu ve varsa "
                "ilerlemeyi kısaca yazın."
            )
            return

        eta_result = normalize_eta_date(
            draft.reported_eta_text,
            message.date,
        )

        token = secrets.token_hex(4)
        ai_model = getattr(extractor, "model", None)

        data.update(
            {
                "source_message_id": message.message_id,
                "source_message_date": message.date.isoformat(),
                "original_message": text,
                "draft": draft.model_dump(mode="json"),
                "progress_baseline": progress_baseline,
                "reported_eta_date": (
                    eta_result.normalized_date.isoformat()
                    if eta_result.normalized_date is not None
                    else None
                ),
                "ai_model": (
                    str(ai_model)[:100]
                    if ai_model is not None
                    else None
                ),
                "confirmation_token": token,
                "field_to_edit": None,
                "preview_message_id": None,
            }
        )

        # Render the preview before entering the reviewing state. If the
        # Telegram send fails, the employee stays in the report state and
        # can retry instead of being stuck with no preview buttons.
        sent = await message.answer(
            formatting.format_preview_text(data),
            reply_markup=formatting.preview_keyboard(token),
        )

        data["preview_message_id"] = getattr(
            sent,
            "message_id",
            None,
        )

        await state.set_data(data)
        await state.set_state(ReportFlow.reviewing)

    except Exception:
        # Never log or persist the employee's message content here.
        logger.exception("Report analysis failed.")
        await message.answer(
            "Raporunuz analiz edilemedi. Hiçbir kayıt "
            "oluşturulmadı.\n\nLütfen rapor metnini yeniden "
            "gönderin."
        )


def _voice_limit_message(voice) -> str | None:
    """Reject oversized voice messages before any download.

    Telegram reports the duration and the file size in the message
    metadata, so an unusable recording is rejected without fetching it.
    """

    duration = getattr(voice, "duration", None)

    if (
        isinstance(duration, int)
        and duration > MAX_VOICE_DURATION_SECONDS
    ):
        return formatting.voice_too_long_message(
            MAX_VOICE_DURATION_SECONDS
        )

    file_size = getattr(voice, "file_size", None)

    if (
        isinstance(file_size, int)
        and file_size > MAX_VOICE_FILE_SIZE_BYTES
    ):
        return formatting.voice_too_large_message(
            MAX_VOICE_FILE_SIZE_BYTES
        )

    return None


async def _download_voice(message: Message) -> bytes | None:
    """Read the voice message into memory; never store it on disk."""

    try:
        buffer = await message.bot.download(message.voice)
    except Exception:
        logger.exception("Could not download the voice message.")
        await message.answer(formatting.VOICE_DOWNLOAD_FAILED)
        return None

    if buffer is None:
        await message.answer(formatting.VOICE_DOWNLOAD_FAILED)
        return None

    if hasattr(buffer, "getvalue"):
        audio = buffer.getvalue()
    else:
        audio = bytes(buffer)

    if not audio:
        await message.answer(formatting.VOICE_EMPTY_FILE)
        return None

    if len(audio) > MAX_VOICE_FILE_SIZE_BYTES:
        await message.answer(
            formatting.voice_too_large_message(
                MAX_VOICE_FILE_SIZE_BYTES
            )
        )
        return None

    return audio


async def _transcribe_voice(message: Message) -> str | None:
    """Transcribe a voice message into the employee's own words.

    The original audio is discarded after the transcript is produced. An
    empty or failed transcript returns ``None`` so nothing is saved.
    """

    limit_message = _voice_limit_message(message.voice)

    if limit_message is not None:
        await message.answer(limit_message)
        return None

    transcriber = _transcriber

    if transcriber is None:
        await message.answer(formatting.VOICE_NOT_READY)
        return None

    audio = await _download_voice(message)

    if audio is None:
        return None

    await message.answer(formatting.VOICE_TRANSCRIBING)

    try:
        transcript = await transcriber.transcribe(
            audio,
            mime_type=VOICE_MIME_TYPE,
        )
    except Exception:
        # Never log the audio content or the transcript.
        logger.exception("Voice transcription failed.")
        await message.answer(formatting.VOICE_TRANSCRIPTION_FAILED)
        return None

    transcript = (transcript or "").strip()

    if not transcript:
        await message.answer(formatting.VOICE_TRANSCRIPT_EMPTY)
        return None

    return transcript


async def _transcribe_and_preview(
    message: Message,
    state: FSMContext,
    data: dict,
    context,
    today: date,
) -> None:
    """Feed a voice transcript into the existing report pipeline.

    After transcription the text path is used unchanged, so the task
    context, weekly plan, scope conversion, ETA normalization, preview
    and confirmation all behave exactly like a typed report.
    """

    transcript = await _transcribe_voice(message)

    if transcript is None:
        return

    await _analyze_and_preview(
        message,
        state,
        data,
        context,
        transcript,
        today,
    )


async def _handle_report_voice(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    if not data or data.get("task_id") is None:
        await state.clear()
        await message.answer(
            "Rapor akışı bulunamadı. "
            + formatting.RESTART_HINT
        )
        return

    if not _matches_flow(
        data,
        message.from_user.id,
        message.chat.id,
    ):
        await state.clear()
        await message.answer(
            "Bu rapor akışı size ait değil. "
            + formatting.RESTART_HINT
        )
        return

    today = _today()

    async with SessionLocal() as session:
        employee = await get_active_employee_by_telegram_id(
            session,
            message.from_user.id,
        )

        if employee is None:
            await state.clear()
            await message.answer(formatting.REGISTER_GUIDANCE)
            return

        try:
            context = await get_task_context(
                session,
                employee.id,
                data["task_id"],
                today,
            )
        except NotFoundError:
            await state.clear()
            await message.answer(
                "Görev atamanız bulunamadı veya kaldırıldı. "
                + formatting.RESTART_HINT
            )
            return

    await _transcribe_and_preview(
        message,
        state,
        data,
        context,
        today,
    )


async def _handle_unprompted_voice(
    message: Message,
    state: FSMContext,
) -> None:
    """Route a voice message sent without a selected task.

    The same rules as plain text apply: a single assigned task is chosen
    automatically, several tasks keep the voice file id and ask for one
    tap on an inline task button, and no task means there is nothing to
    report against.
    """

    today = _today()

    async with SessionLocal() as session:
        employee = await get_active_employee_by_telegram_id(
            session,
            message.from_user.id,
        )

        if employee is None:
            await message.answer(formatting.REGISTER_GUIDANCE)
            return

        tasks = await list_my_tasks(session, employee.id, today)

    if not tasks:
        await message.answer(
            "Bu hafta için size atanmış bir görev bulunmuyor.\n\n"
            "Görev ataması yapıldığında buradan rapor "
            "gönderebilirsiniz."
        )
        return

    if len(tasks) > 1:
        await _start_pending_selection(
            message,
            state,
            tasks,
            kind=PENDING_KIND_VOICE,
        )
        return

    context = tasks[0]

    data = selection_data(
        context,
        telegram_user_id=message.from_user.id,
        chat_id=message.chat.id,
    )

    await _transcribe_and_preview(
        message,
        state,
        data,
        context,
        today,
    )


async def _handle_field_edit_text(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    if not data or not _matches_flow(
        data,
        message.from_user.id,
        message.chat.id,
    ):
        await state.clear()
        await message.answer(
            "Düzenleme oturumu bulunamadı. "
            + formatting.RESTART_HINT
        )
        return

    field = data.get("field_to_edit")

    if not field or field not in EDITABLE_FIELDS:
        await message.answer(
            "Lütfen düzenlemek istediğiniz alanı "
            "butonlardan seçin."
        )
        return

    spec = EDITABLE_FIELDS[field]

    if spec.kind == "status":
        await message.answer(
            "Durum için lütfen yukarıdaki butonlardan "
            "birini seçin."
        )
        return

    if (
        data.get("draft") is None
        or data.get("source_message_date") is None
    ):
        await state.clear()
        await message.answer(
            "Taslak bilgisi bulunamadı. "
            + formatting.RESTART_HINT
        )
        return

    reference_datetime = datetime.fromisoformat(
        data["source_message_date"]
    )

    current_eta_date = (
        date.fromisoformat(data["reported_eta_date"])
        if data.get("reported_eta_date")
        else None
    )

    outcome = apply_edit(
        draft_data=data["draft"],
        field=field,
        raw_value=message.text,
        reference_datetime=reference_datetime,
        current_eta_date=current_eta_date,
    )

    if outcome.error is not None:
        await message.answer(outcome.error)
        return

    data["draft"] = outcome.draft
    data["reported_eta_date"] = (
        outcome.eta_date.isoformat()
        if outcome.eta_date is not None
        else None
    )
    data["field_to_edit"] = None
    # A changed draft must not be confirmable through a button that was
    # rendered for the previous version.
    data["confirmation_token"] = secrets.token_hex(4)

    await state.set_data(data)
    await state.set_state(ReportFlow.reviewing)

    # The updated report is delivered as a new message at the end of
    # the chat, with a keyboard built from the rotated token.
    await _send_fresh_preview(message, state, data)


@router.callback_query(F.data == "rep:edit")
async def edit_menu_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not _callback_allowed(callback):
        await _reject_non_private(callback)
        return

    data = await state.get_data()

    if not data or not _matches_flow(
        data,
        callback.from_user.id,
        callback.message.chat.id,
    ):
        await state.clear()
        await callback.answer(
            "Düzenleme oturumu bulunamadı. "
            + formatting.RESTART_HINT,
            show_alert=True,
        )
        return

    if not _state_is(
        await state.get_state(),
        ReportFlow.reviewing,
    ):
        await callback.answer(
            "Düzenlenecek bir rapor önizlemesi yok.",
            show_alert=True,
        )
        return

    data["field_to_edit"] = None
    await state.set_data(data)
    await state.set_state(ReportFlow.waiting_for_field_edit)

    await callback.message.answer(
        "Hangi bilgiyi düzenlemek istiyorsunuz?",
        reply_markup=formatting.edit_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rep:field:"))
async def edit_field_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not _callback_allowed(callback):
        await _reject_non_private(callback)
        return

    data = await state.get_data()

    if not data or not _matches_flow(
        data,
        callback.from_user.id,
        callback.message.chat.id,
    ):
        await state.clear()
        await callback.answer(
            "Düzenleme oturumu bulunamadı. "
            + formatting.RESTART_HINT,
            show_alert=True,
        )
        return

    if not _state_is(
        await state.get_state(),
        ReportFlow.waiting_for_field_edit,
    ):
        await callback.answer(
            "Bu düzenleme bağlantısı artık geçerli değil.",
            show_alert=True,
        )
        return

    field = (callback.data or "").split(":", 2)[-1]
    spec = EDITABLE_FIELDS.get(field)

    if spec is None:
        await callback.answer(
            "Bu alan düzenlenemiyor.",
            show_alert=True,
        )
        return

    data["field_to_edit"] = field
    await state.set_data(data)

    if spec.kind == "status":
        await callback.message.answer(
            formatting.format_field_prompt(spec),
            reply_markup=formatting.status_keyboard(),
        )
    else:
        await callback.message.answer(
            formatting.format_field_prompt(spec)
        )

    await callback.answer()


@router.callback_query(F.data.startswith("rep:status:"))
async def edit_status_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not _callback_allowed(callback):
        await _reject_non_private(callback)
        return

    data = await state.get_data()

    if not data or not _matches_flow(
        data,
        callback.from_user.id,
        callback.message.chat.id,
    ):
        await state.clear()
        await callback.answer(
            "Düzenleme oturumu bulunamadı. "
            + formatting.RESTART_HINT,
            show_alert=True,
        )
        return

    if (
        not _state_is(
            await state.get_state(),
            ReportFlow.waiting_for_field_edit,
        )
        or data.get("field_to_edit") != "status"
    ):
        await callback.answer(
            "Bu durum seçimi artık geçerli değil.",
            show_alert=True,
        )
        return

    if (
        data.get("draft") is None
        or data.get("source_message_date") is None
    ):
        await state.clear()
        await callback.answer(
            "Taslak bilgisi bulunamadı. "
            + formatting.RESTART_HINT,
            show_alert=True,
        )
        return

    reference_datetime = datetime.fromisoformat(
        data["source_message_date"]
    )

    current_eta_date = (
        date.fromisoformat(data["reported_eta_date"])
        if data.get("reported_eta_date")
        else None
    )

    status_value = (callback.data or "").split(":", 2)[-1]

    outcome = apply_edit(
        draft_data=data["draft"],
        field="status",
        raw_value=status_value,
        reference_datetime=reference_datetime,
        current_eta_date=current_eta_date,
    )

    if outcome.error is not None:
        await callback.answer(
            outcome.error,
            show_alert=True,
        )
        return

    data["draft"] = outcome.draft
    data["reported_eta_date"] = (
        outcome.eta_date.isoformat()
        if outcome.eta_date is not None
        else None
    )
    data["field_to_edit"] = None
    # Invalidate any button rendered for the previous draft version.
    data["confirmation_token"] = secrets.token_hex(4)

    await state.set_data(data)
    await state.set_state(ReportFlow.reviewing)

    sent = await _send_fresh_preview(callback.message, state, data)

    if sent:
        await callback.answer("Durum güncellendi.")
    else:
        await callback.answer(
            "Önizleme güncellenemedi.",
            show_alert=True,
        )


@router.callback_query(F.data == "rep:back")
async def back_to_preview_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not _callback_allowed(callback):
        await _reject_non_private(callback)
        return

    data = await state.get_data()

    if not data or not _matches_flow(
        data,
        callback.from_user.id,
        callback.message.chat.id,
    ):
        await state.clear()
        await callback.answer(
            "Düzenleme oturumu bulunamadı. "
            + formatting.RESTART_HINT,
            show_alert=True,
        )
        return

    if not _state_is(
        await state.get_state(),
        ReportFlow.waiting_for_field_edit,
    ):
        await callback.answer(
            "Bu işlem artık geçerli değil.",
            show_alert=True,
        )
        return

    data["field_to_edit"] = None
    await state.set_data(data)
    await state.set_state(ReportFlow.reviewing)

    sent = await _send_fresh_preview(callback.message, state, data)

    if sent:
        await callback.answer()
    else:
        await callback.answer(
            "Önizleme güncellenemedi.",
            show_alert=True,
        )


@router.callback_query(F.data == "rep:cancel")
async def cancel_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not _callback_allowed(callback):
        await _reject_non_private(callback)
        return

    data = await state.get_data()

    if not data or not _matches_flow(
        data,
        callback.from_user.id,
        callback.message.chat.id,
    ):
        await state.clear()
        await callback.answer(
            "İptal edilecek bir rapor taslağı bulunamadı.",
            show_alert=True,
        )
        return

    await _clear_and_replace(
        callback,
        state,
        data,
        "Rapor iptal edildi. Hiçbir kayıt oluşturulmadı.\n\n"
        + formatting.RESTART_HINT,
    )

    await callback.answer("Rapor iptal edildi.")


@router.callback_query(F.data.startswith("rep:confirm:"))
async def confirm_handler(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not _callback_allowed(callback):
        await _reject_non_private(callback)
        return

    data = await state.get_data()

    if not data or not _matches_flow(
        data,
        callback.from_user.id,
        callback.message.chat.id,
    ):
        await state.clear()
        await callback.answer(
            "Onay oturumu bulunamadı veya size ait değil. "
            + formatting.RESTART_HINT,
            show_alert=True,
        )
        return

    if not _state_is(
        await state.get_state(),
        ReportFlow.reviewing,
    ):
        await callback.answer(
            "Bu onay artık geçerli değil.",
            show_alert=True,
        )
        return

    token = (callback.data or "").split(":", 2)[-1]
    expected_token = data.get("confirmation_token") or ""

    if (
        not expected_token
        or not token
        or not secrets.compare_digest(token, expected_token)
    ):
        await callback.answer(
            "Onay bağlantısı geçersiz veya eski. "
            "Lütfen güncel önizlemeyi kullanın.",
            show_alert=True,
        )
        return

    if (
        data.get("task_id") is None
        or data.get("draft") is None
        or data.get("source_message_id") is None
        or data.get("source_message_date") is None
        or data.get("original_message") is None
    ):
        await _clear_and_replace(
            callback,
            state,
            data,
            "Rapor taslağı bulunamadı. "
            + formatting.RESTART_HINT,
        )
        await callback.answer(
            "Taslak bilgisi eksik.",
            show_alert=True,
        )
        return

    today = _today()

    async with SessionLocal() as session:
        employee = await get_active_employee_by_telegram_id(
            session,
            callback.from_user.id,
        )

        if employee is None:
            await _clear_and_replace(
                callback,
                state,
                data,
                "Aktif çalışan kaydınız bulunamadı; rapor "
                "kaydedilmedi.\n\n"
                + formatting.REGISTER_GUIDANCE,
            )
            await callback.answer(
                "Aktif çalışan kaydı bulunamadı.",
                show_alert=True,
            )
            return

        try:
            context = await get_task_context(
                session,
                employee.id,
                data["task_id"],
                today,
            )
        except NotFoundError:
            await _clear_and_replace(
                callback,
                state,
                data,
                "Görev atamanız artık bulunmuyor; rapor "
                "kaydedilmedi.\n\n"
                + formatting.RESTART_HINT,
            )
            await callback.answer(
                "Görev ataması bulunamadı.",
                show_alert=True,
            )
            return

        if not context_matches_selection(data, context):
            await _clear_and_replace(
                callback,
                state,
                data,
                "Haftalık plan bilgisi önizleme "
                "oluşturulduktan sonra değişti. Eski "
                "önizleme kaydedilmedi.\n\n"
                + formatting.RESTART_HINT,
            )
            await callback.answer(
                "Haftalık plan değişti; akışı yeniden başlatın.",
                show_alert=True,
            )
            return

        source_datetime = datetime.fromisoformat(
            data["source_message_date"]
        )

        try:
            draft = draft_from_data(data["draft"])

            eta_result = normalize_eta_date(
                draft.reported_eta_text,
                source_datetime,
            )

            await create_task_update(
                session,
                telegram_user_id=callback.from_user.id,
                telegram_chat_id=data["chat_id"],
                telegram_message_id=data["source_message_id"],
                task_id=context.task_id,
                original_message=data["original_message"],
                draft=draft,
                weekly_plan_id=(
                    context.weekly_plan.id
                    if context.weekly_plan is not None
                    else None
                ),
                reported_eta_date=eta_result.normalized_date,
                ai_model=data.get("ai_model"),
                today=today,
            )

            await session.commit()

        except ConflictError:
            await session.rollback()
            await _clear_and_replace(
                callback,
                state,
                data,
                "Bu rapor daha önce kaydedilmiş olabilir. "
                "İkinci bir kayıt oluşturulmadı.\n\n"
                + formatting.RESTART_HINT,
            )
            await callback.answer(
                "Rapor daha önce kaydedilmiş.",
                show_alert=True,
            )
            return

        except (NotFoundError, ServiceValidationError) as exc:
            await session.rollback()
            await _clear_and_replace(
                callback,
                state,
                data,
                "Rapor kaydedilemedi: "
                + str(exc)
                + "\n\n"
                + formatting.RESTART_HINT,
            )
            await callback.answer(
                "Rapor kaydedilemedi.",
                show_alert=True,
            )
            return

        except PydanticValidationError:
            await session.rollback()
            await _clear_and_replace(
                callback,
                state,
                data,
                "Rapor bilgileri geçersiz; kayıt "
                "oluşturulmadı.\n\n"
                + formatting.RESTART_HINT,
            )
            await callback.answer(
                "Geçersiz rapor taslağı.",
                show_alert=True,
            )
            return

        except Exception:
            await session.rollback()
            logger.exception("Could not persist the confirmed report.")
            await _clear_and_replace(
                callback,
                state,
                data,
                "Rapor kaydedilirken bir hata oluştu. "
                "Lütfen tekrar deneyin.",
            )
            await callback.answer(
                "Kayıt sırasında hata oluştu.",
                show_alert=True,
            )
            return

    success_text = (
        "Raporunuz kaydedildi.\n\n"
        f"Görev: {data.get('task_title') or 'Belirtilmedi'}\n"
        "Durum: Yönetici raporlarında görüntülenebilir.\n\n"
        "Yeni bir rapor için /gorevlerim komutunu "
        "kullanabilirsiniz."
    )

    await _clear_and_replace(
        callback,
        state,
        data,
        success_text,
    )
    await callback.answer("Rapor kaydedildi.")


@router.message(F.voice)
async def report_voice_handler(
    message: Message,
    state: FSMContext,
) -> None:
    """Accept a voice note exactly where a text report is accepted."""

    if message.from_user is None:
        return

    if message.chat.type != "private":
        await message.answer(formatting.PRIVATE_ONLY)
        return

    current = await state.get_state()

    if _state_is(current, ReportFlow.choosing_task):
        # A pending report must not be silently replaced.
        await message.answer(formatting.PENDING_INPUT_GUIDANCE)
        return

    if _state_is(current, ReportFlow.waiting_for_report):
        await _handle_report_voice(message, state)
        return

    if _state_is(current, ReportFlow.waiting_for_field_edit):
        # Field edits stay text-only; the running edit flow is untouched.
        await message.answer(formatting.VOICE_EDIT_GUIDANCE)
        return

    if _state_is(current, ReportFlow.reviewing):
        await message.answer(formatting.VOICE_REVIEW_GUIDANCE)
        return

    # Registration and any other FSM flow must not be interrupted.
    if current is not None:
        return

    await _handle_unprompted_voice(message, state)


@router.message()
async def unsupported_message_handler(
    message: Message,
    state: FSMContext,
) -> None:
    if (
        getattr(message, "audio", None) is not None
        or getattr(message, "video_note", None) is not None
    ):
        await message.answer(formatting.VOICE_ATTACHMENT_UNSUPPORTED)
        return

    if message.chat.type != "private":
        return

    await message.answer(
        "Şimdilik yalnızca metin ve sesli mesajları "
        "destekliyorum. Rapor göndermek için /gorevlerim "
        "komutunu kullanın."
    )


def register_report_handlers(dispatcher) -> None:
    """Include the employee report router after existing handlers."""

    dispatcher.include_router(router)
