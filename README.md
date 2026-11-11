# Weekly Work Tracker

A Telegram bot that turns free-form work updates from office and construction site employees into clean, structured data using Google Gemini — and stores them in a PostgreSQL (Neon) database.

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
│   ├── database/
│   │   ├── connection.py      # Async engine & session factory
│   │   ├── models.py          # ORM models
│   │   └── repositories.py    # Data access layer (in progress)
│   ├── schemas/
│   │   └── work_update.py     # WorkUpdate / WorkStatus schemas
│   └── services/
│       └── ai_service.py      # Gemini extraction service
├── init_db.py                 # Creates database tables
├── main.py                    # Telegram bot entry point
├── test_ai.py                 # Manual AI extraction test
├── test_db.py                 # Manual database connectivity test
├── requirements.txt
└── .env                       # Local secrets (not committed)
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
```

> **Note:** `GEMINI_MODEL` is optional and defaults to `gemini-3.5-flash-lite`.

### 5. Initialize the database

```bash
python init_db.py
```

### 6. Run the bot

```bash
python main.py
```

Open your bot in Telegram and send `/start`.

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
| `weekly_task_plans` | Weekly targets per task, including target completion % |
| `task_updates` | AI-extracted updates, review status, and sync state |

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

The project includes two manual smoke tests:

```bash
# Verify the database connection
python test_db.py

# Run a single AI extraction against a sample message
python test_ai.py
```

Both scripts load configuration from `.env` and exit cleanly, disposing of connections.

---

## Security Notes

- `.env` is git-ignored — **never commit real tokens or database credentials**.
- The AI system instruction explicitly rejects prompt-injection attempts inside employee messages.
- Database identifiers are always generated by the backend; the model is never asked to produce them.
- SSL is enabled for database connections by default.

---

## Roadmap

- [ ] Persist analyzed updates to `task_updates`
- [ ] Match `task_reference_text` to existing tasks
- [ ] Normalize relative ETAs (e.g. *"cuma"*) into calendar dates using the Telegram message timestamp and `Europe/Istanbul`
- [ ] Weekly summary and reporting endpoints
- [ ] Manager review flow (approve / reject updates)
- [ ] External system synchronization
- [ ] Alembic migrations instead of `create_all`
- [ ] Automated test suite

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
