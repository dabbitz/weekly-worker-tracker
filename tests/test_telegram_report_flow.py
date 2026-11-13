from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, func, select, update

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot import formatting, handlers
from app.bot.drafts import apply_edit, draft_to_data
from app.bot.states import ReportFlow
from app.database.models import (
    Employee,
    TaskAssignment,
    TaskUpdate,
    WeeklyTaskPlan,
)
from app.schemas.work_update import WorkUpdate
from tests.test_employee_work_reports import (
    TODAY,
    seed_plan,
    seed_task,
)
from tests.test_employees_tasks import seed_employee


WEEK_END = date(2026, 11, 22)
EXPECTED_ETA = date(2026, 11, 20)  # Friday
REPORT_TEXT = (
    "Elektrik tesisatının %70'ini tamamladım. Pano bağlantıları "
    "kaldı, cuma gününe kadar bitecek."
)
REFERENCE_DATETIME = datetime(
    2026,
    11,
    16,
    9,
    0,
    tzinfo=timezone.utc,
)


class FakeBot:
    def __init__(self):
        self.edits = []
        self.sent = []
        self._next_id = 1000

    def next_message_id(self) -> int:
        self._next_id += 1
        return self._next_id

    async def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)
        return True

    async def send_message(self, **kwargs):
        self.sent.append(kwargs)
        return FakeMessage(
            bot=self,
            chat_id=kwargs["chat_id"],
            user_id=0,
            message_id=self.next_message_id(),
        )


class FakeChat:
    def __init__(self, chat_id: int, chat_type: str = "private"):
        self.id = chat_id
        self.type = chat_type


class FakeUser:
    def __init__(self, user_id: int):
        self.id = user_id


class FakeMessage:
    def __init__(
        self,
        *,
        bot: FakeBot,
        chat_id: int,
        user_id: int,
        text: str | None = None,
        message_id: int | None = None,
        date_value: datetime | None = None,
        chat_type: str = "private",
    ):
        self.bot = bot
        self.chat = FakeChat(chat_id, chat_type)
        self.from_user = FakeUser(user_id)
        self.text = text
        self.message_id = (
            message_id
            if message_id is not None
            else bot.next_message_id()
        )
        self.date = date_value or REFERENCE_DATETIME
        self.voice = None
        self.audio = None
        self.video_note = None
        self.answers = []

    async def answer(self, text, reply_markup=None, **kwargs):
        self.answers.append(
            {"text": text, "reply_markup": reply_markup}
        )
        return FakeMessage(
            bot=self.bot,
            chat_id=self.chat.id,
            user_id=self.from_user.id,
            message_id=self.bot.next_message_id(),
            chat_type=self.chat.type,
        )

    async def edit_text(self, text, reply_markup=None, **kwargs):
        self.answers.append(
            {"text": text, "reply_markup": reply_markup}
        )
        return True


class FakeCallback:
    def __init__(
        self,
        *,
        bot: FakeBot,
        data: str,
        user_id: int,
        chat_id: int,
        message_id: int = 900,
        chat_type: str = "private",
    ):
        self.bot = bot
        self.data = data
        self.from_user = FakeUser(user_id)
        self.message = FakeMessage(
            bot=bot,
            chat_id=chat_id,
            user_id=user_id,
            message_id=message_id,
            chat_type=chat_type,
        )
        self.answers = []

    async def answer(
        self,
        text=None,
        show_alert=False,
        **kwargs,
    ):
        self.answers.append(
            {"text": text, "show_alert": show_alert}
        )
        return True


class FakeExtractor:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.model = "fake-model"
        self.calls = []

    async def extract(self, text):
        self.calls.append(text)
        if self.error is not None:
            raise self.error
        return self.result


def make_draft(**overrides) -> WorkUpdate:
    data = {
        "task_reference_text": "Elektrik tesisatı",
        "status": "in_progress",
        "completion_percentage": 70,
        "blocker": None,
        "delay_reason": None,
        "next_step": "Pano bağlantılarını tamamla",
        "reported_eta_text": "cuma gününe kadar",
        "summary": "İşin %70'i tamamlandı.",
    }
    data.update(overrides)
    return WorkUpdate.model_validate(data)


async def make_state(user_id: int, chat_id: int | None = None):
    storage = MemoryStorage()
    key = StorageKey(
        bot_id=4242,
        chat_id=chat_id if chat_id is not None else user_id,
        user_id=user_id,
    )
    return FSMContext(storage=storage, key=key)


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(
        "app.bot.handlers._today",
        lambda: TODAY,
    )


@pytest.fixture(autouse=True)
def bot_session(database, monkeypatch):
    monkeypatch.setattr(
        "app.bot.handlers.SessionLocal",
        database.sessionmaker,
    )
    yield
    handlers.set_extractor(None)


