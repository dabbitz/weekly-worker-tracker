
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
# WEEKLY TASK PLANS
# ==========================================

class WeeklyTaskPlan(Base):

    __tablename__ = "weekly_task_plans"

    __table_args__ = (

        UniqueConstraint(
            "task_id",
            "week_start_date",
            name="uq_weekly_plans_task_week"
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