# TestFlow implementation status

Updated: 2026-11-05 09:15 ICT. Current checkpoint: S0/S1 local gates pass. S1b publication and TXT import run end-to-end locally; Quiz Rush source matched 300/300 read-only. S2 has an offline evaluator but no real gold set. Independent S3 quota/state-machine and S5/S6 local operations work is partial. S1b legal migration and S2–S6 exit gates remain open. Hosted CI and clean Linux bootstrap remain unverified. This is the resume point for interrupted sessions. Evidence below records actual commands only.

| Slice | Requirements | Implementation files | Tests | Last command/result | State | Blocker | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Intake | PRD §§1–23; execution contract | `docs/prd.md`, `docs/agent-master-prompt.md`, `docs/implementation/*` | Document audit | Both source specs read in full; `git init -b main` succeeded; Quiz Rush RAW = 300 questions / 4 chapters | IMPLEMENTED | None | Preserve as reference |
| S0 | FR-A1/A2/A3/A4, FR-T1/T2/T3/T4; NFR-7/8/9 | `backend/apps/accounts`, `backend/config`, `frontend/src`, `design`, `compose.dev.yml`, `.github/workflows/ci.yml` | `backend/tests/test_accounts.py`, `frontend/src/App.test.tsx`, `frontend/e2e/auth.spec.ts` | PostgreSQL and Redis healthy; migrations applied; 4 DB/API tests pass; 2 component tests pass; 2 real Chrome E2E pass (including axe accessibility and 360px overflow); Ruff, mypy, import-linter, schema, 288 contrast checks, frontend build pass; Celery inspect ping returns pong | LOCAL PASS / CI UNVERIFIED | No remote repository or hosted CI run; Linux `make setup && make dev` not executed | Begin S1; run hosted CI when remote is provided |
| S1 | Manual exam, catalog, grading, timed practice | `contracts/testflow_contracts/exam.py`, `backend/apps/catalog`, `backend/apps/practice`, `frontend/src/{catalog,practice}.tsx`, `backend/apps/catalog/management/commands/seed_thpt_demo.py` | `backend/tests/{test_catalog,test_grading,test_practice}.py`, `frontend/e2e/{catalog,practice}.spec.ts` | 33 backend tests and 5 Chrome E2E pass, including full self-authored three-section THPT exam scoring 10/10; 18 pure grading cases; auto-save, flag/reload, practice feedback, private isolation, history; Ruff, mypy, 5 import contracts, OpenAPI validation, TypeScript, Vitest, Vite build pass | LOCAL PASS / CI UNVERIFIED | Hosted CI and clean Linux bootstrap unavailable | Begin S1b; run hosted CI when remote exists |
| S1b | TXT, privacy, publication, wrong bank, 300-question migration | `backend/apps/catalog`, `backend/apps/imports`, `frontend/src/{publication,imports}.tsx` | `backend/tests/{test_publication,test_txt_parser,test_txt_import}.py`, `frontend/e2e/{publication,imports}.spec.ts`, `scripts/check_quiz_rush_parser.py` | 51 backend tests and 9 Chrome E2E pass; import-linter 9/9, Ruff, mypy, OpenAPI, TS/Vitest/build pass; read-only Quiz Rush comparison 300/300 questions, 4 chapters, 0 skipped/issues; per-user TXT quota pass | IN PROGRESS | Legal rights before copying or distributing legacy questions; no hosted CI | Complete retained-behavior matrix, accessible question review UX and legal migration decision |
| S2 | Gold set and E1–E5 OCR evaluation | `eval/run.py`, `eval/README.md`, `docs/experiments/README.md` | `backend/tests/test_eval.py` | Offline metric runner and synthetic smoke tests implemented; no real OCR numbers | BLOCKED EXTERNAL | Legally usable 30-exam gold set and actual extractor outputs/GPU/provider capacity | Annotate real gold set, run E1–E5, inspect failures, decide extractor |
| S3 | Document import pipeline | `backend/apps/imports/{models,services}.py` for shared states, SHA dedup and TXT quota only | `backend/tests/test_txt_import.py` state matrix, quota and cleanup | Full 8×8 ImportJob transition matrix and daily TXT quota pass; no document upload or OCR | PARTIAL FOUNDATION | S2 extractor decision for production OCR | Implement document ingestion, page processing, retry and fake CI path |
| S4 | Review and moderation UI | Planned | Planned | Not run | NOT STARTED | S3 | Close S3 |
| S5 | R1 completion and E2E/security/performance | `backend/apps/common/{health,request_logging}.py`, `backend/apps/ops`, `frontend/src/ops.tsx` | `backend/tests/{test_health,test_ops}.py`, `frontend/e2e/ops.spec.ts` | `/healthz` DB/Redis probe, request ID, JSON logs and Admin summary pass locally; 51 backend and 9 Chrome E2E pass | PARTIAL LOCAL | S2–S4, real OCR/performance/security audit | Add measured metrics, remaining routes, privacy/performance gates |
| S6 | Production operations/deployment | `docs/runbooks/local-operations.md` and local observability only | Local health and Admin E2E | Local Docker Engine 28.2.2 and PostgreSQL/Redis healthy; no host/domain/backup destination or deployed smoke | BLOCKED EXTERNAL | Infrastructure, credentials, legal source rights, release authorization | Finish repo artifacts, then stage/deploy only with authorized access |

