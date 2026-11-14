
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


# ==========================================
# EMPLOYEES
# ==========================================

class Employee(Base):

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    telegram_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        unique=True,
        nullable=True
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    role: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Employee-task assignments

    task_assignments: Mapped[list["TaskAssignment"]] = relationship(
        back_populates="employee"
    )

    # Updates submitted by this employee

    updates: Mapped[list["TaskUpdate"]] = relationship(
        back_populates="employee",
        foreign_keys="TaskUpdate.employee_id"
    )

    # Updates reviewed by this employee

    reviewed_updates: Mapped[list["TaskUpdate"]] = relationship(
        back_populates="reviewed_by",
        foreign_keys="TaskUpdate.reviewed_by_employee_id"
    )


# ==========================================
# REGISTRATION REQUESTS
# ==========================================

class RegistrationRequest(Base):

    __tablename__ = "registration_requests"

    __table_args__ = (

        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_registration_requests_status"
        ),

        # Only one pending request per Telegram account.
        # A new request is allowed after rejection.

        Index(
            "uq_registration_requests_pending_user",
            "telegram_user_id",
            unique=True,
            postgresql_where=text("status = 'pending'")
        ),

    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )

    telegram_chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )

    requested_full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    # Link to an existing employee if this is a reactivation request.
    # Otherwise, a new employee will be created after approval.

    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    reviewed_by_telegram_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True
    )



# ==========================================
# PROJECTS
# ==========================================

class Project(Base):

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    location: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True
    )

    expected_completion_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project"
    )


# ==========================================
# TASKS
# ==========================================

