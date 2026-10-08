# Smart Placement Preparation Platform

A production-style Django platform for placement preparation.

## Features
- Student authentication and profile management
- Database-driven aptitude practice for quantitative aptitude, logical reasoning, and verbal ability
- Topic-level difficulty, four-option answers, immediate results, explanations, score, accuracy, and time tracking
- Django admin question authoring with exactly four options and one correct answer
- Database-driven coding problem library with topic filters, a code-editor interface, saved submission history, and safe non-executing sample-validation status
- Coding practice and mock test management
- Dashboard analytics and recommendation tracking
- Gemini-powered AI assistant service isolated in `core/services/gemini_service.py`

## Aptitude practice

Run migrations and start the server, then visit `/practice/` after signing in. Categories and starter topics are created by the migration; add or edit questions at `/admin/` under Aptitude questions. Each question requires four options and exactly one correct option. Attempts are tied to the signed-in student and are visible as read-only records in admin.

Run the focused test suite with:

```bash
python manage.py test core.tests
```

Coding problems are managed in Django admin under Coding problems. Student submissions save their code and selected language, but do not execute code or claim that sample tests passed. A future execution service must run outside the Django web process in an isolated, resource-limited environment.

Visit `/coding/` after signing in to browse by topic or difficulty. Add problem topics and problems under `/admin/` → Coding topics / Coding problems. A problem includes statement, input/output format, constraints, sample input/output, explanation, difficulty, tags, and optional starter code. Each student submission is private to its owner and appears in their submission history.

Apply schema updates and run the server with:

```bash
python manage.py migrate
python manage.py runserver
```

Run aptitude and coding regression tests with:

```bash
python manage.py test core.tests
```

## Timed mock assessments

Create a test under `/admin/` → Tests and add rows to its Test questions inline, choosing aptitude questions from any active category or topic. Publish only after adding the desired questions. Students take the assessment at `/mock-tests/`; answer and review state is saved to the server while navigating, and the deadline is enforced on every save and submission request. Results include marks, correct/wrong/skipped counts, accuracy, time, and category/topic breakdowns.

## Performance analytics

Signed-in students can view their private report at `/analytics/`; the matching authenticated JSON endpoint is `/api/analytics/`. Aggregation is implemented in `core/services/analytics_service.py` and filters every activity source by the request user.

- Question accuracy is correct answered practice and completed-assessment questions divided by the number of those answered questions.
- Questions attempted/solved count each recorded answer; unanswered test questions are excluded.
- Coding problems attempted and solved are unique problem IDs across that student's submissions and coding attempts; a problem is solved when an attempt passed or a submission is accepted.
- Mock tests completed counts both legacy completed mock attempts and submitted/expired timed-test attempts. Recent timed-test percentages are score divided by snapshotted total marks; the legacy model has no total-mark field, so its raw score is shown without a percentage.
- Category/topic accuracy is calculated from the same answered question records. Weekly buckets show the previous seven calendar days; assessment question activity is attributed to the test submission date.
- Preparation score is the arithmetic mean of the available aptitude accuracy, coding success rate, and timed-test average percentage; domains with no recorded activity are omitted.

The analytics page renders weekly activity and category accuracy with Chart.js and includes empty states until the student has recorded activity.

## AI placement tutor

The signed-in AI tutor is available at `/ai-assistant/`. Configure the server-side `.env` file with a Gemini key from Google AI Studio:

```dotenv
GEMINI_API_KEY=your-private-key
GEMINI_MODEL=gemini-2.0-flash
```

Never put the key in templates, static assets, browser requests, source control, or client-side configuration. `.env` is ignored by Git; use `.env.example` only as a placeholder reference. The browser calls authenticated, CSRF-protected Django endpoints and never calls Google directly.

The request path is: **Browser → Django view/API → `core/services/gemini_service.py` → Gemini API → Django → Browser**. The tutor supports concept, coding, aptitude, DBMS and SQL explanations, original practice generation, hints, mistake explanations, and study recommendations. Conversations and role-labeled messages are stored in `AIConversation` and `AIMessage`; existing prompt/response records are migrated into message history.

User messages are limited to 6,000 characters, prior context is bounded to 12 messages, and each account is limited to 5 requests per minute. Gemini provider throttling (429), configuration/authentication problems, unavailable provider responses, network errors, malformed responses, and empty answers produce explicit safe errors rather than demo answers. Clear conversation permanently deletes that conversation and its messages.

## Setup

1. Create a virtual environment
2. Install dependencies
3. Run: `python manage.py migrate`
4. Create a superuser: `python manage.py createsuperuser`
5. Load seed data: `python manage.py seed_data`

## Docker

See [DEPLOYMENT.md](./DEPLOYMENT.md) for Docker, PostgreSQL, production settings, media storage, health checks, and Render deployment instructions. Local development continues to use SQLite unless `placement_platform.production_settings` is selected.

Copy `.env.example` to an untracked `.env`, replace the Django secret and PostgreSQL password, then start the PostgreSQL + Gunicorn stack:

```bash
docker compose up --build
```

The container runs migrations and `collectstatic` before starting Gunicorn. Check readiness at `http://localhost:8000/health/`.
