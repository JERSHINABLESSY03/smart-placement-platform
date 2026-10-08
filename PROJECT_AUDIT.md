# Smart Placement Preparation Platform — Project Audit

**Audit date:** 2026-10-08
**Scope:** Read-only inspection of the existing project. No application code was changed for this audit.

> The root `.env` file was confirmed to exist, but its contents were deliberately not inspected. No credential values are included in this report.

## Subsequent verified updates

- The pending `core.0011_ai_messages` migration was applied and verified after this audit.
- Dashboard, dashboard API, and analytics now consume the user-scoped canonical calculations in `core/services/performance_metrics.py`. The implementation adds consistency/privacy coverage; the full suite now has 40 passing tests and `manage.py check` passes.
- Findings below describe the project as inspected on the audit date; the metric-consistency finding and pending-migration finding have since been addressed.

## 1. Project inventory

### Folder structure

- `core/` — the single custom Django application: models, forms, views, admin, URLs, tests, migrations, management commands, and services.
- `placement_platform/` — Django project configuration, WSGI/ASGI entry points, root URLs, and production settings.
- `templates/core/` — application templates and reusable dashboard partials.
- `static/css/` and `static/js/` — shared styling and browser-side JavaScript.
- `docker/` — container entrypoint script.
- `.venv/` — local Python virtual environment.
- Root-level configuration and docs — `manage.py`, requirements, Docker files, environment examples, README, and deployment documentation.
- `db.sqlite3` — local development database.

### Django apps and configuration

There is one custom Django app, `core`. Django’s built-in admin, authentication, content types, sessions, and static files apps are installed, along with Django REST Framework.

The default `placement_platform.settings` uses SQLite. The separate `placement_platform.production_settings` selects PostgreSQL from environment variables, configures WhiteNoise static storage, security options, and optional S3-compatible media storage.

### Existing application data models

- **Authentication/profile:** Django’s default `User` and one-to-one `StudentProfile`.
- **Legacy practice:** `Question`, `QuestionAttempt`, and `TopicProgress`.
- **Database-backed aptitude:** `AptitudeCategory` → `AptitudeTopic` → `AptitudeQuestion` → `AptitudeQuestionOption`, plus `AptitudeQuestionAttempt`.
- **Coding practice:** `CodingTopic` → `CodingProblem`, with `CodingAttempt` and `CodingSubmission` associated with users and problems.
- **Legacy mock tests:** `MockTest` and `MockTestAttempt`.
- **Timed assessment engine:** `Test` → `TestQuestion` → aptitude question; each user’s `TestAttempt` contains `TestAnswer` rows.
- **Other activity:** `StudentActivity`.
- **AI tutor:** user-owned `AIConversation` with associated role-labeled `AIMessage` rows.

### Existing views, routes, and APIs

`core/views.py` contains views for authentication, profiles, dashboard, aptitude practice, coding practice, mock tests, analytics, AI tutor, and health checks. `core/urls.py` defines these application routes and API routes.

Existing API-style endpoints include:

- Authenticated dashboard and performance-analytics JSON endpoints.
- Authenticated AI conversation listing/creation, message reading/sending, and conversation deletion.
- Timed-assessment answer saving and submission endpoints.
- A database readiness endpoint at `/health/`.

### Templates and static files

Templates are located under `templates/core/`, including authentication/profile pages, dashboard, aptitude, coding, timed assessments, analytics, and AI tutor UI. The dashboard has reusable partials for empty states, progress cards, navigation, and stat cards.

Static assets include the shared `styles.css`, general `app.js`, and AI chat JavaScript.

### Services, admin, tests, and dependencies

Services currently cover dashboard metrics, analytics, coding submission recording, timed-test logic, and Gemini integration. Django admin support exists for question banks, coding problems/submissions, assessments/attempts, AI conversations, and messages.

`requirements.txt` includes Django, Django REST Framework, dotenv, Pillow, Gunicorn, WhiteNoise, psycopg, and django-storages/S3 support.

The test suite covers aptitude flows, coding storage without execution, timed-test flows and access control, analytics calculations/privacy, AI conversation ownership/errors, and health checks. The existing suite ran with **36 passing tests**. Django’s system check reported no issues.

## A. What has already been implemented

- Student registration, email-based login, logout, profile creation/editing, and protected student pages using Django’s default user model plus `StudentProfile`.
- A SaaS-style dashboard and analytics service.
- Database-driven aptitude categories, topics, questions, answer options, attempts, scoring, and admin authoring.
- Coding problem browsing and submission history. Code execution is intentionally disabled.
- Timed tests with answer autosave, navigation, marking for review, deadline handling, grading, and result breakdowns.
- Private performance analytics and an authenticated JSON endpoint.
- Gemini-backed AI tutor architecture with stored conversations/messages and a browser chat interface.
- Docker/Gunicorn/PostgreSQL configuration, production settings, health check, static-file handling, optional object storage, and Render deployment documentation.

## B. What is working

- The current core suite reports 36 tests passing.
- Django’s system check reports no issues.
- The local default settings still use SQLite, so the existing local development workflow has not been replaced by PostgreSQL.
- The code-submission flow stores submissions but does not run arbitrary code.
- Student-specific queries and access tests exist for analytics, timed-test attempts, coding submissions, and AI conversations.

Production configuration and deployment documentation exist, but they are not evidence of a successful Docker build, PostgreSQL deployment, or cloud deployment.

## C. What is incomplete or needs verification