class Task(Base):

    __tablename__ = "tasks"

    __table_args__ = (

        CheckConstraint(
            "planned_start_date IS NULL "
            "OR planned_due_date IS NULL "
            "OR planned_start_date <= planned_due_date",
            name="ck_tasks_planned_dates"
        ),

    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    title: Mapped[str] = mapped_column(
        String(250),
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Planned start date

    planned_start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    # Automatically generated Turkish weekday

    planned_start_weekday: Mapped[str | None] = mapped_column(
        String(10),
        Computed(
            """
            CASE EXTRACT(ISODOW FROM planned_start_date)
                WHEN 1 THEN 'pazartesi'
                WHEN 2 THEN 'salı'
                WHEN 3 THEN 'çarşamba'
                WHEN 4 THEN 'perşembe'
                WHEN 5 THEN 'cuma'
                WHEN 6 THEN 'cumartesi'
                WHEN 7 THEN 'pazar'
            END
            """,
            persisted=True
        ),
        nullable=True
    )

    # Planned completion date

    planned_due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    # Automatically generated Turkish weekday

    planned_due_weekday: Mapped[str | None] = mapped_column(
        String(10),
        Computed(
            """
            CASE EXTRACT(ISODOW FROM planned_due_date)
                WHEN 1 THEN 'pazartesi'
                WHEN 2 THEN 'salı'
                WHEN 3 THEN 'çarşamba'
                WHEN 4 THEN 'perşembe'
                WHEN 5 THEN 'cuma'
                WHEN 6 THEN 'cumartesi'
                WHEN 7 THEN 'pazar'
            END
            """,
            persisted=True
        ),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships

    project: Mapped["Project"] = relationship(
        back_populates="tasks"
    )

    assignments: Mapped[list["TaskAssignment"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan"
    )

    weekly_plans: Mapped[list["WeeklyTaskPlan"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan"
    )

    updates: Mapped[list["TaskUpdate"]] = relationship(
        back_populates="task",
        foreign_keys="TaskUpdate.task_id"
    )


# ==========================================
# TASK ASSIGNMENTS
# ==========================================

class TaskAssignment(Base):

    __tablename__ = "task_assignments"

    __table_args__ = (

        Index(
            "ix_task_assignments_employee",
            "employee_id"
        ),

    )

    # Composite primary key

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True
    )

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"),
        primary_key=True
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    task: Mapped["Task"] = relationship(
        back_populates="assignments"
    )

    employee: Mapped["Employee"] = relationship(
        back_populates="task_assignments"
    )


# ==========================================
# WEEKLY PLAN GENERATIONS
# ==========================================

class WeeklyPlanGeneration(Base):
    """One AI weekly-plan generation request.

    Plans created by the same request share this record. The unique
    request_id makes retries idempotent and keeps AI drafts grouped.
    """

    __tablename__ = "weekly_plan_generations"

    __table_args__ = (

        CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="ck_weekly_plan_generations_status"
        ),

        UniqueConstraint(
            "request_id",
            name="uq_weekly_plan_generations_request_id"
        ),

    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    request_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )

    request_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True
    )

    model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    extra_instructions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'")
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    plans: Mapped[list["WeeklyTaskPlan"]] = relationship(
        back_populates="generation"
    )


# ==========================================
# WEEKLY TASK PLANS
# ==========================================

class WeeklyTaskPlan(Base):

    __tablename__ = "weekly_task_plans"

    __table_args__ = (

        # Only one officially approved plan may exist for a task/week.
        # Drafts and historical versions can coexist.

        Index(
            "uq_weekly_plans_approved_task_week",
            "task_id",
            "week_start_date",
            unique=True,
            postgresql_where=text("status = 'approved'")
        ),

        CheckConstraint(
            "week_end_date >= week_start_date",
            name="ck_weekly_plans_date_range"
        ),

        CheckConstraint(
            "target_completion_percentage IS NULL OR "
            "(target_completion_percentage BETWEEN 0 AND 100)",
            name="ck_weekly_plans_completion"
        ),

        CheckConstraint(
            "status IN ('draft', 'approved', 'rejected', 'superseded')",
            name="ck_weekly_plans_status"
        ),

        CheckConstraint(
            "source IN ('manual', 'ai')",
            name="ck_weekly_plans_source"
        ),

    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    week_start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    week_end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    target_description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    # Target percentage for the entire task
    # at the end of this planning week

    target_completion_percentage: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True
    )

    # Lifecycle:
    # draft      -> AI or manual proposal, not official yet
    # approved   -> official weekly target
    # rejected   -> rejected draft, preserved for history
    # superseded -> previously approved plan replaced by a newer one

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        server_default=text("'draft'")
    )

    # manual -> created by the administrator
    # ai     -> generated by the AI weekly planning service

    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="manual",
        server_default=text("'manual'")
    )

    generation_id: Mapped[int | None] = mapped_column(
        ForeignKey("weekly_plan_generations.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # AI planning notes shown to the administrator during review.

    ai_rationale: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    ai_assumptions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    ai_warnings: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    task: Mapped["Task"] = relationship(
        back_populates="weekly_plans"
    )

    generation: Mapped["WeeklyPlanGeneration | None"] = relationship(
        back_populates="plans"
    )

    updates: Mapped[list["TaskUpdate"]] = relationship(
        back_populates="weekly_plan",
        foreign_keys="TaskUpdate.weekly_plan_id"
    )


# ==========================================
# TASK UPDATES
# ==========================================

class TaskUpdate(Base):

    __tablename__ = "task_updates"

    __table_args__ = (

        CheckConstraint(
            "status IN "
            "('completed', 'in_progress', 'blocked', "
            "'not_started', 'unknown')",
            name="ck_task_updates_status"
        ),

        CheckConstraint(
            "completion_percentage IS NULL OR "
            "(completion_percentage BETWEEN 0 AND 100)",
            name="ck_task_updates_completion"
        ),

        CheckConstraint(
            "review_status IN "
            "('pending', 'approved', 'rejected')",
            name="ck_task_updates_review_status"
        ),

        CheckConstraint(
            "sync_status IN "
            "('not_synced', 'synced', 'failed')",
            name="ck_task_updates_sync_status"
        ),

        CheckConstraint(
            "(review_status = 'pending' "
            "AND reviewed_by_employee_id IS NULL "
            "AND reviewed_at IS NULL) "
            "OR "
            "(review_status IN ('approved', 'rejected') "
            "AND reviewed_by_employee_id IS NOT NULL "
            "AND reviewed_at IS NOT NULL)",
            name="ck_task_updates_review_consistency"
        ),

        UniqueConstraint(
            "telegram_chat_id",
            "telegram_message_id",
            name="uq_task_updates_telegram_message"
        ),

        Index(
            "ix_task_updates_task_received",
            "task_id",
            "received_at"
        ),

        Index(
            "ix_task_updates_employee_received",
            "employee_id",
            "received_at"
        ),

    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    # Related task

    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True
    )

    # Related weekly plan

    weekly_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("weekly_task_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Employee who submitted the update

    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True
    )

    # Telegram source information

    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )

    telegram_chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )

    telegram_message_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )

    # Original employee message

    original_message: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    # AI extracted information

    task_reference_text: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unknown",
        server_default=text("'unknown'")
    )

    completion_percentage: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True
    )

    blocker: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    delay_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    next_step: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Original and normalized ETA

    reported_eta_text: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    reported_eta_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    # Automatically generated Turkish weekday

    reported_eta_weekday: Mapped[str | None] = mapped_column(
        String(10),
        Computed(
            """
            CASE EXTRACT(ISODOW FROM reported_eta_date)
                WHEN 1 THEN 'pazartesi'
                WHEN 2 THEN 'salı'
                WHEN 3 THEN 'çarşamba'
                WHEN 4 THEN 'perşembe'
                WHEN 5 THEN 'cuma'
                WHEN 6 THEN 'cumartesi'
                WHEN 7 THEN 'pazar'
            END
            """,
            persisted=True
        ),
        nullable=True
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Review information

    review_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'")
    )

    reviewed_by_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Integration information

    sync_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="not_synced",
        server_default=text("'not_synced'")
    )

    synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    ai_model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships

    task: Mapped["Task | None"] = relationship(
        back_populates="updates",
        foreign_keys=[task_id]
    )

    weekly_plan: Mapped["WeeklyTaskPlan | None"] = relationship(
        back_populates="updates",
        foreign_keys=[weekly_plan_id]
    )

    employee: Mapped["Employee | None"] = relationship(
        back_populates="updates",
        foreign_keys=[employee_id]
    )

    reviewed_by: Mapped["Employee | None"] = relationship(
        back_populates="reviewed_updates",
        foreign_keys=[reviewed_by_employee_id]
    )


