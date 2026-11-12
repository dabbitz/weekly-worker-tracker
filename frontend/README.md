# WorkTrack Yönetim Paneli

Turkish-first administrator dashboard for WorkTrack. React + TypeScript +
Vite, with TanStack Query for server state and React Router for navigation.

## Development

The backend API must be running first:

```bash
# From the repository root
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --port 8000
```

Then start the frontend:

```bash
npm install
npm run dev
```

Open `http://localhost:5173`. Sign in with the backend's
`ADMIN_USERNAME` and the password matching `ADMIN_PASSWORD_HASH`.

## Configuration

The API base URL defaults to `http://127.0.0.1:8000/api`. To override it,
copy `.env.example` to `.env.local` and set `VITE_API_BASE_URL`.

Only public, build-time values belong in `VITE_*` variables. Never put
database URLs, bot tokens, Gemini keys, JWT secrets, or password hashes in
the frontend environment.

## Checks

```bash
npm run build   # TypeScript project build + Vite production bundle
npm run lint    # Oxlint
```

## Production hosting

`vite build` writes static assets to `dist/`. The app uses client-side
routing, so the host must rewrite unknown paths to `index.html`.