- The local SQLite database has migrations through `core.0010`; `core.0011_ai_messages` is pending. Apply and verify it before using the AI feature against this database. The container entrypoint is configured to apply migrations at startup.
- Live Gemini operation has not been verified. Tests mock provider calls; the `.env` contents were not read.
- Docker Compose was not built or run in the audit environment because Docker CLI was unavailable.
- PostgreSQL-backed migrations, concurrency/locking behavior, S3-compatible uploads, and cloud deployment have not been exercised against live services.
- Email delivery uses Django’s console backend rather than a production email service.
- Coding execution is intentionally not implemented.

## D. Duplicate or redundant code/data structures

There are overlapping legacy and newer model families:

- `Question` / `QuestionAttempt` overlap with `AptitudeQuestion` / `AptitudeQuestionAttempt`.
- `MockTest` / `MockTestAttempt` overlap with `Test` / `TestAttempt` / `TestAnswer`.
- `TopicProgress` overlaps with metrics derived from activity records.
- `CodingAttempt` overlaps with `CodingSubmission` for tracking coding activity. The current submission service creates a not-passed attempt for a submission.
- `CodingProblem` retains legacy `category` and `description` fields alongside newer topic and problem fields.

Some overlap may preserve prior behavior or data. Do not remove these models without first checking stored data, consumers, and migration requirements.

## E. Architectural problems

- `core/views.py` contains request logic for many unrelated modules. There are service modules, but responsibilities are not consistently separated.
- Dashboard, dashboard API, and analytics do not use identical activity sources. Dashboard/API metrics primarily use legacy question and coding attempt records, while analytics also includes newer aptitude attempts, completed timed tests, and accepted submissions. Their totals and scores can therefore disagree.
- Dashboard readiness, analytics preparation score, and some recommendations use different data sources and formulas.
- Some metrics iterate through records or topics and issue repeated queries. Analytics loads a student’s activity into Python, which may become costly at higher volume.
- The single `core` app and large views module are increasingly broad. This does not require an immediate rewrite, but future changes should preserve current URLs and behavior.

## F. Security problems and cautions

- Default development settings use `DEBUG=True`, wildcard allowed hosts, and a fallback development secret. Production settings reject debug mode, wildcard hosts, short/placeholder secrets, and placeholder database passwords; production deployments must select those settings correctly.
- Logout is linked through a GET request in the shared navigation. A state-changing logout should use a CSRF-protected POST.
- Profile/resume uploads do not show explicit type and size restrictions. Production uploads should be validated and stored privately in durable object storage.
- Compose enables local media serving for local containers. That is not suitable for public production; production should keep it disabled and use private durable object storage.
- Login and registration have no visible application-level throttling. AI requests have per-user rate limiting, but a database-count limit can be vulnerable to concurrent request races and is not a replacement for infrastructure-level controls.
- Prompts and bounded conversation context are sent to Gemini. Users should be informed of third-party processing and retention expectations.
- Bootstrap and Chart.js are loaded from CDNs without visible Subresource Integrity attributes or a Content Security Policy configuration.
- `.env` is ignored by the project’s current Git ignore rules and excluded from the Docker build context. The project root has no `.git` directory, so Git remotes, status, commit history, and possible prior credential exposure could not be verified.

## G. Database problems and risks

- **Immediate:** apply `core.0011_ai_messages` to the current local database before using the AI conversation/message feature.
- Legacy and newer practice/test model families can diverge. The seed-data command currently seeds the legacy `Question` table and coding problems, not the newer aptitude question bank.
- Exactly four answer options and exactly one correct option are validated in admin and test-start service logic rather than fully enforced by database constraints. Direct ORM or import paths could create malformed data.
- PostgreSQL is the production target, but SQLite test results do not verify PostgreSQL migration, transaction, or locking behavior.
- Typical cloud container filesystems are ephemeral. Persistent user uploads require object storage; database backups alone do not contain uploaded media.

## H. Code-quality and test-coverage problems

- The tests cover several newer modules, but the reviewed suite does not provide comparable coverage for registration/login/profile flows or dashboard metric consistency.
- Existing tests do not establish live Gemini, Docker, PostgreSQL, S3, or cloud behavior.
- Legacy and new model paths remain active. Their compatibility and retirement plan should be explicit before schema cleanup.
- Large shared view modules and repeated query loops increase the cost of testing, reasoning, and performance tuning.

## I. What should be improved before continuing

1. Apply and verify the pending AI migration against the existing local SQLite database.
2. Align dashboard, dashboard API, and analytics data sources and formulas, or clearly document legacy metrics as intentionally separate.
3. Plan the transition from legacy question/mock models only after inventorying existing records and consumers; retain backward compatibility during any migration.
4. Add tests for authentication/profile flows and dashboard/API metric consistency.
5. Change logout to POST; validate upload types/sizes; use private durable production media storage; verify exact production hostnames, CSRF origins, HTTPS, and secure cookies.
6. Verify Docker Compose and PostgreSQL in an environment that has Docker and a test PostgreSQL service. Separately test object storage and cloud deployment.
7. Configure production email delivery and document AI third-party processing/retention before onboarding real students.

## J. Recommended next step

Apply and verify `core.0011_ai_messages`, then reconcile dashboard and analytics metrics. This addresses the immediate local database schema gap and a visible cross-module consistency problem before adding further features.

## Existing Git/GitHub setup

No `.git` directory was present at the project root during inspection. Therefore, the current branch, configured remotes, repository status, GitHub connection, and prior commit history could not be determined. The ignored `.env` file’s presence does not establish whether credentials were ever committed in another repository or earlier history.

## Verification snapshot

- Core test suite: **36 passed**.
- Django system check: **no issues reported**.
- Local database migration plan: `core.0011_ai_messages` pending at the time inspected.
- Docker/cloud deployment: **not verified**; Docker CLI was unavailable in the inspection environment.
- File changes during the audit: **none**.
