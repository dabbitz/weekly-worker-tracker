# Weekly Work Tracker

A Telegram bot that turns free-form work updates from office and construction site employees into clean, structured data using Google Gemini, plus a Turkish-first administrator dashboard for managing projects, employees, tasks, assignments, and weekly plans on a PostgreSQL (Neon) database.

> "We completed about 70% of the electrical installation this week. We couldn't finish the rest because of a cable supply issue. If the materials arrive tomorrow, we plan to finish by Friday."
>
> ↓ ↓ ↓

```json
{
  "task_reference_text": "electrical installation",
  "status": "blocked",
  "completion_percentage": 70,
  "blocker": "cable supply issue",
  "next_step": "finish the remaining work once materials arrive",
  "reported_eta_text": "cuma gününe kadar",
  "summary": "Elektrik tesisatının %70'i tamamlandı. Kablo tedarik sorunu nedeniyle kalan kısım bitirilemedi. Malzemeler yarın gelirse cuma gününe kadar tamamlanması planlanıyor."
}
```

---

## Features

- **Natural language input** — employees simply describe their progress in Turkish or English.
- **Structured extraction** — Gemini returns a validated `WorkUpdate` schema via Pydantic.
- **No hallucinated numbers** — percentages, dates, and blockers are extracted only when explicitly stated.
- **Smart status classification** — distinguishes `completed`, `in_progress`, `blocked`, `not_started`, and `unknown`.
- **Prompt-injection resistant** — the model is instructed to treat messages strictly as data.
- **Relational data model** — employees, projects, tasks, assignments, weekly plans, and updates.
- **Review workflow ready** — updates support `pending` / `approved` / `rejected` states.
- **Integration ready** — updates carry a `sync_status` for future external system sync.
- **Async everywhere** — `aiogram`, SQLAlchemy async engine, and `asyncpg`.
- **Admin dashboard** — Turkish-first React interface backed by a FastAPI API and the same PostgreSQL database.
- **AI weekly planning** — select several tasks, add extra instructions, and let Gemini draft multi-week targets as reviewable drafts.
- **Draft-first approvals** — AI plans are never official until an administrator approves them; edits, rejection, and regeneration keep a full history.
- **Real data only** — no seeded demo records or fabricated metrics.
- **Derived project teams** — employees are associated with projects through task assignments, not a separate membership table.

---

## How It Works

```mermaid
flowchart LR
    A[Employee] -->|Telegram message| B[🤖 aiogram bot]
    B --> C[WorkUpdateExtractor]
    C -->|Structured output| D[WorkUpdate schema]
    D --> E[Formatted reply]
    C -.->|planned| F[(PostgreSQL / Neon)]
```