## Verified intake commands

| Command/check | Result |
| --- | --- |
| `Get-Content -Raw -Encoding utf8` on both source specs | Read in full before implementation |
| `node` evaluation of Quiz Rush `js/data.js` | `RAW.length=300`, chapters `C12=80`, `C3=90`, `C4=70`, `C5=60` |
| `git -C T:\coding\testflow status` before initialization | No repository existed |
| `git init -b main` in TestFlow | Succeeded |
| `docker info --format '{{.ServerVersion}}'` | Initially failed; after starting Docker Desktop outside sandbox returned `28.2.2` |
| `nvidia-smi` | Command unavailable; GPU not verified |

## S0 local gate evidence

| Command/check | Observed result |
| --- | --- |
| `docker compose -f compose.dev.yml up -d --wait` | PostgreSQL and Redis both healthy |
| `backend/.venv/Scripts/python.exe backend/manage.py migrate --noinput` | Migrations through `accounts.0003_user_display_name` applied |
| `backend/.venv/Scripts/pytest.exe -c backend/pytest.ini backend/tests -q` | 4 passed against PostgreSQL |
| `npm run check` in frontend | TypeScript and 2 Vitest tests passed |
| `npm run e2e` in frontend | 2 Chrome tests passed: identity/profile/refresh/logout/login and theme persistence; axe reported 0 violations on register/account; 360px layout had no horizontal overflow |
| `npm run build` in frontend | Vite production build passed |
| Ruff, mypy, import-linter | All passed; import-linter: 1 contract kept |
| `manage.py spectacular --validate --fail-on-warn` | Passed with no warnings after serializer fixes |
| `python design/palette.py` | 288 contrast pairs checked; 0 failures |
| `celery -A config inspect ping --timeout=5` | One worker online; pong; worker stopped afterward |

S0 remains open for a clean Linux bootstrap and hosted CI run. These are validation gaps, not evidence that the local browser/API flow failed.

## S1 package 1: private manual exam and catalog boundary (in progress)

Requirements: FR-L1/L3/L4, US-05 prerequisite, ADR-001/007/017/018, PRD §§8.2, 9.5, 11.2. Input contract: versioned `ExamDraft` with explicit provenance; only `catalog.services.create_exam` writes finalized exams. A valid manual exam creates Section/Question/Choice atomically as PRIVATE, and the owner can read it. An unrelated Student and visitor receive 404 for detail/preview and cannot find it via list, facets, or search. An invalid draft, missing subject, or duplicate order yields 400 with no partial exam. Publication is a separate service path. Tests: DTO validation/round-trip, DB atomicity and counts, API query/object privacy, and manual UI to seeded practice path when package 2 is ready. Run focused checks then broad gates before marking the package complete.

Observed: 4 catalog DB/API tests pass; one real browser test creates a manual MCQ exam and verifies PRIVATE isolation for visitor and another Student. The contract round-trip is checked. Full S1 exit remains open until practice and result UI pass.

## S1 package 2: grading and session lifecycle (local implementation validated)

