# AGENTS.md — WorkTrack Weekly Work Tracking System

## 1. Project purpose

Build **WorkTrack**, a Turkish-first, AI-assisted weekly work tracking system for office and construction-site teams.

The system has three cooperating parts:

1. **Telegram bot** — employee registration requests and, in a later phase, employee work updates.
2. **Python backend** — authentication, business rules, REST API, validation, and database access.
3. **React admin dashboard** — the administrator's interface for managing projects, employees, tasks, assignments, and weekly plans.

The immediate priority is the **administrator dashboard and its real connection to the existing backend/database**. Do not continue or expand the employee AI work-report submission flow during this dashboard phase unless a change is essential to keep the existing system working.

## 2. Mandatory workflow

1. Read this `AGENTS.md` before inspecting or changing code.
2. Inspect the existing repository before making assumptions. Review the actual `models.py`, database connection, Telegram handlers, registration service, `.gitignore`, `requirements.txt`, and current database/migration setup.
3. Preserve working functionality. Do not replace or rewrite the project from scratch.
4. Before changing the database schema, compare the SQLAlchemy models with the actual Neon schema and migration history.
5. Implement changes in small, coherent steps. Run relevant tests, type/build checks, and `pip check` where applicable.
6. Do not claim something works unless you have run the corresponding check.
7. If blocked by a missing tool, environment variable, or external account setting, explain the exact blocker and continue with independent work where safe.

## 3. Current project context to verify

The project root is expected to be:

`C:\Users\Tunahan\weekly-work-tracker`

The existing project has been developed on Windows with PowerShell and Python 3.14 in a virtual environment named `.venv`.

The repository has already been developed to include:

- An aiogram 3 Telegram bot in the root `main.py`.
- Telegram `/register` flow: a user submits a full name, a `registration_requests` record is created, and the configured administrator receives Telegram approval/rejection buttons. An `employees` record is created or reactivated only after approval.
- Gemini integration using the `google-genai` SDK and the `gemini-3.5-flash-lite` model.
- A Turkish date normalizer that uses Telegram's original message timestamp and `Europe/Istanbul`.
- Neon-hosted PostgreSQL, accessed via `DATABASE_URL` in `.env`.
- SQLAlchemy asynchronous database access using `asyncpg`.
- Pydantic schemas and Alembic may already be installed or partially configured.

These are repository-context clues, not permission to assume every file is current. Inspect the code and retain the actual working implementation. Do not print, log, copy, or expose the values in `.env`.

## 4. Agreed data-model rules

The current intended core entities are:

- `employees`
- `projects`
- `tasks`
- `task_assignments`
- `weekly_task_plans`
- `task_updates`
- `registration_requests`

Use the actual models as the source of truth and reconcile differences carefully.

### Important relationship decision

**Do not create a `project_memberships` table.** The user explicitly decided that employees do not need a direct project membership at this stage.

Instead:

- A task belongs to one project through `tasks.project_id`.
- Employees are assigned to tasks through `task_assignments`.
- A project's associated employees are derived from employees assigned to that project's tasks.
- Keep the existing many-to-many task assignment design: a task may have multiple assigned employees. Do not add a direct employee-to-project association.

If an employee has no assigned task, do not invent a project association for them.

### Weekly plans

`weekly_task_plans` holds each task's weekly target. It is separate from the task's overall planned start/due dates. Preserve this distinction.

### Work updates

Every Telegram message/update is an independent historical record in `task_updates`; do not overwrite earlier updates. The employee's approval is represented by the existing review fields. Do not delete rejected updates.

### Registration requests

Registration must remain approval-based. A Telegram user is not an active employee merely because they ran `/register`. Preserve the existing administrator approval workflow and prevent duplicate pending requests.

## 5. Architecture decisions

Use a single repository, with separate frontend and backend areas:

- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy 2 async, asyncpg, Neon PostgreSQL.
- **Frontend:** React + TypeScript + Vite.
- **UI:** Tailwind CSS and shadcn/ui (or accessible equivalents if the current project setup makes shadcn impractical).
- **Routing:** React Router.
- **Server state/API cache:** TanStack Query.
- **Icons:** lucide-react.
- **Charts:** Recharts only where actual data makes a chart useful.

