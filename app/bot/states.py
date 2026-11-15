"""FSM states for the Telegram text reporting flow.

The state names are part of the persisted FSM data contract; keep them
stable. The flow uses the default in-memory storage, so a bot restart
drops drafts. Handlers must treat missing data as a restart request.
"""

from aiogram.fsm.state import State, StatesGroup


class ReportFlow(StatesGroup):
    """States of one employee report draft."""

    # A task was selected; waiting for the employee's report text.
    waiting_for_report = State()

    # A preview exists; waiting for confirm / edit / cancel.
    reviewing = State()

    # The employee is editing one field of the current draft.
    waiting_for_field_edit = State()


class RegistrationFlow(StatesGroup):
    """States of the Telegram self-registration request."""

    # Name and surname were received; waiting for the job title.
    waiting_for_position = State()
