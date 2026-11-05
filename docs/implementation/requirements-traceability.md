# TestFlow requirements traceability

Updated: 2026-11-06. Planned paths and tests must be replaced with real evidence as each slice closes. The historical filenames are absent from this checkout; `docs/prd.md` is canonical. Latest broad local gates: 59 backend tests, 11 Chrome E2E, Ruff, mypy 68 files, import-linter 9/9, schema, TypeScript/Vitest/build pass. Hosted CI and production are unverified.

| ID | Source/scope | Implementation target | Test target | Verification method | State |
| --- | --- | --- | --- | --- | --- |
| ADR-001 | PRD §20 / R1 | backend/config; backend/apps; backend/.importlinter | backend import-linter | 9 architectural contracts kept locally | VERIFIED LOCAL |
| ADR-002 | PRD §20 / R1 | inference/app | inference/app | design review + CI gate | NOT STARTED |
| ADR-003 | PRD §20 / R1 | backend/config/celery.py; compose.dev.yml | Celery inspect ping | local worker returned pong over Redis | VERIFIED LOCAL |
| ADR-004 | PRD §20 / R1 | backend/apps/imports/assemble | backend/apps/imports/assemble | design review + CI gate | NOT STARTED |
| ADR-005 | PRD §20 / R1 | backend/apps | backend/apps | design review + CI gate | NOT STARTED |
| ADR-006 | PRD §20 / R1 | backend/apps | backend/apps | design review + CI gate | NOT STARTED |
| ADR-007 | PRD §20 / R1 | contracts/testflow_contracts/exam.py; backend/apps/catalog | backend/tests/test_catalog.py | versioned DTO and DB round-trip pass; import adapters pending | IN PROGRESS |
| ADR-008 | PRD §20 / R1 | backend/config/api.py | backend/config/api.py | design review + CI gate | NOT STARTED |
| ADR-009 | PRD §20 / R1 | backend/apps/imports; backend/apps/catalog | backend/apps/imports; backend/apps/catalog | design review + CI gate | NOT STARTED |
| ADR-010 | PRD §20 / R1 | backend/apps/practice/grading.py | backend/tests/test_grading.py | 18 pure Decimal grading cases pass for six kinds | VERIFIED LOCAL |
| ADR-011 | PRD §20 / R1 | frontend/src; frontend/package-lock.json | frontend/src/App.test.tsx; frontend/e2e/auth.spec.ts | TypeScript, 2 unit tests, 1 browser E2E passed | VERIFIED LOCAL |
| ADR-012 | PRD §20 / R1 | backend/config; compose.dev.yml | backend/tests/test_accounts.py | PostgreSQL migrations and 4 API tests passed | VERIFIED LOCAL |
| ADR-013 | PRD §20 / R1 | backend/apps/accounts; frontend/src/auth.tsx | backend/tests/test_accounts.py; frontend/src/App.test.tsx; frontend/e2e/auth.spec.ts | 15m access, 7d rotating refresh, blacklist and HttpOnly cookie; private query cache cleared on identity change | VERIFIED LOCAL |
| ADR-014 | PRD §20 / R1 | backend/config/media.py | backend/config/media.py | design review + CI gate | NOT STARTED |
| ADR-015 | PRD §20 / R1 | backend/apps/practice | backend/tests/test_practice.py | session API and browser lifecycle pass; full production load pending | IN PROGRESS |
| ADR-016 | PRD §20 / R1 | backend/apps/imports/ingest | backend/apps/imports/ingest | design review + CI gate | NOT STARTED |
| ADR-017 | PRD §20 / R1 | backend/apps/catalog/models.py; migrations/0003_seed_subjects.py | backend/tests/test_catalog.py | DB Subject catalog and seeded subject endpoint work locally | VERIFIED LOCAL |
| ADR-018 | PRD §20 / R1 | backend/apps/catalog/services.py; frontend/src/publication.tsx | backend/tests/test_publication.py; frontend/e2e/publication.spec.ts | private-first, reviewer approval, withdrawal, hide, and source requirement pass locally | VERIFIED LOCAL |
| ADR-019 | PRD §20 / R1 | backend/apps/catalog/models.py | backend/apps/catalog/models.py | design review + CI gate | NOT STARTED |
| ADR-020 | PRD §20 / R1 | backend/apps/imports/txt_parser.py; data/seed/quiz-rush-cv.txt | backend/tests/test_txt_parser.py; backend/tests/test_quiz_rush_seed.py | Historical 300/300 source comparison; committed fixture and parser covered locally | VERIFIED LOCAL |
| ADR-021 | PRD §20 / R1 | backend/apps/practice/models.py | backend/tests/test_practice.py | PostgreSQL session/answer/wrong-bank migrations and scoped API tests pass | VERIFIED LOCAL |
| ADR-022 | PRD §20 / R1 | design; frontend/src/shared | design; frontend/src/shared | design review + CI gate | NOT STARTED |
| FR-A1 | PRD §5.1 / R1 | backend/apps/accounts; frontend/src/App.tsx | backend/tests/test_accounts.py; frontend/e2e/auth.spec.ts | DB/API and browser register/login/logout passed | VERIFIED LOCAL |
| FR-A2 | PRD §5.1 / R1 | backend/apps/accounts; frontend/src/auth.tsx | backend/tests/test_accounts.py; frontend/e2e/auth.spec.ts | token rotation/blacklist and browser reload passed | VERIFIED LOCAL |
| FR-A3 | PRD §5.1 / R1-S | backend/apps/accounts; frontend/src/App.tsx | frontend/e2e/auth.spec.ts | browser profile PATCH and reload passed | VERIFIED LOCAL |
| FR-A4 | PRD §5.1 / R1 | backend/apps/accounts/permissions.py; backend/apps/accounts/migrations/0002_roles.py | backend/tests/test_accounts.py | Student denied Reviewer/Admin permissions; roles seeded | VERIFIED LOCAL |
| FR-I1 | PRD §5.2 / R1 | backend/apps/imports; frontend/src/imports.tsx | backend/tests/test_txt_import.py; frontend/e2e/imports.spec.ts | TXT upload, size/type check and 20/day quota pass; document formats remain open | PARTIAL LOCAL |
| FR-I10 | PRD §5.2 / R2 | backend/apps/imports; frontend/src/features/imports | backend/apps/imports; frontend/src/features/imports | parser + DB/API + import E2E | DEFERRED |
| FR-I11 | PRD §5.2 / R1 | backend/apps/imports/txt_parser.py; data/seed/quiz-rush-cv.txt; frontend/src/imports.tsx | backend/tests/test_txt_parser.py; backend/tests/test_quiz_rush_seed.py; frontend/e2e/imports.spec.ts | TXT v1/v2 parsed; historical 300/300 comparison; guide modal and 360px import journey pass locally | VERIFIED LOCAL |
| FR-I12 | PRD §5.2 / R1 | data/seed/quiz-rush-cv.txt; backend/apps/imports/management/commands/seed_quiz_rush.py | backend/tests/test_quiz_rush_seed.py | owner-authorized 300-question, four-chapter fixture; private seed, distinct Reviewer publication, public visitor and idempotency pass | VERIFIED LOCAL |
| FR-I2 | PRD §5.2 / R1 | backend/apps/imports/services.py; backend/apps/imports/models.py | backend/tests/test_txt_import.py | TXT SHA-256 duplicate/rejected precedence tested; document formats open | PARTIAL LOCAL |
| FR-I3 | PRD §5.2 / R1 | backend/apps/imports; frontend/src/features/imports | backend/apps/imports; frontend/src/features/imports | parser + DB/API + import E2E | NOT STARTED |
| FR-I4 | PRD §5.2 / R1 | backend/apps/imports; frontend/src/features/imports | backend/apps/imports; frontend/src/features/imports | parser + DB/API + import E2E | NOT STARTED |
| FR-I5 | PRD §5.2 / R1 | backend/apps/imports; frontend/src/features/imports | backend/apps/imports; frontend/src/features/imports | parser + DB/API + import E2E | NOT STARTED |
| FR-I6 | PRD §5.2 / R1 | backend/apps/imports; frontend/src/features/imports | backend/apps/imports; frontend/src/features/imports | parser + DB/API + import E2E | NOT STARTED |
| FR-I7 | PRD §5.2 / R1 | backend/apps/imports; frontend/src/features/imports | backend/apps/imports; frontend/src/features/imports | parser + DB/API + import E2E | NOT STARTED |
| FR-I8 | PRD §5.2 / R1 | backend/apps/imports; frontend/src/features/imports | backend/apps/imports; frontend/src/features/imports | parser + DB/API + import E2E | NOT STARTED |
| FR-I9 | PRD §5.2 / R1 | backend/apps/imports/views.py; frontend/src/imports.tsx | backend/tests/test_txt_import.py; frontend/e2e/imports.spec.ts | owner can read TXT job/report; other user denied; OCR status flow open | PARTIAL LOCAL |
| FR-L1 | PRD §5.5 / R1 | backend/apps/catalog/models.py; backend/apps/catalog/selectors.py | backend/tests/test_catalog.py; frontend/e2e/catalog.spec.ts | owner and visibility model; PRIVATE browser journey passed | IN PROGRESS |
| FR-L2 | PRD §5.5 / R1 | backend/apps/catalog/services.py; frontend/src/{catalog,publication}.tsx | backend/tests/test_publication.py; frontend/e2e/{catalog,publication}.spec.ts | owner soft-delete and withdrawal with cancel/confirm, reviewer approval, guest denial and full serial E2E pass locally | VERIFIED LOCAL |
| FR-L3 | PRD §5.5 / R1 | backend/apps/catalog/selectors.py; frontend/src/catalog.tsx | backend/tests/test_catalog.py; frontend/e2e/catalog.spec.ts | list/detail/preview/facets private isolation passed; future endpoints pending | IN PROGRESS |
| FR-L4 | PRD §5.5 / R1 | backend/apps/catalog/views.py; frontend/src/{App,catalog}.tsx; backend/apps/practice/services.py | frontend/e2e/publication.spec.ts; backend/tests/test_practice.py | PUBLIC visitor selects timed/practice, registers/logs in and starts once; import intent reaches TXT form; wrong active mode returns 409; 11 browser tests pass | VERIFIED LOCAL |
| FR-L5 | PRD §5.5 / R1-S | backend/apps/catalog; frontend/src/features/library | backend/apps/catalog; frontend/src/features/library | privacy DB/API + E2E | NOT STARTED |
| FR-L6 | PRD §5.5 / R2 | backend/apps/catalog; frontend/src/features/library | backend/apps/catalog; frontend/src/features/library | privacy DB/API + E2E | DEFERRED |
| FR-P1 | PRD §5.4 / R1 | backend/apps/catalog/selectors.py; frontend/src/catalog.tsx | backend/tests/test_catalog.py; frontend/e2e/catalog.spec.ts | AND filters, accent-folded search, facets, pagination; list query count bounded locally | VERIFIED LOCAL |
| FR-P10 | PRD §5.4 / R1 | backend/apps/practice/services.py; frontend/src/practice.tsx | backend/tests/test_practice.py; frontend/e2e/practice.spec.ts | immediate MCQ feedback, answer lock, skip/read-only API and browser test pass | VERIFIED LOCAL |
| FR-P11 | PRD §5.4 / R1 | backend/apps/practice/models.py; services.py; selectors.py | backend/tests/test_practice.py | wrong/skip insertion, correct removal, private scoping pass | VERIFIED LOCAL |
| FR-P2 | PRD §5.4 / R1 | backend/apps/catalog/serializers.py; backend/apps/practice/selectors.py; frontend/src/catalog.tsx | backend/tests/test_catalog.py; backend/tests/test_practice.py | section/chapter counts and personal wrong count pass | VERIFIED LOCAL |
| FR-P3 | PRD §5.4 / R1 | backend/apps/practice/selection.py; frontend/src/catalog.tsx | backend/tests/test_practice.py | server-owned fixed order and config; deterministic selection test passes | VERIFIED LOCAL |
| FR-P4 | PRD §5.4 / R1 | backend/apps/practice/services.py; frontend/src/practice.tsx | frontend/e2e/practice.spec.ts | timed auto-save and reload recovery pass in real browser | VERIFIED LOCAL |
| FR-P5 | PRD §5.4 / R1 | backend/apps/practice/services.py; frontend/src/practice.tsx | backend/tests/test_practice.py | server deadline blocks saves and lazy expiry submits; UI countdown present | VERIFIED LOCAL |
| FR-P6 | PRD §5.4 / R1 | backend/apps/practice/grading.py; services.py | backend/tests/test_grading.py; backend/tests/test_practice.py | six-kind Decimal grading, idempotent submit, snapshot pass | VERIFIED LOCAL |
| FR-P7 | PRD §5.4 / R1 | frontend/src/practice.tsx; backend/apps/practice/services.py | frontend/e2e/practice.spec.ts | real result page shows score/answer after submit | VERIFIED LOCAL |
| FR-P8 | PRD §5.4 / R1 | backend/apps/practice/selectors.py; frontend/src/practice.tsx | backend/tests/test_practice.py; frontend/e2e/practice.spec.ts | scoped paginated history and personal count stats pass | VERIFIED LOCAL |
| FR-P9 | PRD §5.4 / R1-S | backend/apps/practice/services.py; frontend/src/practice.tsx | frontend/e2e/practice.spec.ts | timed question flag persists across reload | VERIFIED LOCAL |
| FR-R1 | PRD §5.3 / R1 | backend/apps/imports; frontend/src/features/review | backend/apps/imports; frontend/src/features/review | review permission + E2E | NOT STARTED |
| FR-R2 | PRD §5.3 / R1 | frontend/src/imports.tsx | frontend/e2e/imports.spec.ts | TXT per-question form edit/save/practice passes; page images and warning-to-question links open | PARTIAL LOCAL |
| FR-R3 | PRD §5.3 / R1 | backend/apps/imports/services.py | backend/tests/test_txt_import.py; frontend/e2e/imports.spec.ts | TXT confirm creates PRIVATE exam atomically and once | PARTIAL LOCAL |
| FR-R4 | PRD §5.3 / R1 | backend/apps/imports/{services,views}.py; frontend/src/imports.tsx | backend/tests/test_txt_import.py; frontend/e2e/imports.spec.ts | TXT discard stores optional reason and owner can reload it; document drafts open | PARTIAL LOCAL |
| FR-R5 | PRD §5.3 / R1 | backend/apps/imports/models.py; services.py | backend/tests/test_txt_import.py | ReviewEdit stores before/after on TXT draft save | PARTIAL LOCAL |
| FR-R6 | PRD §5.3 / R1 | backend/apps/catalog/services.py; frontend/src/publication.tsx | backend/tests/test_publication.py; frontend/e2e/publication.spec.ts | Reviewer approval/rejection and owner status/reason locally verified | VERIFIED LOCAL |
| FR-T1 | PRD §5.6 / R1 | design/palette.py; design/tokens.css; frontend/src/theme.tsx | design/palette.py | 288 contrast pairs passed; four themes and three mode choices built | VERIFIED LOCAL |
| FR-T2 | PRD §5.6 / R1 | frontend/index.html | frontend/e2e/auth.spec.ts | prepaint script and reload persistence verified; visual flash measurement pending | IN PROGRESS |
| FR-T3 | PRD §5.6 / R1 | frontend/src/{shared,App,catalog,practice}.tsx | frontend/e2e/{auth,catalog,practice,imports}.spec.ts | text-only modal Escape/cancel/confirm, owner delete and practice submit Chrome journeys; axe account audit passed | VERIFIED LOCAL |
| FR-T4 | PRD §5.6 / R1 | frontend/src/style.css | browser reduced-motion audit pending | CSS disables motion under user preference | IN PROGRESS |
| NFR-1 | PRD §6 / R1 | backend/apps/practice/grading.py | backend/apps/practice/grading.py | measured gate + targeted test | NOT STARTED |
| NFR-2 | PRD §6 / R1 | backend/apps/imports/tasks.py | backend/apps/imports/tasks.py | measured gate + targeted test | NOT STARTED |
| NFR-3 | PRD §6 / R1 | backend/apps/catalog/selectors.py | backend/apps/catalog/selectors.py | measured gate + targeted test | NOT STARTED |
| NFR-4 | PRD §6 / R1 | eval/run.py; inference/app | eval/run.py; inference/app | measured gate + targeted test | NOT STARTED |
| NFR-5 | PRD §6 / R1 | backend/apps/common/request_logging.py; backend/apps/imports/services.py; backend/config/settings/base.py | backend/tests/test_health.py; backend/tests/test_txt_import.py | JSON request/job correlation and TXT assembly timing tested; OCR stage timings pending | PARTIAL LOCAL |
| NFR-6 | PRD §6 / R1 | backend/apps/imports/extraction | backend/apps/imports/extraction | measured gate + targeted test | NOT STARTED |
| NFR-7 | PRD §6 / R1 | compose.dev.yml; Makefile; .github/workflows/ci.yml | local Compose and CI workflow | Compose healthy; clean Linux bootstrap and hosted CI pending | IN PROGRESS |
| NFR-8 | PRD §6 / R1 | frontend/src/style.css | frontend/e2e/auth.spec.ts | 360px auth/account layout has no horizontal overflow; full R1 pages pending | IN PROGRESS |
| NFR-9 | PRD §6 / R1 | frontend/src/shared.tsx; frontend/src/App.tsx | frontend/e2e/auth.spec.ts | axe 0 violations on register/account; full R1 pages pending | IN PROGRESS |
| US-01 | PRD §2.2 / R1 | backend/apps/imports; frontend/src/features/imports | backend/apps/imports; frontend/src/features/imports | parser + DB/API + import E2E | NOT STARTED |
| US-02 | PRD §2.2 / R1 | backend/apps/imports; frontend/src/features/imports | backend/apps/imports; frontend/src/features/imports | parser + DB/API + import E2E | NOT STARTED |
| US-03 | PRD §2.2 / R1 | backend/apps/imports; frontend/src/features/review | backend/apps/imports; frontend/src/features/review | review permission + E2E | NOT STARTED |
| US-04 | PRD §2.2 / R1 | backend/apps/catalog; frontend/src/features/library | backend/apps/catalog; frontend/src/features/library | privacy DB/API + E2E | NOT STARTED |
| US-05 | PRD §2.2 / R1 | backend/apps/practice; frontend/src/features/practice | backend/apps/practice; frontend/src/features/practice | grading + DB/API + E2E | NOT STARTED |
| US-06 | PRD §2.2 / R1 | backend/apps/practice; frontend/src/features/practice | backend/apps/practice; frontend/src/features/practice | grading + DB/API + E2E | NOT STARTED |
| US-07 | PRD §2.2 / R1 | backend/apps/practice; frontend/src/features/practice | backend/apps/practice; frontend/src/features/practice | grading + DB/API + E2E | NOT STARTED |
| US-08 | PRD §2.2 / R2 | backend/apps/catalog; frontend/src/features/library | backend/apps/catalog; frontend/src/features/library | privacy DB/API + E2E | DEFERRED |
| US-09 | PRD §2.2 / R2 | backend/apps/catalog; frontend/src/features/library | backend/apps/catalog; frontend/src/features/library | privacy DB/API + E2E | DEFERRED |
| US-10 | PRD §2.2 / R1 | backend/apps/imports; frontend/src/imports.tsx | backend/tests/test_txt_import.py; frontend/e2e/imports.spec.ts | owner TXT journey passed; other formats open | PARTIAL LOCAL |
| US-11 | PRD §2.2 / R1 | backend/apps/catalog; frontend/src/features/library | backend/apps/catalog; frontend/src/features/library | privacy DB/API + E2E | NOT STARTED |
| US-12 | PRD §2.2 / R1 | backend/apps/practice; frontend/src/features/practice | backend/apps/practice; frontend/src/features/practice | grading + DB/API + E2E | NOT STARTED |
| US-13 | PRD §2.2 / R1 | backend/apps/practice; frontend/src/features/practice | backend/apps/practice; frontend/src/features/practice | grading + DB/API + E2E | NOT STARTED |
| ADR-023 | Execution contract §8 / S6 | docs/adr/023-production-operations.md | document review | accepted decision | DOCUMENTED |
| ADR-024 | Owner rights decision / S1b | docs/adr/024-quiz-rush-seed.md | backend/tests/test_quiz_rush_seed.py | owner authorized Quiz Rush deck distribution; fixture and moderated seed tested | DOCUMENTED |
| ADR-025 | Owner taxonomy clarification / S1b | docs/adr/025-reviewed-taxonomy-names.md; backend/apps/catalog/{taxonomy,models,services,views}.py; backend/apps/catalog/migrations/0007_self_service_taxonomy.py; backend/apps/accounts/serializers.py; frontend/src/{taxonomy,catalog,imports,App}.tsx | backend/tests/test_catalog.py; frontend/e2e/taxonomy.spec.ts | exact case/space variants resolve; close spelling suggests only; explicit self-service creation/reuse, migration of pending names, unknown metadata and profile school guarded; PostgreSQL backend 58, Chrome E2E 11 pass | VERIFIED LOCAL |
| S0 | PRD §18 / exit gate | docs/implementation/status.md; slice files | slice tests and evidence | execution-plan.md exit gate | IN PROGRESS |
| S1 | PRD §18 / exit gate | backend/apps/catalog; backend/apps/practice; contracts; frontend/src/{catalog,practice}.tsx | backend/tests/{test_catalog,test_grading,test_practice}.py; frontend/e2e/{catalog,practice}.spec.ts | local backend/browser gates pass; hosted CI and clean Linux bootstrap open | VERIFIED LOCAL |
| S2 | PRD §§13,18 / exit gate | eval/run.py; eval/README.md; docs/experiments/README.md | backend/tests/test_eval.py | offline runner and synthetic smoke pass; real gold/extractor outputs absent | BLOCKED EXTERNAL |
| S3 | PRD §18 / exit gate | backend/apps/imports/{models,services}.py | backend/tests/test_txt_import.py | state matrix, TXT quota and dedup pass; document processing absent | PARTIAL FOUNDATION |
| S4 | PRD §18 / exit gate | frontend/src/{imports,publication}.tsx; backend/apps/imports/services.py | frontend/e2e/{imports,publication}.spec.ts | TXT structured review and publication moderation pass; document image review open | PARTIAL LOCAL |
| S5 | PRD §18 / exit gate | backend/apps/common/{health,request_logging}.py; backend/apps/ops; frontend/src/ops.tsx | backend/tests/{test_health,test_ops}.py; frontend/e2e/ops.spec.ts | local health/JSON correlation/Admin summary and 9 browser E2E pass; full R1/security/load gates open | PARTIAL LOCAL |
| S6 | Execution contract §§8–10 / exit gate | docs/runbooks/local-operations.md; backend/apps/ops | local health/Admin tests | local operations runbook; no host, backups, TLS, release or deployed smoke | BLOCKED EXTERNAL |

Update paths, named tests, exact command results, and evidence-backed state after each package.