Expected structure (adapt to the existing repository; do not duplicate existing files):

```text
weekly-work-tracker/
├── app/
│   ├── api/
│   │   ├── main.py              # FastAPI entry point; NOT the Telegram main.py
│   │   └── routes/
│   ├── database/
│   ├── schemas/
│   └── services/
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── layouts/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── types/
│   └── ...
├── alembic/                     # if not already present
├── main.py                      # existing Telegram bot; preserve
├── .env                         # secrets; never commit
├── .env.example                 # variable names/placeholders only
└── requirements.txt
```

The Telegram bot and FastAPI app are separate processes but share the same database, models, schemas, and service layer where appropriate.

## 6. Dashboard product requirements

The dashboard is for the administrator. It should be a functional application, not a static mockup.

### Visual direction

Use a polished, restrained **WorkTrack** admin interface inspired by this layout:

- Dark navy left sidebar (for example `#172B3D` / `#20364A`).
- Light neutral main canvas (for example `#F5F7FA`).
- White content cards with subtle borders/shadows.
- Clear typography, generous spacing, consistent alignment.
- Restrained status colors: green for success/active, amber for pending/warning, red for blocked/error.
- Responsive layout for desktop and tablet; usable on narrower screens.
- Sidebar brand/title: `WorkTrack` and subtitle `Yönetim Paneli`.
- Turkish-first interface text.

Do not use fake hard-coded metrics or fake records. Use loading, empty, and error states backed by the API. Empty database states should look intentional and guide the administrator to create the first project.

### Initial pages

1. **Admin login** — secure login for the administrator.
2. **Genel Bakış** — real counts for projects, active employees, tasks, and pending registration requests; recent projects; useful empty states.
3. **Projeler** — list, search/filter, create, edit, and view projects.
4. **Proje Detayı** — project metadata, expected completion date, tasks belonging to the project, and employees derived from assignments to those tasks.
5. **Çalışanlar** — list/search employees, show active/inactive status, and open employee detail.
6. **Çalışan Detayı** — show that employee's assigned tasks and the projects derived through those tasks. Do not show a direct project membership that is not stored.
7. **Görevler** — create/edit tasks within a project, manage planned dates, and assign/unassign one or more employees using `task_assignments`.
8. **Haftalık Planlar** — create/edit weekly plans per task, including week range, target description, and target completion percentage.
9. **Kayıt Talepleri** — display pending/approved/rejected Telegram registration requests. If dashboard approval/rejection is implemented, reuse the same backend business logic as the Telegram callback; do not duplicate decision logic. Telegram approval must continue to work.

Reports can be a clearly marked later-phase item or a minimal read-only page. Do not fabricate weekly performance results before there are actual task updates.

### Project and employee behavior

- The administrator can create a project before any task or employee is associated with it.
- Creating a project must not automatically create employees or assignments.
- The administrator can create tasks under a project.
- A task can have multiple employees assigned through `task_assignments`.
- The employees displayed on a project page are the distinct employees assigned to tasks belonging to that project.
- Employees without task assignments remain visible in the global employee list but are not artificially attached to a project.
- Do not add `project_memberships`.

## 7. Backend/API requirements

- Create a FastAPI application under `app/api/` without renaming or breaking the root Telegram `main.py`.
- Use async SQLAlchemy sessions and the existing database engine/session factory.
- Use Pydantic request/response schemas; do not expose SQLAlchemy ORM objects directly.
- Keep route handlers thin. Put business logic in services/repositories.
- Provide documented REST endpoints for authentication, dashboard summary, projects, employees, tasks, task assignments, weekly plans, and registration requests.
- Add pagination or sensible limits to list endpoints; support basic search/filter where useful.
- Validate foreign keys, date ranges, completion percentages, active employee status, and assignment consistency.
- For project employee lists, query through `tasks` → `task_assignments` → `employees`, returning distinct employees.
- Do not connect React directly to Neon. All database access must go through FastAPI.
- Configure CORS for the exact local Vite origin during development (normally `http://localhost:5173`); do not use wildcard origins with credentials.
- Keep API error responses understandable and avoid leaking database URLs, stack traces, or secrets.
- Add `/health` or `/api/health` for a simple health check.

