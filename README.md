# WorkTrack — Weekly Work Tracking System

WorkTrack is a Turkish-first weekly work tracking system for office and construction-site teams. It combines a Telegram bot for employees, an AI-assisted reporting pipeline that turns free-text updates into structured progress records, a REST API, and a Turkish administrator dashboard for projects, employees, tasks, assignments, weekly plans, and management reports.

All application data lives in PostgreSQL (Neon). The Telegram bot, the FastAPI backend, and the React dashboard are separate processes that share the same database and business-logic layer.

> "We completed about 70% of the electrical installation this week. We couldn't finish the rest because of a cable supply issue. If the materials arrive tomorrow, we plan to finish by Friday."
>
> ↓ ↓ ↓

```json
{
  "task_reference_text": "electrical installation",
  "status": "blocked",
  "completion_percentage": 70,
  "blocker": "cable supply issue",
  "delay_reason": null,
  "next_step": "finish the remaining work once materials arrive",
  "reported_eta_text": "cuma gününe kadar",
  "summary": "Elektrik tesisatının %70'i tamamlandı. Kablo tedarik sorunu nedeniyle kalan kısım bitirilemedi. Malzemeler yarın gelirse cuma gününe kadar tamamlanması planlanıyor."
}
```

---

## Features

### Telegram and work reports

- **Approval-based employee registration** — an employee submits a full name and an optional job position; the configured Telegram administrator approves or rejects the request before any employee record becomes active.
- **Optional job positions** — the position is asked during registration, can be skipped with `/atla`, and can be edited later in the dashboard. It is a profession label, not an authorization role.
- **Task-linked reporting** — employees use `/gorevlerim` (or `/rapor`) to see their assigned tasks and submit a report for a selected task.
- **Natural-language extraction** — Gemini converts Turkish or English free text into a validated `WorkUpdate` schema via Pydantic.
- **Natural-language progress estimation** — explicit percentages are kept exactly; qualitative descriptions such as "yarısını tamamladık" are mapped to a defensible approximate percentage, and no percentage is invented for vague messages.
- **Delays are not blockers** — a delayed but continuing task stays in progress and records a separate `delay_reason`. `blocked` is used only when a stated obstacle actually prevents work from continuing.
- **Preview before saving** — the employee sees the extracted fields, can edit them, and explicitly confirms before a row is inserted.
- **Historical records** — every confirmed report is a new `task_updates` row. Earlier reports are never overwritten.
- **Duplicate protection** — a Telegram message can produce only one saved report.
- **Prompt-injection resistant** — messages are treated strictly as data; the assistant never produces database identifiers.

### Administrator dashboard

- **Secure single-administrator login** — Argon2 password hashing and signed, expiring JWT access tokens.
- **Genel Bakış** — real project, active employee, task, and pending registration counts, plus recent projects and intentional empty states.
- **Project management** — create, search, edit, view, and delete projects with location and expected completion date.
- **Project detail** — project metadata, its tasks, and the team derived from task assignments.
- **Employee management** — list/search employees, inspect assigned tasks and derived projects, edit the position, and delete an employee when no historical reports depend on them.
- **Task management** — create and edit tasks inside a project, set planned start/due dates, and assign one or more employees.
- **Weekly planning** — AI-generated or manual weekly targets with approval, rejection, replacement, and history.
- **Registration history** — inspect pending, approved, and rejected Telegram registration requests. Decisions remain in Telegram.
- **Reports** — inspect employee work reports and generate AI-assisted weekly manager reports.
- **Real data only** — no seeded demo records and no fabricated metrics.

### AI weekly planning

- Select one or more tasks, optionally add instructions, and generate multi-week draft targets.
- Monday-based weeks are clipped to each task's real planned dates.
- Targets are cumulative end-of-week percentages, not weekly increments.
- AI output is always a draft until an administrator approves it.
- Only one approved plan may exist per task/week; replacing it preserves the previous plan as `superseded`.