Requirements: FR-P1/P2/P3/P4/P5/P6/P7, US-05, ADR-010/021, PRD §§8.4, 10.1–10.4, 11.4. A logged-in user starts TIMED or PRACTICE against a visible exam. The server fixes order and deadline, accepts idempotent answer saves, and grades all six kinds with Decimal. TIMED reads and saves expose no answer key or explanation before submit/expiry; submit is idempotent and stores immutable snapshot. PRACTICE reveals only the answered/skipped question and locks it. Invalid answer shape, unauthorized exam/session, expired save, and repeated submit have explicit tests. Finish with real UI journey from private manual exam to result.

Observed: `backend/tests/test_grading.py` covers all six kinds in 18 cases. `backend/tests/test_practice.py` covers timed answer secrecy, unauthorized session reads/writes, expiry, idempotent submit, immediate practice feedback, wrong-bank update, and deterministic selection. `pytest backend/tests -q`: 30 passed. `frontend/e2e/practice.spec.ts`: manual exam → timed auto-save → reload → submit/result → practice wrong answer/lock passed against real API/PostgreSQL. `npm run check` (2 component tests), `npm run build`, Ruff, mypy, import-linter (5/5 contracts), and OpenAPI schema validation passed. Full 4-browser-test suite passed before the last auto-save change; focused browser test passed after it. Full suite must be rerun before S1 closes.

## S1 package 3: catalog and personal practice completion (local implementation validated)

Requirements: FR-P1/P2/P3/P8/P9/P11, FR-L3/L4, PRD §§5.4, 8.5, 10.4b, 12.2. Add all AND catalog filters and real-data facets with pagination in UI; detail counts by section/chapter and the current user's wrong questions; configurable chapter/wrong-bank/shuffle session start; server-scoped history/statistics; answer flagging in UI. Query-bound tests cover list/detail to detect N+1 regression. Unauthorized/private data must remain absent from every read. Run focused DB/API tests, UI E2E, then broad local gates before marking S1 complete.

Observed: filters, facets, pagination, section/chapter counts, wrong count, configurable PRACTICE launch, history/stats, and timed question flagging are wired through UI/API/PostgreSQL. Accent-folded search and list/detail query bounds have DB tests. A synthetic, idempotent `seed_thpt_demo` command supplies the three PRD parts. `pytest backend/tests -q`: 33 passed; `npm run e2e`: 5 passed, including seed → all three parts → 10/10 result; `npm run check`: 2 passed; `npm run build`, Ruff, mypy, import-linter 5/5 and `spectacular --validate --fail-on-warn` passed. Hosted CI and clean Linux bootstrap remain unverified.

## S1b package 1: exam ownership and moderated publication (specified)

Requirements: FR-L1/L2/L3/L4, ADR-018, PRD §§5.5, 8.2, 11.2. The owner can soft-delete a private/public exam or make a public exam private immediately; other users lose list/detail/preview/practice access. Private-to-public creates one pending request; only Reviewer/Admin can approve or reject with reason, and only an approved request makes PUBLIC. Admin can hide content. All transitions lock the exam row and reject unauthorized/stale requests. Tests cover owner/other/reviewer/admin/visitor and every read surface. UI exposes real controls and a review queue. Run focused then broad gates before proceeding to TXT.

Observed: owner visibility request, private withdrawal, soft-delete, reviewer queue/detail, approve/reject, and admin hide are implemented with row locks and server role checks. Source is mandatory and self-review is forbidden. `backend/tests/test_publication.py`: 3 passed in broad backend run. `frontend/e2e/publication.spec.ts`: owner → Reviewer → public visitor → private visitor journey passed in the full serial suite (7/7). Reviewer detail only exposes a pending private request.

## S1b package 2: structured TXT import (local implementation validated)

