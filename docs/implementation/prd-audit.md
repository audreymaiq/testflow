# TestFlow specification and repository audit

Initial audit: 2026-11-04; updated 2026-11-06. Canonical specifications: [`../prd.md`](../prd.md) and [`../agent-master-prompt.md`](../agent-master-prompt.md). The historical `educommons-*` filenames are absent from this checkout; the canonical documents retain the specification content with the owner's TestFlow override.

## Intake evidence

| Item | Observed state | Consequence |
| --- | --- | --- |
| Implementation root | `T:\coding\testflow` contained only two source documents; no application, tests, `.gitignore`, or Git history | Build TestFlow here from the first S0 slice. Git was initialized on `main`; the specification content is present under canonical filenames. |
| Legacy source | `T:\coding\quiz-rush` contains a static HTML/CSS/JS application with Firebase Auth/Firestore, local storage, and `js/data.js` | Treat as behavior and migration input, never as the new runtime. |
| Legacy dataset | Evaluated `RAW.length === 300`; four chapters have 80, 90, 70, and 60 questions | Owner authorized use and distribution; the checked TXT fixture is committed and seeded through private-first moderation. |
| Other prototype | `T:\coding\educommons` contains an independent FastAPI/SQLite/static-JS implementation | Reference only per owner instruction; no TestFlow import, copy, deployment, or development dependency. |
| Toolchains | Python 3.11.0, Node 26.5.0, npm 11.17.0, Docker CLI/Compose installed; `make` and `uv` absent on Windows | Provide native PowerShell operator commands and a Makefile for Linux/CI. Pin CI toolchains. |
| Runtime | Docker Desktop Linux Engine was initially unavailable; it later started. PostgreSQL/Redis became healthy and S0 browser/API tests passed. `nvidia-smi` remains unavailable; GPU inventory query was denied. | S0 has local runtime evidence. S2 GPU evidence is still absent. |
| Gold data / hosting | No gold set, deploy host, domain, or production credentials found in target or Quiz Rush source | OCR benchmark and S6 live deployment require external inputs. Continue independent work. |

## Discrepancies and local resolutions

Each resolution is intentionally narrow. Update the canonical PRD and an ADR if later evidence changes a material decision.

| Ref | Problem | Resolution and affected verification |
| --- | --- | --- |
| Owner instruction; PRD title and §23 | Source document names the product EduCommons and points to `testflow` as the Quiz Rush source. | Canonical copy names **TestFlow** and points to `T:\coding\quiz-rush`. The old filenames are absent; product copy, package names, logging, and docs use TestFlow. |
| §11.1 auth example vs ADR-013 | Login example returns both access and refresh in JSON, exposing the long-lived credential to JavaScript storage in a SPA. | Return access and safe user profile in JSON; set refresh as HttpOnly SameSite cookie scoped to `/api/v1/auth/`. Refresh rotates and blacklists the cookie token; logout revokes it. S0 E2E checks the cookie is HttpOnly. |
| §4.2 vs §1.1, §9.9, ADR-018 | Glossary describes an `Exam` as approved and public, while confirmation creates a private exam. | Define Exam as a confirmed normalized exam; visibility is independent. Test confirmation to PRIVATE and moderation to PUBLIC. |
| §8.2 vs §15.3 | Publication requires a source URL/provenance, but `Exam` and `PublishRequest` omit a source field. | Add nullable `Exam.source` for all exams and require a nonempty source before requesting PUBLIC. Test missing source rejection and source preservation. |
| §8.4 vs §15.2 | `Session.user` is `CASCADE`, yet account deletion promises anonymized sessions and uploads. | Use nullable `SET_NULL` for session ownership and retain immutable aggregate result snapshots under a deletion service. Remove personal answer text where required by the account deletion policy. Test account deletion and residual data. Keep access to orphaned sessions admin-only. |
| §5.4 FR-P3 | Links to nonexistent §10.4b. | Implement §10.3b; retain the reference correction in the next PRD revision. |
| §10.3b, §8.4 | Shuffle seed is mentioned but not modeled explicitly. | Store seed in validated `Session.config`; persist resulting `question_order` and `option_order`. Test reload stability. |
| §11.3 | `/imports/{id}/` may capture `/imports/mine/` if routes are ordered badly. | Register static `mine` before dynamic `id` in the final router; test both routes. |
| §12.3 | `F` is both choice F and flag shortcut. | Use A–F for choices and `Shift+F` for flagging; ignore shortcuts while typing. Test keyboard behavior. |
| §12.3 vs §5.6 FR-T4, §12.4b | Legacy option stagger is retained in one sentence, while motion policy forbids stagger. | Use one restrained state transition for options and disable it for reduced motion. Test reduced motion. |
| §23.1 items 1–2, §23.4 vs §12.4b | Quiz Rush parity retains a full-height hero and card grid, while the new design requires an information-dense catalog table and minimal decoration. | Candidate resolution: a restrained home hero with deck grid and a separate dense `/library` table. Verify at 360px and in a browser before closing S1b. No data migration; update ADR-022 only if the final layout changes its design decision. Current gap is recorded in `quiz-rush-parity.md`. |
| §3, §5, §18 vs execution contract §4 | Some `S` features overlap mandatory stories: history is `FR-P8 (S)` but US-07 and S5 require it; reduced motion is `FR-T4 (S)` but design contract requires it. | Treat history and reduced motion as R1 release requirements. Keep FR-L5 and FR-P9 as R1 late if capacity permits; keep R2/R3 explicitly out of scope. |
| §9.4–9.5 | Illustrative JSON differs from strict invariants; migration path for schema versions is unspecified. | Put versioned Pydantic contracts in `contracts/`, reject unknown versions safely, add explicit migrators only when a second version exists. Contract and round-trip tests are required. |
| §15.1, §16.5 | Private original files and cropped assets must never be publicly served, including by Nginx. | Store private media outside public static roots; serve through authenticated, object-authorized Django views. Test direct URL and guessed UUID attempts. |
| §4.1, §22.1 | THPT 2025 scoring preset is labeled provisional. | Keep scoring configurable; mark the preset unverified until official material is checked. Do not imply policy correctness in user copy. Test scoring mechanics separately from official-rule fidelity. |
| §13, S2 and S6 | Owner plans to provide 30 usable scans and answer keys; they have not arrived. No GPU or real extractor is available. | Build reproducible evaluation tooling and synthetic smoke fixtures; keep real E1–E5 and full OCR readiness open until measured. A fake extractor is restricted to dev/CI. |
| §16.4 vs owner request | Production deployment was optional in PRD R1. | Add S6 as operational scope via ADR-023. No paid service, DNS, production secret, public release, or data deletion without owner authorization. |

## External gates

1. The 30-exam gold set with usable scans, answer keys and permission for evaluation; owner has said it will be provided.
2. Real GPU/model or explicitly authorized hosted provider for E1–E5 and production OCR.
3. Production host, domain/TLS control, backup destination, monitoring notification channel, and release authorization.
None of these prevents implementing independent S0–S5 code and deterministic tests.