### Weekly management reports

- Manually generated Monday–Sunday management reports; there is no scheduler or background worker.
- Deterministic metrics are calculated in plain SQL/Python; Gemini only interprets them.
- Validation rejects invented numbers, dates, tokens, classifications, employee names, and identifiers.
- Report versions are retained per week, failed generations can be retried, and report documents can be deleted without touching source data.
- Manager intervention suggestions combine deterministic candidates and evidence-backed AI recommendations.

---

## How It Works

```mermaid
flowchart LR
    E[Employee] -->|/register or /gorevlerim| B[aiogram bot]
    B -->|AI draft extraction| G[Google Gemini]
    G -->|Validated WorkUpdate| B
    B -->|Employee-confirmed report| DB[(PostgreSQL / Neon)]
    A[Administrator] --> D[React dashboard]
    D -->|REST + JWT| API[FastAPI backend]
    API --> DB
    API -->|Plan drafts and weekly report narrative| G
```

### Employee registration

1. The employee sends `/register İsim Soyisim` in a private chat.
2. The bot asks for an optional position. The employee can answer `/atla` or let the administrator fill it in later.
3. A `registration_requests` row is created and the administrator receives Telegram approve/reject buttons.
4. Only an approval creates a new employee or reactivates an existing one. The applicant is notified of the decision.

### Work reporting

1. The employee sends `/gorevlerim` or `/rapor`.
2. The bot lists the tasks assigned to that active employee, together with the approved weekly target covering today when one exists.
3. The employee selects a task and writes a report in free text.
4. Gemini extracts the structured fields.
5. The bot shows a preview with separate labels for target and reported progress, plus blocker, delay, next step, and ETA information.
6. The employee can edit individual fields, cancel, or confirm.
7. Only a confirmation inserts a new row into `task_updates`. The original message, AI model, and normalized ETA date are stored with it.

### Weekly management reporting