## 8. Dashboard authentication and security

This is initially a single-administrator dashboard.

- Do not add public administrator registration.
- Use credentials configured through backend environment variables, not frontend variables.
- Store only a password hash (Argon2 preferred) in environment/configuration; do not store plaintext passwords in source code or the database.
- Use a signed, expiring authentication mechanism and protect every admin API endpoint, except login and health check.
- Validate authorization on the backend for every protected action. Hiding a button in React is not authorization.
- Do not trust Telegram callback data or frontend-supplied employee/admin IDs.
- Keep `ADMIN_TELEGRAM_ID` separate from dashboard login credentials.
- Never put `DATABASE_URL`, `BOT_TOKEN`, `GEMINI_API_KEY`, JWT/session secrets, or administrator password/hash in `VITE_*` variables or client bundles.
- Keep `.env` in `.gitignore`. Update `.env.example` using placeholders only; never overwrite the user's real `.env`.
- Do not print secrets in terminal output, logs, tests, or responses.

## 9. Database and migration safety

Neon is already configured through `.env`. Treat it as a real persistent database.

- Never drop, truncate, or recreate existing tables to make the dashboard work.
- Do not run destructive SQL or reset the Neon database.
- `Base.metadata.create_all()` does not update existing tables; do not rely on it for schema changes.
- Inspect existing Alembic configuration and migration history first.
- If model changes are required, create a reviewed Alembic migration. Inspect the generated migration before applying it.
- Preserve existing employee registrations, registration requests, projects, and any task data.
- Do not seed fake data automatically into Neon. Provide optional local/demo seed data only if explicitly requested, and make it opt-in.
- Generated weekday columns must remain database-generated from their corresponding DATE fields. The application must not try to insert values into generated columns.
- Keep original date expressions and normalized dates distinct where the current schema already provides them.

## 10. Existing Telegram and AI behavior to preserve

- Preserve the existing Telegram bot entry point and `/register` request flow.
- Preserve admin approval/rejection security checks using `ADMIN_TELEGRAM_ID`.
- Preserve the Gemini service and date normalizer; do not silently change the model or billing configuration.
- Do not make employee AI work-update ingestion the focus of this dashboard task. It can remain unchanged/paused until the administrator has projects, tasks, and assignments to refer to.
- Avoid introducing `project_memberships` or any alternative direct employee-project table.

## 11. Frontend quality requirements

- Use TypeScript types for API data and component props; avoid `any` unless unavoidable and justified.
- Keep API calls in a dedicated `src/api/` layer.
- Use TanStack Query for server data fetching, caching, loading/error states, and invalidation after mutations.
- Use React Router for page navigation.
- Use reusable components for sidebar, header, page title, tables, status badges, forms, dialogs, empty states, and loading states.
- Forms must validate input and display field-level errors.
- Confirm destructive actions and show success/error feedback.
- Make tables readable and responsive; use proper empty states.
- Accessible labels, keyboard navigation, and visible focus states are required.
- Do not create buttons that do nothing. Every visible action must work or be clearly marked as unavailable/later phase.

## 12. Testing and completion criteria

At minimum:

- Backend tests for authentication, project CRUD, employee listing, task CRUD, task assignment, weekly plans, and project-derived employee lists.
- Test that inactive employees cannot be newly assigned to tasks.
- Test that one task can have multiple employees.
- Test that project employee listing is derived through assigned tasks, with no `project_memberships` table.
- Test that unauthenticated users cannot access admin endpoints.
- Test that registration request approval still works and the existing Telegram registration flow is not broken.
- Run frontend production build and lint/type checks.
- Run Python import checks and `pip check`.
- Do not report tests as passing unless they were actually run.

The implementation is complete when the administrator can log in, create and view projects, view employees, create tasks, assign multiple employees to tasks, manage weekly plans, and see project employees derived from task assignments — all backed by the existing Neon database — while the Telegram bot's registration workflow remains functional.