Requirements: FR-I1/I11/I12, ADR-007/020, PRD §§9.0, 9.0.1, 9.2, 9.5, 11.3. A pure finite-state `parse_txt(text)` accepts UTF-8/BOM/NFC v1 plus v2 extensions, returns a versioned `ExamDraft` and line-numbered issues, never silently drops malformed questions, enforces size/line limits, and does not touch DB. A TXT ImportJob records upload/hash/report/draft, reaches NEEDS_REVIEW synchronously, and confirms once through `catalog.services.create_exam` to PRIVATE. Owner-only job read/confirm, duplicate upload handling, invalid draft/no-partial-write and repeat-confirm behavior have DB/API tests. UI shows report and draft before one-action confirm. Use synthetic fixtures; inspect legacy 300-question source read-only and do not redistribute it without usage-rights decision.

Observed: pure parser handles v1/v2, line errors, duplicate warnings, HTML rejection, size/line bounds, and preserves valid neighbors. `scripts/check_quiz_rush_parser.py` compared the read-only legacy `data.js` in memory: 300 source and parsed questions, 4 chapters, text/choices/answers exact, 0 issues/skipped. No legacy content is copied into TestFlow. `ImportJob`/`Draft`/`ReviewEdit` persist private upload, SHA-256 dedup, state transitions, versioned draft and edits. Confirm creates one PRIVATE exam through catalog; API enforces owner scope. UI supports upload, report, metadata form for v1, advanced draft JSON correction and confirmation. TXT daily quota defaults to 20 jobs per uploader and has duplicate precedence and file cleanup tests. Full backend: 51 passed. Full Chrome suite: 9 passed, including TXT → chapter → wrong bank → correct removal, v1 metadata completion, and Admin operations summary. Ruff, mypy (64 files), import-linter (9 kept), OpenAPI, TypeScript, Vitest (2) and Vite build passed. Limits: no OCR pipeline yet; review of question errors still uses JSON editing. Source rights prevent the requested seed migration. Hosted CI remains unverified.

## S2 package 1: offline evaluation contract (synthetic smoke only)

Requirements: PRD §13.1–13.3, execution contract §6. The runner must validate real gold/predicted `ExamDraft`, score matched questions and fields, report CER/formula and measured edit/latency/cost values, split dev versus held-out, and fail on absent data. No fake OCR result may count as a model decision. `eval/run.py` and `eval/README.md` define the private input layout and CLI. `backend/tests/test_eval.py` uses one explicitly synthetic case and checks exact/wrong answer metrics, missing-data failure, and synthetic labeling. E1–E5 remain blocked on real 30-exam gold data and actual extractor outputs; no extractor has been selected. The runner has not produced real evaluation evidence.

## S3/S5 independent local foundation (partial)

Requirements: FR-I1/I2/I9, NFR-5, PRD §9.2 and §18; execution contract §9. The TXT path now enforces a per-uploader local-day upload quota with row locking, preserves SHA-256 duplicate precedence, cleans an original file on failed transaction, and records assembly timing. The ImportJob transition matrix is exercised across all eight states. These are reusable controls, not a document/OCR pipeline.

`GET /healthz` probes PostgreSQL and Redis. Request middleware gives each response a validated or generated `X-Request-ID`; JSON stdout request/import logs include correlation and timing without request bodies. An Admin-only operations summary and browser page show import state counts, oldest review age, pending publication count, and build SHA. [Local operations runbook](../runbooks/local-operations.md) records checks and limits. Tests cover probe failure, request ID sanitization, Admin authorization/counts, and a real Chrome Admin journey. No production log sink, measured alert baseline, backup monitor or deployment is present.

Latest broad local gates: `pytest -c backend/pytest.ini backend/tests -q` 51 passed on PostgreSQL; `npm run e2e` 9 passed on Chrome; Ruff passed on backend/contracts/scripts/eval; mypy passed 64 source files; import-linter kept 9/9 contracts; `manage.py check`, `makemigrations --check --dry-run`, `spectacular --validate --fail-on-warn`, `npm run check` (2 Vitest tests), and `npm run build` passed. Docker Compose PostgreSQL and Redis were healthy. CI workflow has these expanded static gates but has not run on a remote host.

## Open decisions

- Use **TestFlow** everywhere in new product surfaces and package names (owner decision).
- Historical `educommons-*` filenames are not present in this checkout. Canonical adapted files are `docs/prd.md` and `docs/agent-master-prompt.md`; their complete content is present. Do not claim independent original copies are preserved.
- S6 is added to R1 operations scope by ADR-023. No public production release is authorized merely by this plan.