1. The administrator opens **Raporlar → Haftalık Yönetici Raporları** and selects a week.
2. The backend builds a deterministic metrics snapshot, including plans, reports, classifications, conflicts, and intervention candidates.
3. Gemini writes the narrative from anonymous tokens and verified facts only.
4. The narrative is validated and stored as a numbered version for that week.
5. The dashboard renders project, employee, and task analyses, history comparison, data-quality notes, and manager interventions.

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Bot framework | [aiogram 3](https://aiogram.dev/) |
| AI | [Google Gemini](https://ai.google.dev/) via `google-genai` |
| Backend API | [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn |
| Validation | [Pydantic v2](https://docs.pydantic.dev/) |
| ORM | [SQLAlchemy 2.0 (async)](https://www.sqlalchemy.org/) |
| Database | PostgreSQL (Neon) + `asyncpg` |
| Migrations | Alembic |
| Authentication | Argon2 (`argon2-cffi`) + PyJWT |
| Frontend | React 19 + TypeScript + Vite |
| UI and styling | Tailwind CSS, accessible in-house components, `lucide-react` icons |
| Routing | React Router |
| Server state | TanStack Query |
| Frontend linting | oxlint |
| Config | `python-dotenv` |

---

## Project Structure

```text
weekly-work-tracker/
├── app/
│   ├── api/
│   │   ├── main.py              # FastAPI entry point (not the Telegram bot)
│   │   ├── config.py            # Dashboard environment settings
│   │   ├── security.py          # JWT creation/validation and revocation
│   │   ├── dependencies.py      # Bearer auth and DB session dependencies
│   │   ├── errors.py            # API error handling
│   │   └── routes/              # Auth, dashboard, projects, employees, tasks,
│   │                            # plans, registrations, reports, weekly reports
│   ├── bot/
│   │   ├── handlers.py          # /gorevlerim, preview, edit, confirm flows
│   │   ├── states.py            # FSM states for registration and reporting
│   │   ├── drafts.py            # Draft validation and field edits
│   │   ├── selection.py         # Task/plan snapshot helpers
│   │   └── formatting.py        # Turkish Telegram messages and keyboards
│   ├── database/
│   │   ├── connection.py        # Async engine and session factory
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   └── repositories.py      # Shared data-access helpers
│   ├── schemas/                 # Pydantic API and AI contracts
│   └── services/                # Business logic, AI services, metrics, validation
├── alembic/
│   └── versions/                # Schema migrations (0001–0004)
├── frontend/
│   ├── src/
│   │   ├── api/                 # REST client and endpoint functions
│   │   ├── components/          # UI and feature components
│   │   ├── hooks/               # Authentication context
│   │   ├── layouts/             # Sidebar/header application shell
│   │   ├── pages/               # Dashboard routes
│   │   ├── types/               # Shared TypeScript DTOs
│   │   └── App.tsx              # Router and providers
│   └── package.json
├── tests/                       # Automated backend tests
├── scripts/
│   └── hash_admin_password.py   # Argon2 password hash helper
├── alembic.ini
├── init_db.py                   # Fresh-start bootstrap only; prefer Alembic
├── main.py                      # Telegram bot entry point
├── requirements.txt
├── pytest.ini
├── .env                         # Local secrets (not committed)
└── .env.example                 # Placeholders only
```

---

## Getting Started

### Prerequisites

- Python **3.11+**
- Node.js **20+** and npm
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A Google Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)
- A PostgreSQL database (a free [Neon](https://neon.tech/) project works well)

### 1. Clone the repository

```bash
git clone https://github.com/dabbitz/weekly-worker-tracker.git
cd weekly-worker-tracker
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create `.env` in the project root:

```env
# Telegram
BOT_TOKEN=your-telegram-bot-token
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-3.5-flash-lite

# PostgreSQL (Neon)
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
DATABASE_URL_POOLED=postgresql://user:password@host/dbname?sslmode=require

# Telegram administrator (registration approval; not a dashboard login)
ADMIN_TELEGRAM_ID=123456789

# Admin dashboard
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=replace-with-an-argon2-hash
AUTH_SECRET=replace-with-at-least-32-random-characters
ACCESS_TOKEN_EXPIRE_MINUTES=480
# FRONTEND_ORIGIN=https://your-dashboard.example.com

# Optional frontend build-time value (never a secret)
# VITE_API_BASE_URL=http://127.0.0.1:8000/api
```

Notes:

- `GEMINI_MODEL` is optional and defaults to `gemini-3.5-flash-lite`.
- Generate the dashboard password hash without writing the plaintext password to a file:

  ```bash
  python scripts/hash_admin_password.py
  ```

  Copy the printed Argon2 hash into `ADMIN_PASSWORD_HASH`.
- `AUTH_SECRET` must be at least 32 characters.
- `ADMIN_TELEGRAM_ID` and `ADMIN_USERNAME` authenticate different channels and must stay separate.

### 5. Apply database migrations

```bash
# Windows
.\.venv\Scripts\python.exe -m alembic upgrade head

# macOS / Linux
.venv/bin/python -m alembic upgrade head
```

Apply migrations before using the dashboard or the bot. `init_db.py` exists for a fresh bootstrap, but it uses `Base.metadata.create_all()` and cannot alter existing tables, so Alembic is the supported path for schema changes.

### 6. Run the Telegram bot

```bash
python main.py
```

Open the bot in Telegram and send `/start`.

### 7. Run the admin API

```bash
# Windows (PowerShell)
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --port 8000

# macOS / Linux
.venv/bin/python -m uvicorn app.api.main:app --reload --port 8000
```

The API is available at `http://127.0.0.1:8000`, interactive docs at `http://127.0.0.1:8000/docs`, and the health check at `http://127.0.0.1:8000/api/health`.

### 8. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` and sign in with the configured `ADMIN_USERNAME` and password. The frontend reads `VITE_API_BASE_URL`, which defaults to `http://127.0.0.1:8000/api`. It is a public build-time value only; never put secrets in `VITE_*` variables.

The bot, API, and frontend run as three separate processes.

---

## Telegram Bot

| Command | Description |
| --- | --- |
| `/start` | Welcome message and basic usage guidance |
| `/help` | List available commands |
| `/myid` | Show the caller's Telegram user ID |
| `/register İsim Soyisim` | Start an approval-based registration request |
| `/gorevlerim` | List assigned tasks and start a work report |
| `/rapor` | Alias for `/gorevlerim` |

Only text reports are supported. Voice, audio, and video-note submissions receive a message explaining that voice reporting is not enabled.

### Registration and approval

- Registration works only in a private chat.
- Full name and surname are required; the position is optional.
- Position prompts can be skipped with `/atla` (or `/geç`, `-`, `yok`).
- Only one pending request per Telegram account is allowed. A rejected applicant can apply again.
- The administrator sees the request number, name, position, Telegram ID, and username, with **Onayla** / **Reddet** buttons.
- The administrator identity is checked against `ADMIN_TELEGRAM_ID`; the callback button alone is never trusted.
- Approval creates or reactivates the employee and notifies the applicant.
- The dashboard can display and delete registration requests, but it does not approve or reject them; those decisions stay in Telegram.

### Reporting flow

- Only active employees with a Telegram link can report.
- A report must be tied to a task assigned to that employee.
- The bot re-resolves the employee, task assignment, and weekly plan from the database when a report is submitted.
- Draft fields are clamped and validated before the preview is shown.
- Edits rotate the confirmation token, so an old button cannot confirm a newer draft.
- If the weekly plan changes between preview and confirmation, the stale preview is rejected instead of being saved.
- A confirmed report is stored with `review_status = approved`, meaning the employee approved the AI draft. It is not an administrator review decision.
- Reports are never overwritten; each message is an independent historical record.
- Missing task assignments or inactive employee records are rejected before anything is stored.

### Work status values

| Value | Meaning |
| --- | --- |
| `completed` | The entire reported task is finished |
| `in_progress` | Work is ongoing and can continue |
| `blocked` | Work cannot continue because of a stated obstacle |
| `not_started` | The employee explicitly says work has not started |
| `unknown` | Not enough information to determine status |

### Delays versus blockers

| Situation | Stored as |
| --- | --- |
| Work has stopped because of a stated obstacle | `status = blocked` and `blocker` |
| Work continues but the schedule is slipping | the working status (usually `in_progress`) and `delay_reason` |
| Both an obstacle and a delay are reported | both `blocker` and `delay_reason` |
| A completed task is mentioned with a past delay | `status = completed` |

A delay alone never sets the status to `blocked`, and a completed task is never downgraded because of a delay.

### Progress percentage estimation

- An explicitly stated percentage is used exactly.
- When no number is given but the message clearly describes overall progress, the assistant may infer an approximate value:

| Phrase | Inferred progress |
| --- | --- |
| "Daha yeni başladık." | 10 |
| "Yarısını tamamladık." | 50 |
| "Çoğu bitti." | 75 |
| "Neredeyse tamamladık." | 90 |
| "İşin tamamını bitirdik." | 100 |

- A vague message produces `null`; no default percentage is invented.
- A time expression such as "this week" does not turn a percentage into weekly progress.
- Values always stay between 0 and 100.

### Expected completion dates

- The original ETA expression is preserved in `reported_eta_text`.
- The backend normalizes it into `reported_eta_date` using the original Telegram message timestamp and `Europe/Istanbul`.
- Supported expressions include Turkish weekdays, day/month names, `yarın`, `bugün`, `öbür gün`, `haftaya cuma`, relative durations, and common numeric date formats.
- Dates of deliveries, meetings, inspections, and other events are not treated as task completion dates.
- When the date is ambiguous or unsupported, only the original expression is kept.

---

## Admin Dashboard

The dashboard is a Turkish-first React application. It talks only to the FastAPI backend, never directly to PostgreSQL.

| Page | Purpose |
| --- | --- |
| Genel Bakış | Real project, active employee, task, and pending registration counts; recent projects; first-step guidance |
| Projeler | Create, search, edit, and delete projects; open project detail |
| Proje Detayı | Project metadata, tasks, and employees derived from task assignments |
| Çalışanlar | Search employees, filter active/inactive, open employee detail |
| Çalışan Detayı | Assigned tasks, projects derived through those assignments, position editing |
| Görevler | Create/edit tasks, set planned dates, assign multiple employees, start AI weekly planning |
| Haftalık Planlar | Review drafts or create manual plans; edit, approve, reject, delete, and inspect AI notes |
| Kayıt Talepleri | Read-only Telegram registration history with status/search filters; decisions stay in Telegram |
| Raporlar | Employee work reports and AI-assisted weekly manager reports |

Key behavior:

- Projects can exist without tasks or employees.
- Creating a project never creates employees or assignments.
- A task can have multiple assignees through `task_assignments`.
- Inactive employees cannot be newly assigned to a task.
- Project teams are derived from `tasks → task_assignments → employees`; there is no `project_memberships` table.
- Employees without task assignments stay in the global employee list without being attached to a project.
- Weekly plan targets are separate from a task's planned start/due dates.
- Employees enter the system only through Telegram approval; the dashboard edits their position, not their identity.
- Deleting a project removes its planning data but is refused when historical reports reference its tasks or plans.
- Deleting an employee removes task assignments but is refused while historical reports reference that employee.
- Destructive actions require confirmation and show their effect before deletion.

---

## AI Weekly Planning

- The administrator selects one or more tasks on **Görevler**, optionally adds extra instructions, and requests a draft.
- Gemini returns a strictly validated multi-week plan. Every suggestion is stored as a `draft` with `source = ai`.
- Planning weeks start on Monday, last seven days, and are clipped to the task's planned start/due dates.
- `target_completion_percentage` is the **cumulative** completion expected at the end of that week, not the weekly increment.
- Percentages must be integers between 0 and 100 and must not decrease week over week.
- A draft can be edited, approved, rejected, or deleted. Manual plans use `source = manual`.
- Several drafts may coexist for the same task/week, but a partial unique index allows only **one approved plan per task/week**. Approving a conflicting draft requires explicit replacement confirmation; the previous approved plan becomes `superseded` instead of being deleted.
- Replacing an approved plan keeps the previous one as `superseded`. Plans can be deleted explicitly while no work report references them; a plan referenced by a report is protected until that report is removed.
- Generation requests are idempotent per `request_id` plus a content fingerprint, so retrying a failed request does not create duplicates.
- AI rationale, assumptions, and warnings are stored with each draft for administrator review.

### Weekly plan lifecycle

| Status | Meaning |
| --- | --- |
| `draft` | Editable suggestion, not yet official |
| `approved` | The single active plan for that task/week |
| `rejected` | Reviewed and declined; kept for history |
| `superseded` | Replaced by a newer approved plan; kept for history |

---

## Weekly Manager Reports

- **Raporlar → Haftalık Yönetici Raporları** creates a stored management report for one Monday–Sunday week. Generation is always started manually; there is no scheduler or background worker.
- A preview shows project scope, task and report counts, status counts, unassigned tasks, plan conflicts, missing target percentages, and intervention candidates before generation.
- All numbers come from the deterministic engine in `app/services/weekly_report_metrics.py`. Gemini only interprets those numbers and is rejected by validation if it introduces a number, date, token, or classification that is not in the deterministic snapshot.
- `target_completion_percentage` (weekly target) and `completion_percentage` (employee-reported progress) are never presented as the same value. Percentages from different employees are never averaged, and no project-level progress percentage is calculated.
- Only `approved` work reports enter activity metrics. `pending` reports are excluded from activity and counted separately; `rejected` reports are excluded.
- Missing reports are neutral (“Rapor gönderilmedi”); the report never states that an unreported task was not done.
- Weeks use Europe/Istanbul Monday–Sunday boundaries. The last completed week is the default; the current week can be generated with a “Kısmi değerlendirme” label, and future weeks are rejected.
- Report periods are selected from `TaskUpdate.received_at` (database insert time). The Telegram message timestamp is not stored as a separate column, so a report submitted near midnight may fall on the other side of a week boundary than the original message. This limitation is documented in the stored `metrics_snapshot.methodology` and shown in the report’s calculation explanation.
- The Gemini payload contains tokens (`E#`, `T#`, `P#`, `U#`, `W#`, `WEEK#`) and a separate generic `ai_references` map. It never contains employee names, Telegram user/chat/message IDs, database IDs, original messages, or secrets. Free-text fields are additionally scrubbed of known employee names before the call. Real IDs and snapshot labels stay in the stored `references` column and are returned only to the authenticated dashboard; they are never sent to Gemini.
- Large weeks are processed with a project-level map step and a final synthesis step so the prompt budget is respected.
- The report includes a general summary, project and employee analyses, task assessments, unmet-work analysis, comparison with prior weeks, recommendations, data-quality notes, and evidence-backed manager interventions. Priorities are AI suggestions; final decisions belong to the administrator.
- A `request_id` is unique. Repeating it with the same content returns the existing report without calling Gemini; using it with different content returns `409`. A new `request_id` creates a new version and keeps old versions. Failed versions can be retried in place.
- The history view lists versions with status filters and supports opening, retrying, and deleting report documents.
- `weekly_manager_reports` has no foreign keys to source tables, so deleting a task or employee cannot break stored report history. Deleting a report removes only that report document.
- The table is added by `alembic/versions/0003_weekly_manager_reports.py`. It is additive only and must be applied with the normal migration workflow before using the feature against a database.

---

## REST API

All endpoints below are served under `/api`. Every endpoint except `POST /auth/login` and `GET /health` requires a bearer token.

| Area | Endpoints |
| --- | --- |
| Authentication | `POST /auth/login`, `GET /auth/me`, `POST /auth/logout` |
| Health | `GET /health` |
| Dashboard | `GET /dashboard/summary` |
| Projects | `GET /projects`, `GET /projects/options`, `POST /projects`, `GET /projects/{id}`, `PATCH /projects/{id}`, `DELETE /projects/{id}`, `GET /projects/{id}/tasks`, `GET /projects/{id}/employees`, `GET /projects/{id}/deletion-preview` |
| Employees | `GET /employees`, `GET /employees/{id}`, `PATCH /employees/{id}`, `DELETE /employees/{id}` |
| Tasks | `GET /tasks`, `POST /tasks`, `GET /tasks/{id}`, `PATCH /tasks/{id}`, `DELETE /tasks/{id}`, `PUT /tasks/{id}/assignments` |
| Weekly plans | `GET /weekly-plans`, `POST /weekly-plans`, `POST /weekly-plans/ai/generate`, `GET /weekly-plans/{id}`, `PATCH /weekly-plans/{id}`, `POST /weekly-plans/{id}/approve`, `POST /weekly-plans/{id}/reject`, `DELETE /weekly-plans/{id}` |
| Registration requests | `GET /registration-requests`, `GET /registration-requests/{id}`, `DELETE /registration-requests/{id}` |
| Work reports | `GET /reports`, `GET /reports/{id}`, `DELETE /reports/{id}` |
| Weekly manager reports | `GET /weekly-reports/periods`, `GET /weekly-reports/preview`, `GET /weekly-reports`, `POST /weekly-reports`, `GET /weekly-reports/{id}`, `POST /weekly-reports/{id}/retry`, `DELETE /weekly-reports/{id}` |

List endpoints use pagination (`page`, `page_size`) and support search or filters where relevant. Database access always goes through FastAPI.

---

## Data Model

```mermaid
erDiagram
    EMPLOYEES ||--o{ TASK_ASSIGNMENTS : has
    TASKS ||--o{ TASK_ASSIGNMENTS : assigned_to
    PROJECTS ||--o{ TASKS : contains
    TASKS ||--o{ WEEKLY_TASK_PLANS : planned_in
    WEEKLY_PLAN_GENERATIONS ||--o{ WEEKLY_TASK_PLANS : produces
    TASKS ||--o{ TASK_UPDATES : receives
    WEEKLY_TASK_PLANS ||--o{ TASK_UPDATES : contextualizes
    EMPLOYEES ||--o{ TASK_UPDATES : submits
    EMPLOYEES ||--o{ REGISTRATION_REQUESTS : applies
```

| Table | Purpose |
| --- | --- |
| `employees` | Staff members, optionally linked to a Telegram user ID; includes the optional job position |
| `registration_requests` | Telegram registration history with status and requested position |
| `projects` | Projects with description, location, and expected completion date |
| `tasks` | Work items belonging to a project, with planned dates and generated weekday columns |
| `task_assignments` | Many-to-many link between tasks and employees |
| `weekly_task_plans` | Weekly targets per task with lifecycle status, source, and AI notes |
| `weekly_plan_generations` | One AI generation request, grouping the drafts it produced |
| `task_updates` | Confirmed work reports, extracted fields, review state, and sync state |
| `weekly_manager_reports` | Self-contained weekly manager report documents, metrics snapshots, references, and narratives |

`task_updates.review_status` records the employee's confirmation of the AI draft. The stored value is `approved` when a report is saved; the `pending` and `rejected` values remain available in the schema but are not used as a dashboard approval workflow. `sync_status` is reserved for future external synchronization.

---

## Testing

### Automated backend tests

```bash
# Windows (PowerShell)
.\.venv\Scripts\python.exe -m pytest tests -q

# macOS / Linux
.venv/bin/python -m pytest tests -q
```

The suite runs against isolated, randomly named PostgreSQL schemas on the configured Neon database and removes them afterwards. It does not modify rows in the `public` schema.

Covered areas include dashboard authentication, project/employee/task CRUD, task assignments, inactive-employee assignment rules, weekly plans, AI weekly planning, Telegram registration and report flows, work-update extraction, date normalization, weekly manager report metrics, validation, and the weekly-report API.

### Manual smoke tests

```bash
# Verify the database connection
python test_db.py

# Run a single AI extraction against a sample message
python test_ai.py

# Exercise Turkish ETA normalization
python test_date_normalizer.py
```

All three scripts load configuration from `.env` and dispose of their connections before exiting.

### Frontend checks

```bash
cd frontend
npm run build
npm run lint
```

---

## Security Notes

- `.env` is git-ignored — **never commit real tokens or database credentials**.
- The AI system instruction explicitly rejects prompt-injection attempts inside employee messages and administrator notes.
- Database identifiers are always generated by the backend; the model is never asked to produce them.
- SSL is enabled for database connections by default.
- The dashboard stores only an Argon2 password hash and signs short-lived JWTs with `AUTH_SECRET`.
- Dashboard tokens are kept in `sessionStorage`, and logout revokes the token ID.
- CORS is limited to the local Vite origins and an optional configured frontend origin; wildcard origins with credentials are not used.
- Dashboard secrets are backend-only environment variables and never appear in `VITE_*` variables.
- Weekly manager report payloads use anonymous tokens; real identifiers and employee names are never sent to Gemini.
- Telegram callback data is always verified against `ADMIN_TELEGRAM_ID` before a registration decision is applied.

---

## Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/my-feature`.
3. Commit your changes: `git commit -m "Add my feature"`.
4. Push the branch: `git push origin feature/my-feature`.
5. Open a pull request.

---

## License

No license has been specified yet. Contact the repository owner before using this project in production or redistributing it.