# ==========================================
# WEEKLY MANAGER REPORTS
# ==========================================

class WeeklyManagerReport(Base):
    """Stored AI-assisted weekly manager report document.

    The report is intentionally self-contained. It has no foreign keys to
    tasks, projects, employees, plans or reports, so deleting a source row
    later cannot break the historical document. Real identifiers and labels
    live in ``references``; the AI narrative stores only tokens that are
    resolved against that snapshot when the report is read.
    """

    __tablename__ = "weekly_manager_reports"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="ck_weekly_manager_reports_status"
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_weekly_manager_reports_version"
        ),
        CheckConstraint(
            "week_end_date >= week_start_date",
            name="ck_weekly_manager_reports_date_range"
        ),
        UniqueConstraint(
            "week_start_date",
            "version",
            name="uq_weekly_manager_reports_week_version"
        ),
        UniqueConstraint(
            "request_id",
            name="uq_weekly_manager_reports_request_id"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    week_start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    week_end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'")
    )

    request_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )

    request_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )

    model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    is_partial_week: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false")
    )

    extra_instructions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    metrics_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb")
    )

    data_quality: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb")
    )

    narrative: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True
    )

    references: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb")
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )


Index(
    "ix_weekly_manager_reports_week_version",
    WeeklyManagerReport.week_start_date.desc(),
    WeeklyManagerReport.version.desc(),
)