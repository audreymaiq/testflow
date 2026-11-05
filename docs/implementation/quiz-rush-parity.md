# Quiz Rush retained-behavior audit

Date: 2026-11-06. Scope: PRD §23.1 items 1–28 and §23.4. `PASS LOCAL` means the behavior is implemented and has local code/test evidence. `PARTIAL` and `OPEN` prevent the S1b exit gate from closing. This is an implementation audit, not a production acceptance claim.

| PRD item | State | Evidence and remaining gap |
| --- | --- | --- |
| 1 Home hero and snap to deck grid | PARTIAL | `frontend/src/App.tsx` has a short hero; full-height scroll/snap and a home deck grid are absent. |
| 2 Deck grid with icon, color and metadata | OPEN | `frontend/src/catalog.tsx` uses a table on `/library`; no home deck grid. Reconcile this retained behavior with PRD §12.4b's required dense library table. |
| 3 System sample badge | PASS LOCAL | `is_system_sample` appears as “Bộ mẫu” in catalog/detail; `test_quiz_rush_seed.py` covers the seeded deck. |
| 4 Title/subtitle search | PASS LOCAL | Accent-insensitive `search_text` and catalog query tests; library search calls the real API. |
| 5 School/major filter chips plus level/grade/subject | PARTIAL | AND filtering and data-driven facets exist, but the UI uses dropdowns rather than the retained chip carousel. |
| 6 TXT parser and format guide | PASS LOCAL | v1/v2 parser and issue reports pass; the upload page has a text-only guide modal with a v1 example, v2 variants, Escape dismissal and 360px Chrome check before real import. |
| 7 Private/public choice | PASS LOCAL | Private-first save and separate moderated publication pass API/browser tests. |
| 8 Owner visibility, delete and confirmation | PARTIAL | Owner controls and server rules pass; delete uses `window.confirm` instead of the shared modal. |
| 9 Two-step email/password login | PARTIAL | Registration/login are real; two-step legacy UX and password reset are absent. |
| 10 Google login | OUT OF R1 | Explicit non-goal in PRD §1.3. |
| 11 Fake Apple login | PASS LOCAL | No Apple control in TestFlow. |
| 12 Guest intent after authentication | PASS LOCAL | `publication.spec.ts` covers PUBLIC exam → practice/timed intent → registration/login → session, and import intent → login → TXT form. |
| 13 Chapter selection and empty-selection guard | PARTIAL | Chapter controls and counts exist; an empty selection currently means all chapters, so the legacy empty-selection guard is absent. |
| 14 Shuffle questions | PASS LOCAL | Server stores deterministic question order; practice API tests cover stable selection. |
| 15 Urgent wrong-bank practice | PASS LOCAL | Detail control and browser/API wrong-bank journey pass. |
| 16 Practice progress and staggered choices | PARTIAL | Question index/navigation exist; stagger is intentionally prohibited by PRD §12.4b and the motion discrepancy in `prd-audit.md`. Review remaining progress presentation. |
| 17 Immediate feedback and locked answer | PASS LOCAL | PRACTICE API/browser tests cover feedback and locking. |
| 18 Skip with answer reveal and wrong bank | PASS LOCAL | `practice.services.skip_question` and tests cover it. |
| 19 Previous question read-only | PASS LOCAL | UI previous navigation and locked answer state are present. |
| 20 Confirm exit and resume unfinished practice | OPEN | Server persists the session, but leaving via top navigation has no confirmation. |
| 21 Result percentage, counts, retry and home | PARTIAL | Result percentage/counts/details exist; explicit retry and home actions are absent. |
| 22 Clear answered/correct progress labels | PARTIAL | Question index and answer navigation exist; live correct/answered totals are not shown together. |
| 23 Four themes, persistence and no flash | PASS LOCAL | Theme E2E and 288 contrast checks; tokens are generated from `design/palette.py`. |
| 24 Toast progress, hover pause and close | PARTIAL | Shared text-only Toast exists; timed progress, pause and dismiss are absent. |
| 25 Shared modal alert/confirm | PARTIAL | Shared modal exists and logout uses it; other destructive actions still call `window.confirm`. |
| 26 Firestore sync replaced by PostgreSQL/API | PASS LOCAL | No Firebase runtime; server state goes through API/PostgreSQL. |
| 27 Built-in 300-question deck | PASS LOCAL | Authorized fixture parses 300/300 in four chapters; seed/publication/idempotency DB tests pass. Operator-owned environment seeding remains open. |
| 28 Licensed replacement fonts | PASS LOCAL | IBM Plex Sans/Mono and Literata are self-hosted via `@fontsource`; old font folder is not a runtime dependency. |

Next coherent packages: (1) resolve home grid versus library table without changing the library's required dense layout; (2) complete the TXT format guide and practice exit/resume controls; (3) repeat the browser parity walkthrough and update each row with direct evidence. The S1b gate stays open until all retained items have an accepted implementation or a documented PRD/ADR resolution.
