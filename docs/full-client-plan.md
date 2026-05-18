# Full Client Plan (Phase 1)

## Goal

Turn the current hints-focused app into a full desktop client for question bank operations:
- search and filter tasks;
- open full task card;
- edit core fields and hints;
- manage links between tasks;
- work with task files and LaTeX sessions.

## What We Already Confirmed From HAR

Validated endpoints from your HAR files:
- `POST /api/test/v1/question/admin/list`
- `GET /api/test/v1/question/admin/by-id/{id}`
- `POST /api/test/v1/question/admin/edit/{id}`
- `PUT /api/test/v1/related-questions/admin/edit`
- `POST /api/storage/v1/files`
- `POST /api/test/v1/theme/admin/list`
- `POST /api/test/v1/tags/list`
- `POST /api/test/v1/subject-difficulty/admin/list`
- `POST /api/test/v1/question-source/list`
- `POST /api/stream/v1/lesson/admin/list`
- `POST /api/test/v1/theory/admin/list`

This is enough to build a practical CRUD-style admin client MVP.

## Phase 1 Delivered In Code

- New full-client API module:
  - `shkolkovo/task_client_api.py`
- New full-client UI module:
  - `shkolkovo/full_client_qt.py`
- New app startup mode:
  - `main.py` now launches Full Client by default
  - legacy hints mode is still available with `--legacy-hints`

## Product Direction

### Core UX Principles

- One-screen workflow: list on the left, editable card on the right.
- Low-friction editing: fast fields, ids, tags, themes, hints JSON.
- Safe write path: preserve untouched fields and only patch changed inputs.
- Traceability: status feedback for every load/save operation.

### Phase 2 (Next)

- Add advanced filter builder for `Condition` rules.
- Add dedicated tabs that mirror admin UI:
  - Main
  - Task (LaTeX session)
  - Solution (LaTeX session)
  - Answer
  - Hints
  - Related questions
- Add source/theory/lesson selectors (not only id fields).
- Add file attachments manager using storage endpoints.
- Add draft compare panel (before/after JSON).

### Phase 3

- Batch operations:
  - bulk set tags;
  - bulk set difficulty/theme;
  - bulk private/public switch.
- History and rollback snapshots.
- QA checks before save:
  - required fields;
  - inconsistent flags;
  - missing theme/difficulty.

## Comparable Products and Patterns Worth Borrowing

1. Moodle Question Bank
   - strong category structure, import/export, reusable bank patterns.
   - source: https://docs.moodle.org/405/en/Question_bank

2. Open edX Studio problem authoring flow
   - component-driven authoring and explicit editor modes.
   - source: https://docs.openedx.org/en/latest/educators/navigation/components_activities.html

3. Learnosity Author API / Author Site
   - item bank + editor integration model (good reference for future modularity).
   - source: https://authorguide.learnosity.com/hc/en-us/articles/360000539158-What-is-the-Author-API

4. Internal tool builders (Appsmith / Directus patterns)
   - fast CRUD UX, schema-driven forms, practical admin ergonomics.
   - sources:
     - https://docs.appsmith.com/
     - https://docs.directus.io/user-guide/overview/data-studio-app

## Data Still Needed To Reach Full Parity

- HAR of "Create question" flow from first click to successful save.
- HAR of "Edit answer type" with at least two different answer types.
- HAR of:
  - adding/removing related question;
  - file upload and file remove;
  - adding theory facts and plan items.
- One anonymized real question JSON after `by-id` for each major task type.