async def setup_flow(
    session,
    bot,
    state,
    *,
    telegram_id: int = 7001,
    title: str = "Elektrik tesisatı",
    project_name: str = "Rapor Projesi",
    with_plan: bool = True,
    plan_percentage: int = 40,
    employee_id: int | None = None,
) -> tuple[int, int, int | None]:
    if employee_id is None:
        employee_id = await seed_employee(
            session,
            f"Çalışan {telegram_id}",
            telegram_user_id=telegram_id,
        )

    _, task_id = await seed_task(
        session,
        title=title,
        project_name=project_name,
        employee_ids=(employee_id,),
    )

    plan_id = None

    if with_plan:
        plan_id = await seed_plan(
            session,
            task_id,
            TODAY,
            WEEK_END,
            percentage=plan_percentage,
            description="Kabloları döşe",
        )

    callback = FakeCallback(
        bot=bot,
        data=f"task:{task_id}",
        user_id=telegram_id,
        chat_id=telegram_id,
    )

    await handlers.task_selection_handler(callback, state)

    assert await state.get_state() == (
        ReportFlow.waiting_for_report.state
    )

    return employee_id, task_id, plan_id


async def submit_report(
    bot,
    state,
    *,
    telegram_id: int = 7001,
    text: str = REPORT_TEXT,
    message_id: int = 500,
):
    message = FakeMessage(
        bot=bot,
        chat_id=telegram_id,
        user_id=telegram_id,
        text=text,
        message_id=message_id,
    )
    await handlers.report_text_handler(message, state)
    return message


async def count_updates(session) -> int:
    await session.rollback()
    return await session.scalar(
        select(func.count(TaskUpdate.id))
    )


async def test_gorevlerim_lists_assigned_task_with_approved_plan(
    session,
):
    telegram_id = 7001
    employee_id = await seed_employee(
        session,
        "Aktif Çalışan",
        telegram_user_id=telegram_id,
    )
    _, task_id = await seed_task(
        session,
        title="Elektrik tesisatı",
        project_name="Rapor Projesi",
        employee_ids=(employee_id,),
    )
    await seed_plan(
        session,
        task_id,
        TODAY,
        WEEK_END,
        percentage=40,
        description="Kabloları döşe",
    )

    bot = FakeBot()
    state = await make_state(telegram_id)
    message = FakeMessage(
        bot=bot,
        chat_id=telegram_id,
        user_id=telegram_id,
    )

    await handlers.gorevlerim_handler(message, state)

    text = message.answers[-1]["text"]
    assert "Elektrik tesisatı" in text
    assert "Rapor Projesi" in text
    assert "Kabloları döşe" in text
    assert "%40" in text
    assert "16.11.2026 - 22.11.2026" in text

    markup = message.answers[-1]["reply_markup"]
    callbacks = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
    ]
    assert f"task:{task_id}" in callbacks

    # /rapor is an alias for the same command.
    alias_message = FakeMessage(
        bot=bot,
        chat_id=telegram_id,
        user_id=telegram_id,
    )
    await handlers.gorevlerim_handler(alias_message, state)
    assert "Elektrik tesisatı" in alias_message.answers[-1]["text"]


async def test_unregistered_and_inactive_cannot_enter_report_flow(
    session,
):
    await seed_employee(
        session,
        "Pasif Çalışan",
        is_active=False,
        telegram_user_id=7002,
    )
    await seed_employee(
        session,
        "Görevsiz Çalışan",
        telegram_user_id=7000,
    )

    bot = FakeBot()
    extractor = FakeExtractor(make_draft())
    handlers.set_extractor(extractor)

    no_task_state = await make_state(7000)
    no_task_message = FakeMessage(
        bot=bot,
        chat_id=7000,
        user_id=7000,
    )
    await handlers.gorevlerim_handler(no_task_message, no_task_state)
    assert "atanmış bir görev bulunmuyor" in (
        no_task_message.answers[-1]["text"]
    )

    for telegram_id in (7002, 7999):
        state = await make_state(telegram_id)

        list_message = FakeMessage(
            bot=bot,
            chat_id=telegram_id,
            user_id=telegram_id,
        )
        await handlers.gorevlerim_handler(list_message, state)

        assert "/register" in list_message.answers[-1]["text"]

        text_message = FakeMessage(
            bot=bot,
            chat_id=telegram_id,
            user_id=telegram_id,
            text="Bugün çalıştım.",
        )
        await handlers.report_text_handler(text_message, state)

        assert "/register" in text_message.answers[-1]["text"]
        assert await state.get_state() is None

    assert extractor.calls == []


