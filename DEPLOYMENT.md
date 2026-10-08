# Production deployment

This guide deploys the platform as a Docker web service on Render, using a managed PostgreSQL database and a private S3-compatible bucket for uploaded media. The Docker Compose setup is also suitable for local container testing.

## Local development (SQLite)

The normal Windows development workflow remains unchanged. The default settings module is still `placement_platform.settings`, which uses the local `db.sqlite3` file:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Do not set `DJANGO_SETTINGS_MODULE=placement_platform.production_settings` for this workflow.

## Run the production container stack locally

Docker Compose requires Docker Desktop. Create a local untracked environment file and generate a secret key:

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(50))"
```

Put the generated value in `.env` as `DJANGO_SECRET_KEY`, and replace `POSTGRES_PASSWORD` with a strong, unique local password. `.env` is excluded by `.gitignore` and `.dockerignore`. Do not commit it or use the example values in a real deployment.

Start the app and PostgreSQL:

```powershell
docker compose up --build
```

The entrypoint waits for PostgreSQL's health check, applies migrations, collects static files, then starts Gunicorn. Open `http://localhost:8000/`. Compose keeps PostgreSQL data in `postgres_data` and local container uploads in `app_media`. Uploaded profile files are served only through authenticated, owner-checked application routes; the app does not expose a public media directory. Compose keeps HTTPS redirect disabled for local HTTP testing; set it to `True` for an HTTPS deployment. To stop containers without deleting data, run `docker compose down`. Do not run `docker compose down -v` unless intentionally deleting all Compose database, static, and upload data.

## Deploy on Render

1. Push the application source to a private or public Git repository, ensuring `.env` and local databases are not committed.
2. Create a Render **PostgreSQL** database. Use its **internal** hostname, database name, username, password, and port in the web service environment.
3. Create a Render **Web Service** from the repository and select **Docker**. The supplied Dockerfile and entrypoint build and start the service; no source build command is needed.
4. In the web service settings, add:

   | Variable | Value |
   |---|---|
   | `DJANGO_SETTINGS_MODULE` | `placement_platform.production_settings` |
   | `DJANGO_SECRET_KEY` | Newly generated random secret, at least 50 characters |
   | `DEBUG` | `False` |
   | `DJANGO_ALLOWED_HOSTS` | Your exact Render hostname, e.g. `your-service.onrender.com` |
   | `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://your-service.onrender.com` |
   | `DB_NAME` | Database name from Render |
   | `DB_USER` | Database user from Render |
   | `DB_PASSWORD` | Database password from Render |
   | `DB_HOST` | Internal database hostname from Render |
   | `DB_PORT` | `5432` |
   | `SECURE_SSL_REDIRECT` | `True` |
   | `SESSION_COOKIE_SECURE` | `True` |
   | `CSRF_COOKIE_SECURE` | `True` |
   | `SECURE_HSTS_SECONDS` | Defaults to `3600` (one hour); increase only after validating the HTTPS deployment |
   | `GEMINI_API_KEY` | Optional server-side Gemini key; omit or leave unset if the tutor is not configured |

   Add any other server-only integrations, such as `GEMINI_MODEL`, through the Render environment settings, never source code.

5. Set the Render health check path to `/health/`. It returns `200` only after the application can query the database.
6. Deploy. The container entrypoint runs `migrate` and `collectstatic` before Gunicorn starts. Create an administrator after deployment using a one-off shell for the service:

   ```bash
   python manage.py createsuperuser
   ```

7. Verify the home page, login, admin, health endpoint, static assets, database-backed activity, and file uploads.

### Uploaded media storage

Production uploaded files use S3-compatible storage when `AWS_STORAGE_BUCKET_NAME` is set. Create a private bucket and a dedicated least-privilege service credential with only the needed bucket/object access, then set `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, `AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY` in Render's private environment configuration. For S3-compatible providers such as Cloudflare R2, also set `AWS_S3_ENDPOINT_URL`. Profile files are retrieved through authenticated, owner-checked application routes rather than exposing storage URLs. Keep the bucket private and do not configure public object access.

Without an object-storage bucket configured, production uses `MEDIA_ROOT` on the container filesystem. That filesystem is ephemeral on typical cloud web services, so uploads will not survive replacement/deployments. Configure object storage before relying on profile images or resumes in production.

Static files use WhiteNoise's compressed manifest storage and are collected into `STATIC_ROOT` at container startup. Do not upload static assets into the media bucket.

### Operations and security

- Store database credentials, Django secret, Gemini key, and object-storage credentials only in the platform's secret environment settings.
- Set `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` to exact hostnames/origins; do not use wildcard hosts in production.
- Keep `DEBUG=False`. Production settings reject `DEBUG=True`, wildcard hosts, placeholder keys, and short Django secrets.
- Enable secure cookies and HTTPS redirect only when the public service is behind correctly configured HTTPS. The proxy protocol header is configured for TLS-terminating hosting.
- Back up PostgreSQL and object storage independently, and test restores. Database backups do not include uploaded files.
- Review provider logs for migration/startup failures and monitor `/health/`; the endpoint does not expose exception details.
- The startup migration is appropriate for a single service instance. For multi-instance or zero-downtime releases, run migrations once as a release job before scaling web instances.

## Deployment flow

**Local SQLite development → Docker image → Docker Compose PostgreSQL → Production settings, Gunicorn, and collected static files → Render web service + managed PostgreSQL + private object storage**
