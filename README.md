# TestFlow

TestFlow is a web app for exam practice. Users create or import exams, take them in timed or practice mode, and review their results. Exams are private by default and become public only after a reviewer approves them.

The user interface is in Vietnamese.

## Features

- Accounts with Student, Reviewer, and Admin roles
- An exam library with search and filters by level, subject, and exam type
- Exam creation in the browser, one question at a time
- Import from plain-text files, with a review step before saving
- Six question types: single choice, multiple choice, true/false, grouped true/false statements, short answer, and essay
- Timed mode, which hides answers until you submit, and practice mode, which shows the answer after each question
- Scores, per-question feedback, and a history of past attempts
- Publishing: owners request to make an exam public, and reviewers approve or reject the request
- An admin page with import activity and pending publish requests
- Light, dark, and system display modes with several color themes

## Tech stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.11, Django, Django REST Framework, Celery |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Database and queue | PostgreSQL, Redis |
| Testing | pytest, Vitest, Playwright |

## Requirements

- Python 3.11
- Node.js 24 and npm
- Docker with Docker Compose (for PostgreSQL and Redis)
- GNU Make (optional, for the `make` commands)

## Getting started

### Linux and macOS

```sh
make setup
make dev
```

`make setup` installs the backend and frontend dependencies, builds the theme files, and creates a `.env` file with a random secret key. `make dev` starts PostgreSQL and Redis, applies migrations, and runs the API, the background worker, and the web app.

Open <http://localhost:5173>.

### Windows (PowerShell)

Set up the project:

```powershell
python scripts\init_env.py
python -m venv backend\.venv
backend\.venv\Scripts\pip.exe install -r backend\requirements-dev.txt
backend\.venv\Scripts\pip.exe install -e contracts
npm --prefix frontend ci
python design\build_tokens.py
docker compose -f compose.dev.yml up -d --wait
backend\.venv\Scripts\python.exe backend\manage.py migrate
```

Then run each of these in its own terminal:

```powershell
backend\.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000
```

```powershell
cd backend
.venv\Scripts\celery.exe -A config worker -l info --pool=solo
```

```powershell
npm --prefix frontend run dev
```

Open <http://localhost:5173>.

## Licensed Quiz Rush sample deck

The owner authorized use and distribution of the built-in 300-question Computer Vision deck. The exported [TXT fixture](data/seed/quiz-rush-cv.txt) is committed in TestFlow, so the app has no runtime dependency on `quiz-rush`.

Create two distinct Admin/Reviewer accounts first. Then run:

```powershell
backend\.venv\Scripts\python.exe backend\manage.py seed_quiz_rush --owner ADMIN_USERNAME --reviewer REVIEWER_USERNAME
```

The command creates the deck privately through the normal exam service, then requests and approves publication through the existing moderation services. It is idempotent. Omitting `--reviewer` leaves the deck private. The fixture can be reproduced from the authorized legacy source with `backend\.venv\Scripts\python.exe scripts\check_quiz_rush_parser.py T:\coding\quiz-rush\js\data.js --output data\seed\quiz-rush-cv.txt`; the converter checks all 300 questions and answers before writing.

## Configuration

Settings are read from `.env` in the project root. See [.env.example](.env.example) for all variables.

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Django secret key |
| `DJANGO_DEBUG` | Debug mode (`1` or `0`) |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated list of allowed hostnames |
| `DJANGO_HSTS_SECONDS` | Production HSTS duration; set only after HTTPS and domain verification (default: 0) |
| `DATABASE_URL` | PostgreSQL connection URL |
| `REDIS_URL` | Redis connection URL |
| `CORS_ALLOWED_ORIGINS` | Origins allowed to call the API |
| `IMPORT_DAILY_JOB_LIMIT` | Maximum number of imports per user per day (default: 20) |
| `BUILD_SHA` | Revision shown in the admin operations summary (default: `local`) |
| `VITE_API_BASE_URL` | API address used by the web app |

The database password in `.env.example` is for local development only. PostgreSQL and Redis listen on `127.0.0.1` only.

Local health, logs, quota, and admin operations checks are described in [the operations runbook](docs/runbooks/local-operations.md).

## Importing exams from text

A text file starts with the exam title, followed by chapters and questions. Each question lists its options and marks the correct answer with `=>`:

```text
#TITLE: Basic Math
[C1] Arithmetic
What is 2 + 2?
A. 3
B. 4
=>B
```

Invalid questions are skipped and listed with a reason, so one bad question does not stop the whole import. Files must be UTF-8 encoded.

## API

The API is served under `/api/v1/`:

| Path | Purpose |
| --- | --- |
| `/api/v1/auth/` | Registration, login, token refresh, logout, profile |
| `/api/v1/exams/` | Exam library and exam details |
| `/api/v1/practice/` | Practice sessions, answers, and results |
| `/api/v1/imports/` | Text imports and draft review |
| `/api/v1/ops/` | Operations summary (admins only) |
| `/api/v1/taxonomy/lookup/` | Resolve a canonical subject, school or major and suggest close names |
| `/api/v1/taxonomy/names/` | Create a new canonical name explicitly, or reuse an existing exact match |
| `/api/v1/taxonomy/profile-school/` | Set the authenticated user's profile school from the canonical catalog |
| `/api/v1/schema/` | OpenAPI schema |
| `/healthz` | Database and Redis health check |

Access tokens are short-lived. The refresh token is stored in an HttpOnly cookie.

In manual exam creation, TXT review and account profile, enter a subject, school or major and use **Kiểm tra tên**. Case and whitespace variants resolve to the canonical record. Close spellings are suggestions; select the right one or explicitly choose **Tạo tên mới**. A new name becomes available immediately without Admin review. Exams and profile school reference canonical names. [Decision and limits](docs/adr/025-reviewed-taxonomy-names.md).

## Testing

Run all checks:

```sh
make check
```

Or run them one by one. Start PostgreSQL and Redis first.

```sh
backend/.venv/bin/ruff check backend contracts
backend/.venv/bin/mypy --config-file backend/pyproject.toml backend/apps backend/config contracts/testflow_contracts
cd backend && .venv/bin/lint-imports --config .importlinter
backend/.venv/bin/pytest -c backend/pytest.ini backend/tests -q
```

On Windows, use `backend\.venv\Scripts\` instead of `backend/.venv/bin/`.

Frontend checks (from `frontend/`):

```sh
npm run check     # type check and unit tests
npm run build
npm run e2e       # browser tests
```

The browser tests start the API and the web app, and create test accounts in the local development database.

## Project structure

```text
backend/
  apps/
    accounts/     Users, roles, and authentication
    catalog/      Exams, questions, library, and publishing
    imports/      Text import and draft review
    practice/     Sessions, grading, and results
    ops/          Admin operations summary
    common/       Shared errors, logging, and helpers
  config/         Django settings and URLs
  tests/          Backend tests
contracts/        Shared exam data format
design/           Color palette and theme tokens
eval/             Scoring tool for exam extraction models
frontend/
  src/            Web app
  e2e/            Browser tests
```

The backend is split into Django apps with fixed dependency rules, which `lint-imports` checks. Business logic lives in each app's `services.py`, and views stay thin.