1. The employee sends a free-text update to the bot.
2. `WorkUpdateExtractor` sends the message to Gemini with a strict system instruction and a JSON response schema.
3. The response is validated into a `WorkUpdate` Pydantic model.
4. The bot formats and returns a readable analysis in Turkish.
5. *(Planned)* The update is persisted to the database for weekly reporting.

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Bot framework | [aiogram 3](https://aiogram.dev/) |
| AI | [Google Gemini](https://ai.google.dev/) via `google-genai` |
| Validation | [Pydantic v2](https://docs.pydantic.dev/) |
| ORM | [SQLAlchemy 2.0 (async)](https://www.sqlalchemy.org/) |
| Database | PostgreSQL (Neon) + `asyncpg` |
| Migrations | Alembic |
| Config | `python-dotenv` |

---

## Project Structure

```text
weekly-work-tracker/
├── app/
│   ├── api/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Dashboard environment settings
│   │   ├── dependencies.py      # Bearer auth and DB session dependencies
│   │   └── routes/              # Auth, dashboard, projects, employees, tasks, plans
│   ├── database/
│   │   ├── connection.py        # Async engine & session factory
│   │   └── models.py            # ORM models
│   ├── schemas/                 # Pydantic request/response models
│   └── services/                # Business logic shared by the API and the bot
├── alembic/
│   └── versions/                # Reversible schema migrations
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
├── alembic.ini                  # Alembic configuration
├── init_db.py                   # Legacy table bootstrap (prefer Alembic)
├── main.py                      # Telegram bot entry point
├── requirements.txt
├── .env                         # Local secrets (not committed)
└── .env.example                 # Placeholders only
```

---

## Getting Started

### Prerequisites

- Python **3.11+**
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

Create a `.env` file in the project root:

```env
# Telegram
BOT_TOKEN=your-telegram-bot-token
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-3.5-flash-lite

# PostgreSQL (Neon)
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
DATABASE_URL_POOLED=postgresql://user:password@host/dbname?sslmode=require

# Telegram administrator (bot approval flow; not a dashboard login)
ADMIN_TELEGRAM_ID=123456789

# Admin dashboard
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=replace-with-an-argon2-hash
AUTH_SECRET=replace-with-at-least-32-random-characters
ACCESS_TOKEN_EXPIRE_MINUTES=480
# FRONTEND_ORIGIN=https://your-dashboard.example.com
```

> **Note:** `GEMINI_MODEL` is optional and defaults to `gemini-3.5-flash-lite`.
>
> Generate the dashboard password hash without putting the plaintext
> password in a file:
>
> ```bash
> python scripts/hash_admin_password.py
> ```
>
> Copy the printed Argon2 hash into `ADMIN_PASSWORD_HASH`. Keep
> `ADMIN_TELEGRAM_ID` separate from `ADMIN_USERNAME`; they authenticate
> different channels. `AUTH_SECRET` must be at least 32 characters.

### 5. Initialize / migrate the database

```bash
# Apply all schema migrations
.\.venv\Scripts\python.exe -m alembic upgrade head
```

`init_db.py` still exists for a fresh bootstrap, but it uses
`Base.metadata.create_all()` and therefore cannot alter existing tables.
Use Alembic for every schema change; migrations are reviewed and
reversible.

### 6. Run the bot

```bash
python main.py
```

Open your bot in Telegram and send `/start`.

### 7. Run the admin API

```bash
# Windows (PowerShell)
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --port 8000

# macOS / Linux
.venv/bin/python -m uvicorn app.api.main:app --reload --port 8000
```

The API is available at `http://127.0.0.1:8000`, interactive docs at
`http://127.0.0.1:8000/docs`, and the health check at
`http://127.0.0.1:8000/api/health`.

### 8. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` and sign in with the configured
`ADMIN_USERNAME` and password. The frontend reads
`VITE_API_BASE_URL`, which defaults to `http://127.0.0.1:8000/api`.
It is a public build-time value only; never put secrets in `VITE_*`
variables.

---

## Admin Dashboard

The dashboard is a separate process from the Telegram bot and connects
to the same Neon database through the FastAPI backend.

| Page | Purpose |
| --- | --- |
| Genel Bakış | Real project, active employee, task, and pending registration counts |
| Projeler | Create, search, and edit projects; open project detail |
| Proje Detayı | Project metadata, tasks, and employees derived from task assignments |
| Çalışanlar | Search employees and open employee detail |
| Çalışan Detayı | Assigned tasks and projects derived through those assignments |
| Görevler | Create/edit tasks, assign multiple employees, and start AI weekly planning for selected tasks |
| Haftalık Planlar | Review AI drafts or create manual plans; edit, approve, reject, regenerate, and inspect history |
| Kayıt Talepleri | Read-only Telegram registration history; decisions stay in Telegram |
| Raporlar | Clearly marked later-phase report plan with no fabricated metrics |

Key behavior:

- Projects can exist without tasks or employees.
- A task may have multiple assignees through `task_assignments`.
- Inactive employees cannot be newly assigned to a task.
- Project teams are derived from `tasks → task_assignments → employees`;
  there is no `project_memberships` table.
- Weekly plan targets are separate from a task's planned start/due dates.
- Dashboard authentication uses an Argon2 password hash and a signed,
  expiring JWT. Every admin endpoint except login and health requires a
  bearer token.

### AI weekly planning

- The administrator selects one or more tasks on **Görevler**, optionally
  adds extra instructions, and requests a draft.
- Gemini returns a strictly validated multi-week plan; every suggestion is
  stored as a `draft` with `source = ai` and is never official on its own.
- Planning weeks start on Monday, last seven days, and are clipped to the
  task's planned start/due dates.
- `target_completion_percentage` is the **cumulative** completion expected
  at the end of that week, not the weekly increment.
- A draft can be edited, approved, rejected, deleted, or regenerated.
  Manual plans use `source = manual`.
- Several drafts may coexist for the same task/week, but a partial unique
  index allows only **one approved plan per task/week**. Approving a
  conflicting draft requires an explicit replacement confirmation, and the
  previous approved plan becomes `superseded` instead of being deleted.
- Approved plans (and plans referenced by `task_updates`) are never
  physically removed; history is preserved.
- Generation requests are idempotent per `request_id` plus a content
  fingerprint, so retrying a failed request does not create duplicates.

---

## Bot Commands

| Command | Description |
| --- | --- |
| `/start` | Welcome message and usage example |
| `/help` | Show available commands |
| *any text* | Analyze the message as a work update |

### Example

**Input**

```text
Bu hafta elektrik tesisatının yaklaşık %70'ini tamamladık.
Ancak kablo tedarikinde sorun yaşadığımız için kalan kısmı
bitiremedik. Malzemeler yarın gelirse cuma gününe kadar
bitirmeyi planlıyoruz.
```

**Output**

```text
İŞ GÜNCELLEMESİ ANALİZİ

İş: elektrik tesisatı
Durum: Engellendi
Gerçekleşme: %70
Engel: kablo tedarikinde sorun
Sonraki adım: malzemeler geldiğinde kalan işi bitirmek
Tahmini tamamlanma: cuma gününe kadar

ÖZET
Elektrik tesisatının %70'i tamamlandı. Kablo tedarik sorunu
nedeniyle kalan kısım bitirilemedi. Malzemeler yarın gelirse
cuma gününe kadar tamamlanması planlanıyor.

Bu, yapay zekâ tarafından oluşturulmuş bir analizdir.
```

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
```

| Table | Purpose |
| --- | --- |
| `employees` | Staff members, optionally linked to a Telegram user ID |
| `projects` | Projects with location and expected completion date |
| `tasks` | Work items belonging to a project, with planned dates |
| `task_assignments` | Many-to-many link between tasks and employees |
| `weekly_task_plans` | Weekly targets per task with lifecycle status, source, and AI notes |
| `weekly_plan_generations` | One AI generation request, grouping the drafts it produced |
| `task_updates` | AI-extracted updates, review status, and sync state |

### Weekly plan lifecycle

| Status | Meaning |
| --- | --- |
| `draft` | Editable suggestion, not yet official |
| `approved` | The single active plan for that task/week |
| `rejected` | Reviewed and declined; kept for history |
| `superseded` | Replaced by a newer approved plan; kept for history |

Plans also record their `source` (`manual` or `ai`), the optional AI note,
and the administrator/timestamp of the approval.

### Work status values

| Value | Meaning |
| --- | --- |
| `completed` | The entire reported task is finished |
| `in_progress` | Work is ongoing and can currently continue |
| `blocked` | Work cannot continue due to a stated obstacle |
| `not_started` | The employee explicitly says work has not started |
| `unknown` | Not enough information to determine status |

---

## Testing

### Automated backend tests

```bash
# Windows (PowerShell)
.\.venv\Scripts\python.exe -m pytest tests -q

# macOS / Linux
.venv/bin/python -m pytest tests -q
```

The suite runs against isolated, randomly named PostgreSQL schemas on
the configured Neon database and removes them afterwards. It does not
modify rows in the `public` schema.

Covered areas include dashboard authentication, project/employee/task
CRUD, task assignments, weekly plans, and the AI weekly planning workflow
(structured output validation, date and percentage rules, idempotency,
approval/replacement, history protection, and unauthenticated access).

### Manual smoke tests

The project also includes two manual smoke tests:

```bash
# Verify the database connection
python test_db.py

# Run a single AI extraction against a sample message
python test_ai.py
```

Both scripts load configuration from `.env` and exit cleanly, disposing of connections.

### Frontend checks

```bash
cd frontend
npm run build
npm run lint
```

---

## Security Notes

- `.env` is git-ignored — **never commit real tokens or database credentials**.
- The AI system instruction explicitly rejects prompt-injection attempts inside employee messages.
- Database identifiers are always generated by the backend; the model is never asked to produce them.
- SSL is enabled for database connections by default.
- The dashboard stores only an Argon2 password hash and signs short-lived JWTs with `AUTH_SECRET`.
- Dashboard tokens are kept in `sessionStorage`, and logout revokes the token ID.
- CORS is limited to the local Vite origins; wildcard origins with credentials are not used.
- Dashboard secrets are backend-only environment variables and never appear in `VITE_*` variables.

---

## Roadmap

- [ ] Persist analyzed updates to `task_updates`
- [ ] Match `task_reference_text` to existing tasks
- [ ] Normalize relative ETAs (e.g. *"cuma"*) into calendar dates using the Telegram message timestamp and `Europe/Istanbul`
- [ ] Weekly summary and reporting endpoints
- [ ] Manager review flow (approve / reject updates)
- [ ] External system synchronization
- [x] Alembic migrations instead of `create_all`
- [x] AI-assisted multi-week plan drafts with admin approval
- [x] Automated backend test suite and Turkish admin dashboard

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
