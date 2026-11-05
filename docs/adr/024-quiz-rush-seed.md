# ADR-024: Owner-authorized Quiz Rush seed

Date: 2026-11-05. Status: accepted for the built-in 300-question deck.

The owner confirmed in this session that TestFlow may use and distribute the 300 built-in questions in `T:\coding\quiz-rush`. This decision covers that deck only; it does not establish rights to arbitrary legacy user data or third-party exam scans.

Export the deck to a deterministic UTF-8 TXT fixture, check 300 questions across four chapters with identical text, choices and answer keys, and commit the fixture in TestFlow. The running application does not read or import code from `quiz-rush` or `educommons`.

Seed through `ExamDraft` and `catalog.services.create_exam`. The seed owner must be an existing Admin. An existing, distinct Reviewer may approve a publication request through the normal moderation service. Without a Reviewer, the seed stays PRIVATE. The command is idempotent and refuses a changed or deleted prior seed. Mark this deck with a server-owned `is_system_sample` flag for the “Bộ mẫu” label.

The owner's rights statement is recorded here as an implementation decision. No separate license document was provided in this session.