async def test_group_chat_actions_are_rejected(session):
    telegram_id = 7003
    await seed_employee(
        session,
        "Grup Çalışanı",
        telegram_user_id=telegram_id,
    )

    bot = FakeBot()
    state = await make_state(telegram_id, chat_id=-100123)

    list_message = FakeMessage(
        bot=bot,
        chat_id=-100123,
        user_id=telegram_id,
        chat_type="group",
    )
    await handlers.gorevlerim_handler(list_message, state)

    assert formatting.PRIVATE_ONLY in list_message.answers[-1]["text"]

    text_message = FakeMessage(
        bot=bot,
        chat_id=-100123,
        user_id=telegram_id,
        chat_type="group",
        text="Rapor",
    )
    await handlers.report_text_handler(text_message, state)

    assert formatting.PRIVATE_ONLY in text_message.answers[-1]["text"]

    callback = FakeCallback(
        bot=bot,
        data="task:1",
        user_id=telegram_id,
        chat_id=-100123,
        chat_type="group",
    )
    await handlers.task_selection_handler(callback, state)

    assert callback.answers[-1]["show_alert"] is True
    assert await state.get_state() is None


async def test_task_without_plan_is_listed_and_reportable(session):
    telegram_id = 7004
    employee_id = await seed_employee(
        session,
        "Plansız Çalışan",
        telegram_user_id=telegram_id,
    )
    _, task_id = await seed_task(
        session,
        title="Plansız görev",
        employee_ids=(employee_id,),
    )

    bot = FakeBot()
    state = await make_state(telegram_id)

    list_message = FakeMessage(
        bot=bot,
        chat_id=telegram_id,
        user_id=telegram_id,
    )
    await handlers.gorevlerim_handler(list_message, state)

    assert formatting.NO_PLAN_NOTE in list_message.answers[-1]["text"]

    markup = list_message.answers[-1]["reply_markup"]
    callbacks = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
    ]
    assert f"task:{task_id}" in callbacks

    selection = await state.get_data()
    assert selection == {}

    callback = FakeCallback(
        bot=bot,
        data=f"task:{task_id}",
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    await handlers.task_selection_handler(callback, state)

    data = await state.get_data()
    assert data["plan"] is None
    assert data["plan_conflict"] is False

    handlers.set_extractor(FakeExtractor(make_draft()))
    await submit_report(bot, state, telegram_id=telegram_id)

    confirm = FakeCallback(
        bot=bot,
        data=(
            "rep:confirm:"
            + (await state.get_data())["confirmation_token"]
        ),
        user_id=telegram_id,
        chat_id=telegram_id,
        message_id=900,
    )
    await handlers.confirm_handler(confirm, state)

    assert await count_updates(session) == 1

    await session.rollback()
    update_row = await session.scalar(select(TaskUpdate))

    assert update_row.weekly_plan_id is None


async def test_conflicting_plans_are_flagged_and_not_attached(
    session,
):
    telegram_id = 7005
    employee_id = await seed_employee(
        session,
        "Çakışan Plan Çalışanı",
        telegram_user_id=telegram_id,
    )
    _, task_id = await seed_task(
        session,
        title="Çakışan plan görevi",
        employee_ids=(employee_id,),
    )
    await seed_plan(
        session,
        task_id,
        TODAY - timedelta(days=1),
        date(2026, 11, 21),
        percentage=40,
        description="Birinci hedef",
    )
    await seed_plan(
        session,
        task_id,
        TODAY,
        WEEK_END,
        percentage=80,
        description="İkinci hedef",
    )

    bot = FakeBot()
    state = await make_state(telegram_id)

    list_message = FakeMessage(
        bot=bot,
        chat_id=telegram_id,
        user_id=telegram_id,
    )
    await handlers.gorevlerim_handler(list_message, state)

    text = list_message.answers[-1]["text"]
    assert formatting.CONFLICT_NOTE in text
    assert "Birinci hedef" not in text
    assert "İkinci hedef" not in text

    callback = FakeCallback(
        bot=bot,
        data=f"task:{task_id}",
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    await handlers.task_selection_handler(callback, state)

    data = await state.get_data()
    assert data["plan"] is None
    assert data["plan_conflict"] is True

    handlers.set_extractor(FakeExtractor(make_draft()))
    await submit_report(bot, state, telegram_id=telegram_id)

    confirm = FakeCallback(
        bot=bot,
        data=(
            "rep:confirm:"
            + (await state.get_data())["confirmation_token"]
        ),
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    await handlers.confirm_handler(confirm, state)

    assert await count_updates(session) == 1

    await session.rollback()
    update_row = await session.scalar(select(TaskUpdate))
    assert update_row.weekly_plan_id is None


async def test_unassigned_task_callback_is_rejected(session):
    telegram_id = 7006
    other_telegram_id = 7007

    await seed_employee(
        session,
        "Asıl Çalışan",
        telegram_user_id=telegram_id,
    )
    other_id = await seed_employee(
        session,
        "Diğer Çalışan",
        telegram_user_id=other_telegram_id,
    )
    _, other_task_id = await seed_task(
        session,
        title="Başkasının görevi",
        employee_ids=(other_id,),
    )

    bot = FakeBot()
    state = await make_state(telegram_id)

    callback = FakeCallback(
        bot=bot,
        data=f"task:{other_task_id}",
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    await handlers.task_selection_handler(callback, state)

    assert callback.answers[-1]["show_alert"] is True
    assert await state.get_state() is None


async def test_free_text_only_processed_in_report_state(session):
    telegram_id = 7010
    employee_id = await seed_employee(
        session,
        "Serbest Metin Çalışanı",
        telegram_user_id=telegram_id,
    )

    bot = FakeBot()
    state = await make_state(telegram_id)
    extractor = FakeExtractor(make_draft())
    handlers.set_extractor(extractor)

    message = FakeMessage(
        bot=bot,
        chat_id=telegram_id,
        user_id=telegram_id,
        text="Merhaba, bugün ne yapacağım?",
    )
    await handlers.report_text_handler(message, state)

    assert "/gorevlerim" in message.answers[-1]["text"]
    assert extractor.calls == []

    voice_message = FakeMessage(
        bot=bot,
        chat_id=telegram_id,
        user_id=telegram_id,
    )
    voice_message.voice = object()
    await handlers.unsupported_message_handler(
        voice_message,
        state,
    )
    assert "Sesli raporlama" in voice_message.answers[-1]["text"]

    await setup_flow(
        session,
        bot,
        state,
        telegram_id=telegram_id,
        employee_id=employee_id,
    )

    empty_message = FakeMessage(
        bot=bot,
        chat_id=telegram_id,
        user_id=telegram_id,
        text="   ",
        message_id=499,
    )
    await handlers.report_text_handler(empty_message, state)

    assert "boş olmayan" in empty_message.answers[-1]["text"]
    assert extractor.calls == []

    report_message = await submit_report(
        bot,
        state,
        telegram_id=telegram_id,
    )

    assert extractor.calls == [REPORT_TEXT]
    assert "ÖNİZLEMESİ" in report_message.answers[-1]["text"]

    # A lost FSM draft must ask the employee to restart.
    await state.set_state(ReportFlow.waiting_for_report)
    await state.set_data({})

    lost_message = FakeMessage(
        bot=bot,
        chat_id=telegram_id,
        user_id=telegram_id,
        text="Rapor",
        message_id=503,
    )
    await handlers.report_text_handler(lost_message, state)

    assert "Rapor akışı bulunamadı" in lost_message.answers[-1]["text"]
    assert "/gorevlerim" in lost_message.answers[-1]["text"]
    assert await state.get_state() is None


async def test_ai_preview_is_not_persisted(session):
    telegram_id = 7011
    bot = FakeBot()
    state = await make_state(telegram_id)

    await setup_flow(session, bot, state, telegram_id=telegram_id)

    handlers.set_extractor(FakeExtractor(make_draft()))

    report_message = await submit_report(
        bot,
        state,
        telegram_id=telegram_id,
    )

    data = await state.get_data()
    preview_text = report_message.answers[-1]["text"]

    assert await state.get_state() == ReportFlow.reviewing.state
    assert data["source_message_id"] == 500
    assert data["draft"]["status"] == "in_progress"
    assert data["draft"]["completion_percentage"] == 70
    assert data["reported_eta_date"] == EXPECTED_ETA.isoformat()

    assert "ÇALIŞANIN MESAJI" in preview_text
    assert REPORT_TEXT in preview_text
    assert "AI ANALİZİ" in preview_text
    assert "HAFTALIK HEDEF VE GERÇEKLEŞEN İLERLEME" in preview_text
    assert "%40" in preview_text
    assert "%70" in preview_text

    assert await count_updates(session) == 0

    markup = report_message.answers[-1]["reply_markup"]
    buttons = [
        button
        for row in markup.inline_keyboard
        for button in row
    ]
    callback_values = [button.callback_data for button in buttons]
    assert all(len(value.encode()) <= 64 for value in callback_values)
    assert any(value.startswith("rep:confirm:") for value in callback_values)
    assert "rep:edit" in callback_values
    assert "rep:cancel" in callback_values


async def test_ai_failure_and_invalid_output_do_not_persist(session):
    telegram_id = 7012
    bot = FakeBot()
    state = await make_state(telegram_id)

    await setup_flow(session, bot, state, telegram_id=telegram_id)

    handlers.set_extractor(
        FakeExtractor(error=RuntimeError("gemini down"))
    )
    await submit_report(bot, state, telegram_id=telegram_id)

    assert await count_updates(session) == 0
    assert await state.get_state() == (
        ReportFlow.waiting_for_report.state
    )

    handlers.set_extractor(
        FakeExtractor(result={"status": "not-a-status"})
    )
    await submit_report(
        bot,
        state,
        telegram_id=telegram_id,
        message_id=501,
    )

    assert await count_updates(session) == 0
    assert await state.get_state() == (
        ReportFlow.waiting_for_report.state
    )

    handlers.set_extractor(
        FakeExtractor(result=make_draft(summary=""))
    )
    await submit_report(
        bot,
        state,
        telegram_id=telegram_id,
        message_id=502,
    )

    assert await count_updates(session) == 0
    assert await state.get_state() == (
        ReportFlow.waiting_for_report.state
    )


async def test_status_and_completion_edits_are_validated(session):
    draft = make_draft()
    reference = REFERENCE_DATETIME

    invalid_status = apply_edit(
        draft_data=draft_to_data(draft),
        field="status",
        raw_value="bozuk",
        reference_datetime=reference,
    )
    assert invalid_status.error is not None
    assert invalid_status.draft is None

    for value in ("101", "-1", "abc", "70.5"):
        outcome = apply_edit(
            draft_data=draft_to_data(draft),
            field="completion_percentage",
            raw_value=value,
            reference_datetime=reference,
        )
        assert outcome.error is not None, value

    zero = apply_edit(
        draft_data=draft_to_data(draft),
        field="completion_percentage",
        raw_value="0",
        reference_datetime=reference,
    )
    assert zero.error is None
    assert zero.draft["completion_percentage"] == 0

    hundred = apply_edit(
        draft_data=draft_to_data(draft),
        field="completion_percentage",
        raw_value="%100",
        reference_datetime=reference,
    )
    assert hundred.error is None
    assert hundred.draft["completion_percentage"] == 100

    telegram_id = 7013
    bot = FakeBot()
    state = await make_state(telegram_id)

    await setup_flow(session, bot, state, telegram_id=telegram_id)
    handlers.set_extractor(FakeExtractor(make_draft()))
    await submit_report(bot, state, telegram_id=telegram_id)

    data = await state.get_data()
    data["field_to_edit"] = "status"
    await state.set_data(data)
    await state.set_state(ReportFlow.waiting_for_field_edit)

    callback = FakeCallback(
        bot=bot,
        data="rep:status:not-a-status",
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    await handlers.edit_status_handler(callback, state)

    assert callback.answers[-1]["show_alert"] is True
    assert (await state.get_data())["draft"]["status"] == "in_progress"


async def test_other_fields_edit_and_preview_refresh(session):
    telegram_id = 7014
    bot = FakeBot()
    state = await make_state(telegram_id)

    await setup_flow(session, bot, state, telegram_id=telegram_id)
    handlers.set_extractor(FakeExtractor(make_draft()))
    await submit_report(bot, state, telegram_id=telegram_id)

    edit_menu = FakeCallback(
        bot=bot,
        data="rep:edit",
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    await handlers.edit_menu_handler(edit_menu, state)

    assert await state.get_state() == (
        ReportFlow.waiting_for_field_edit.state
    )

    choose_blocker = FakeCallback(
        bot=bot,
        data="rep:field:blocker",
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    await handlers.edit_field_handler(choose_blocker, state)

    assert (await state.get_data())["field_to_edit"] == "blocker"

    edit_message = FakeMessage(
        bot=bot,
        chat_id=telegram_id,
        user_id=telegram_id,
        text="Malzeme gecikti.",
    )
    await handlers.report_text_handler(edit_message, state)

    data = await state.get_data()
    assert await state.get_state() == ReportFlow.reviewing.state
    assert data["draft"]["blocker"] == "Malzeme gecikti."
    assert "Engel: Malzeme gecikti." in bot.edits[-1]["text"]

    choose_completion = FakeCallback(
        bot=bot,
        data="rep:field:completion_percentage",
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    await handlers.edit_menu_handler(
        FakeCallback(
            bot=bot,
            data="rep:edit",
            user_id=telegram_id,
            chat_id=telegram_id,
        ),
        state,
    )
    await handlers.edit_field_handler(choose_completion, state)

    completion_message = FakeMessage(
        bot=bot,
        chat_id=telegram_id,
        user_id=telegram_id,
        text="85",
    )
    await handlers.report_text_handler(completion_message, state)

    data = await state.get_data()
    assert data["draft"]["completion_percentage"] == 85
    assert "%85" in bot.edits[-1]["text"]

    choose_summary = FakeCallback(
        bot=bot,
        data="rep:field:summary",
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    await handlers.edit_menu_handler(
        FakeCallback(
            bot=bot,
            data="rep:edit",
            user_id=telegram_id,
            chat_id=telegram_id,
        ),
        state,
    )
    await handlers.edit_field_handler(choose_summary, state)

    summary_message = FakeMessage(
        bot=bot,
        chat_id=telegram_id,
        user_id=telegram_id,
        text="Güncellenmiş özet.",
    )
    await handlers.report_text_handler(summary_message, state)

    data = await state.get_data()
    assert data["draft"]["summary"] == "Güncellenmiş özet."
    assert "Güncellenmiş özet." in bot.edits[-1]["text"]
    # Editing fields must not replace the original source message id.
    assert data["source_message_id"] == 500

    old_token = data["confirmation_token"]

    # The next valid edit invalidates the confirmation button rendered
    # for the previous draft version.
    await handlers.edit_menu_handler(
        FakeCallback(
            bot=bot,
            data="rep:edit",
            user_id=telegram_id,
            chat_id=telegram_id,
        ),
        state,
    )
    await handlers.edit_field_handler(
        FakeCallback(
            bot=bot,
            data="rep:field:next_step",
            user_id=telegram_id,
            chat_id=telegram_id,
        ),
        state,
    )
    await handlers.report_text_handler(
        FakeMessage(
            bot=bot,
            chat_id=telegram_id,
            user_id=telegram_id,
            text="Yeni adım.",
        ),
        state,
    )

    data = await state.get_data()
    assert data["confirmation_token"] != old_token


async def test_optional_text_fields_can_be_cleared(session):
    draft = make_draft(
        blocker="Eski engel",
        next_step="Eski adım",
    )
    reference = REFERENCE_DATETIME

    cleared_blocker = apply_edit(
        draft_data=draft_to_data(draft),
        field="blocker",
        raw_value="-",
        reference_datetime=reference,
    )
    assert cleared_blocker.error is None
    assert cleared_blocker.draft["blocker"] is None

    cleared_eta = apply_edit(
        draft_data=draft_to_data(draft),
        field="reported_eta_text",
        raw_value="temizle",
        reference_datetime=reference,
        current_eta_date=EXPECTED_ETA,
    )
    assert cleared_eta.error is None
    assert cleared_eta.draft["reported_eta_text"] is None
    assert cleared_eta.eta_date is None

    changed_eta = apply_edit(
        draft_data=draft_to_data(draft),
        field="reported_eta_text",
        raw_value="salı gününe kadar",
        reference_datetime=reference,
        current_eta_date=EXPECTED_ETA,
    )
    assert changed_eta.error is None
    assert changed_eta.eta_date == date(2026, 11, 17)

    cleared_summary = apply_edit(
        draft_data=draft_to_data(draft),
        field="summary",
        raw_value="-",
        reference_datetime=reference,
    )
    assert cleared_summary.error is not None

    too_long = apply_edit(
        draft_data=draft_to_data(draft),
        field="task_reference_text",
        raw_value="x" * 251,
        reference_datetime=reference,
    )
    assert too_long.error is not None

    telegram_id = 7015
    bot = FakeBot()
    state = await make_state(telegram_id)

    await setup_flow(session, bot, state, telegram_id=telegram_id)
    handlers.set_extractor(FakeExtractor(draft))
    await submit_report(bot, state, telegram_id=telegram_id)

    choose_blocker = FakeCallback(
        bot=bot,
        data="rep:field:blocker",
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    await handlers.edit_menu_handler(
        FakeCallback(
            bot=bot,
            data="rep:edit",
            user_id=telegram_id,
            chat_id=telegram_id,
        ),
        state,
    )
    await handlers.edit_field_handler(choose_blocker, state)

    clear_message = FakeMessage(
        bot=bot,
        chat_id=telegram_id,
        user_id=telegram_id,
        text="-",
    )
    await handlers.report_text_handler(clear_message, state)

    data = await state.get_data()
    assert data["draft"]["blocker"] is None
    assert "Engel:" not in bot.edits[-1]["text"]


async def test_cancel_discards_draft(session):
    telegram_id = 7016
    bot = FakeBot()
    state = await make_state(telegram_id)

    await setup_flow(session, bot, state, telegram_id=telegram_id)
    handlers.set_extractor(FakeExtractor(make_draft()))
    await submit_report(bot, state, telegram_id=telegram_id)

    callback = FakeCallback(
        bot=bot,
        data="rep:cancel",
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    await handlers.cancel_handler(callback, state)

    assert await count_updates(session) == 0
    assert await state.get_state() is None
    assert await state.get_data() == {}
    assert "iptal" in bot.edits[-1]["text"].lower()


async def test_confirm_creates_one_update_with_source_message_id(
    session,
):
    telegram_id = 7017
    bot = FakeBot()
    state = await make_state(telegram_id)

    employee_id, task_id, plan_id = await setup_flow(
        session,
        bot,
        state,
        telegram_id=telegram_id,
    )

    handlers.set_extractor(FakeExtractor(make_draft()))
    report_message = await submit_report(
        bot,
        state,
        telegram_id=telegram_id,
        message_id=500,
    )

    data = await state.get_data()
    assert data["source_message_id"] == report_message.message_id
    assert data["confirmation_token"]

    confirm = FakeCallback(
        bot=bot,
        data=f"rep:confirm:{data['confirmation_token']}",
        user_id=telegram_id,
        chat_id=telegram_id,
        message_id=900,
    )
    # The callback message may be sent on a later day; the stored ETA
    # must still be normalized from the original report timestamp.
    confirm.message.date = datetime(
        2026,
        11,
        18,
        18,
        0,
        tzinfo=timezone.utc,
    )
    await handlers.confirm_handler(confirm, state)

    assert await count_updates(session) == 1
    assert await state.get_state() is None

    await session.rollback()
    update_row = await session.scalar(select(TaskUpdate))

    assert update_row.telegram_message_id == 500
    assert update_row.telegram_message_id != 900
    assert update_row.telegram_chat_id == telegram_id
    assert update_row.telegram_user_id == telegram_id
    assert update_row.employee_id == employee_id
    assert update_row.task_id == task_id
    assert update_row.weekly_plan_id == plan_id
    assert update_row.original_message == REPORT_TEXT
    assert update_row.status == "in_progress"
    assert update_row.completion_percentage == 70
    assert update_row.reported_eta_date == EXPECTED_ETA
    assert update_row.review_status == "approved"
    assert update_row.reviewed_by_employee_id == employee_id
    assert update_row.ai_model == "fake-model"

    assert "kaydedildi" in bot.edits[-1]["text"].lower()


async def test_confirmation_requires_same_user_chat_and_token(
    session,
):
    telegram_id = 7018
    bot = FakeBot()
    state = await make_state(telegram_id)

    _employee_id, task_id, _plan_id = await setup_flow(
        session,
        bot,
        state,
        telegram_id=telegram_id,
    )
    handlers.set_extractor(FakeExtractor(make_draft()))
    await submit_report(bot, state, telegram_id=telegram_id)

    other_user = FakeCallback(
        bot=bot,
        data=(
            "rep:confirm:"
            + (await state.get_data())["confirmation_token"]
        ),
        user_id=7019,
        chat_id=7019,
    )
    await handlers.confirm_handler(other_user, state)

    assert other_user.answers[-1]["show_alert"] is True
    assert await count_updates(session) == 0
    assert await state.get_state() is None

    # A fresh flow for the wrong chat check.
    await handlers.task_selection_handler(
        FakeCallback(
            bot=bot,
            data=f"task:{task_id}",
            user_id=telegram_id,
            chat_id=telegram_id,
        ),
        state,
    )

    await submit_report(
        bot,
        state,
        telegram_id=telegram_id,
        message_id=501,
    )

    wrong_chat = FakeCallback(
        bot=bot,
        data=(
            "rep:confirm:"
            + (await state.get_data())["confirmation_token"]
        ),
        user_id=telegram_id,
        chat_id=999999,
    )
    await handlers.confirm_handler(wrong_chat, state)

    assert wrong_chat.answers[-1]["show_alert"] is True
    assert await count_updates(session) == 0
    assert await state.get_state() is None

    # The employee can retry the same task with a valid state; an old
    # token is not accepted even when the user and chat match.
    await handlers.task_selection_handler(
        FakeCallback(
            bot=bot,
            data=f"task:{task_id}",
            user_id=telegram_id,
            chat_id=telegram_id,
        ),
        state,
    )
    await submit_report(
        bot,
        state,
        telegram_id=telegram_id,
        message_id=502,
    )

    bad_token = FakeCallback(
        bot=bot,
        data="rep:confirm:deadbeef",
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    await handlers.confirm_handler(bad_token, state)

    assert bad_token.answers[-1]["show_alert"] is True
    assert await count_updates(session) == 0
    assert await state.get_state() == ReportFlow.reviewing.state


async def test_deactivated_employee_cannot_confirm(session):
    telegram_id = 7020
    bot = FakeBot()
    state = await make_state(telegram_id)

    _employee_id, _task_id, _plan_id = await setup_flow(
        session,
        bot,
        state,
        telegram_id=telegram_id,
    )

    handlers.set_extractor(FakeExtractor(make_draft()))
    await submit_report(bot, state, telegram_id=telegram_id)

    await session.execute(
        update(Employee)
        .where(Employee.telegram_user_id == telegram_id)
        .values(is_active=False)
    )
    await session.commit()

    confirm = FakeCallback(
        bot=bot,
        data=(
            "rep:confirm:"
            + (await state.get_data())["confirmation_token"]
        ),
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    await handlers.confirm_handler(confirm, state)

    assert confirm.answers[-1]["show_alert"] is True
    assert await count_updates(session) == 0
    assert await state.get_state() is None
    assert "Aktif çalışan" in bot.edits[-1]["text"]


async def test_removed_assignment_cannot_be_confirmed(session):
    telegram_id = 7021
    bot = FakeBot()
    state = await make_state(telegram_id)

    employee_id, task_id, _plan_id = await setup_flow(
        session,
        bot,
        state,
        telegram_id=telegram_id,
    )

    handlers.set_extractor(FakeExtractor(make_draft()))
    await submit_report(bot, state, telegram_id=telegram_id)

    await session.execute(
        delete(TaskAssignment).where(
            TaskAssignment.task_id == task_id,
            TaskAssignment.employee_id == employee_id,
        )
    )
    await session.commit()

    confirm = FakeCallback(
        bot=bot,
        data=(
            "rep:confirm:"
            + (await state.get_data())["confirmation_token"]
        ),
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    await handlers.confirm_handler(confirm, state)

    assert confirm.answers[-1]["show_alert"] is True
    assert await count_updates(session) == 0
    assert await state.get_state() is None
    assert "Görev atamanız" in bot.edits[-1]["text"]


async def test_changed_weekly_plan_blocks_stale_confirmation(session):
    telegram_id = 7022
    bot = FakeBot()
    state = await make_state(telegram_id)

    _employee_id, _task_id, plan_id = await setup_flow(
        session,
        bot,
        state,
        telegram_id=telegram_id,
    )

    handlers.set_extractor(FakeExtractor(make_draft()))
    await submit_report(bot, state, telegram_id=telegram_id)

    await session.execute(
        update(WeeklyTaskPlan)
        .where(WeeklyTaskPlan.id == plan_id)
        .values(target_completion_percentage=90)
    )
    await session.commit()

    confirm = FakeCallback(
        bot=bot,
        data=(
            "rep:confirm:"
            + (await state.get_data())["confirmation_token"]
        ),
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    await handlers.confirm_handler(confirm, state)

    assert confirm.answers[-1]["show_alert"] is True
    assert await count_updates(session) == 0
    assert await state.get_state() is None
    assert "Haftalık plan bilgisi" in bot.edits[-1]["text"]


async def test_duplicate_confirmation_does_not_create_second_update(
    session,
):
    telegram_id = 7023
    bot = FakeBot()
    state = await make_state(telegram_id)

    employee_id, task_id, _plan_id = await setup_flow(
        session,
        bot,
        state,
        telegram_id=telegram_id,
    )

    handlers.set_extractor(FakeExtractor(make_draft()))
    await submit_report(bot, state, telegram_id=telegram_id)

    # Simulate a report that was already stored for this exact source
    # message, for example by a concurrent confirmation.
    session.add(
        TaskUpdate(
            task_id=task_id,
            employee_id=employee_id,
            telegram_user_id=telegram_id,
            telegram_chat_id=telegram_id,
            telegram_message_id=500,
            original_message="Önceki kayıt",
            status="unknown",
        )
    )
    await session.commit()

    confirm = FakeCallback(
        bot=bot,
        data=(
            "rep:confirm:"
            + (await state.get_data())["confirmation_token"]
        ),
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    await handlers.confirm_handler(confirm, state)

    assert confirm.answers[-1]["show_alert"] is True
    assert await count_updates(session) == 1
    assert await state.get_state() is None
    assert "daha önce kaydedilmiş" in bot.edits[-1]["text"]


async def test_approval_does_not_change_weekly_plan(session):
    telegram_id = 7024
    bot = FakeBot()
    state = await make_state(telegram_id)

    _employee_id, task_id, plan_id = await setup_flow(
        session,
        bot,
        state,
        telegram_id=telegram_id,
    )

    await session.rollback()
    plan_before = await session.get(WeeklyTaskPlan, plan_id)
    before = (
        plan_before.target_description,
        plan_before.target_completion_percentage,
        plan_before.week_start_date,
        plan_before.week_end_date,
        plan_before.status,
    )

    handlers.set_extractor(FakeExtractor(make_draft()))
    await submit_report(bot, state, telegram_id=telegram_id)

    confirm = FakeCallback(
        bot=bot,
        data=(
            "rep:confirm:"
            + (await state.get_data())["confirmation_token"]
        ),
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    await handlers.confirm_handler(confirm, state)

    assert await count_updates(session) == 1

    await session.rollback()
    plan_after = await session.get(WeeklyTaskPlan, plan_id)
    after = (
        plan_after.target_description,
        plan_after.target_completion_percentage,
        plan_after.week_start_date,
        plan_after.week_end_date,
        plan_after.status,
    )

    assert after == before
