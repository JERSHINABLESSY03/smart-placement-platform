# Security Review

**Review date:** 2026-10-08
**Scope:** Logout method and CSRF protection, profile file upload and delivery, and production security configuration. No secret values were inspected or included.

## Findings

| # | Severity | Finding | Status |
|---|---|---|---|
| 1 | 🟡 MEDIUM | Resumes could be served through an unauthenticated public media route when media serving was enabled. | Fixed: removed public media-directory serving; profile files are delivered through an authenticated owner-checked route. |
| 2 | 🟡 MEDIUM | Resume uploads had no file-type or size restrictions, allowing dangerous active content to be uploaded and served. | Fixed: resumes are limited to PDF, validated by extension and PDF header, limited to 5 MiB, stored under random filenames, and delivered as downloads with `nosniff`. Profile pictures are limited to JPG, PNG, or WebP and 2 MiB. |
| 3 | ⚪ LOW | Logout was triggered by GET and could be forced through a cross-site link. | Fixed: logout requires POST and the navigation form includes Django CSRF protection. |

## Production configuration review

- Production settings reject a missing/placeholder secret key, wildcard or missing allowed hosts, `DEBUG=True`, and missing/placeholder database credentials. Secrets and database connection values come from environment variables.
- Production defaults enable HTTPS redirects, secure session and CSRF cookies, one-hour HSTS, content-type sniffing protection, frame denial, and a same-origin referrer policy. CSRF trusted origins are configured through the environment.
- Local SQLite development settings were not changed. Docker Compose disables HTTPS redirects and secure cookies for local HTTP testing; those overrides must not be exposed as production settings.
- `.env` values were not inspected or recorded. The project ignore configuration excludes `.env` from Git and Docker build contexts.

## Verification

- Django system check: passed.
- Production-settings system check with temporary non-production validation values: passed.
- Complete Django test suite: 50 tests passed.
- Migration `core.0012_alter_studentprofile_profile_picture_and_more`: applied.
- `makemigrations --check --dry-run`: no changes detected.

## Remaining cautions

- File extension, size, and signature checks do not replace malware scanning. Add scanning before accepting resumes from untrusted users at scale.
- The validation migration does not inspect previously stored uploads; review legacy media files before restoring or importing them into this deployment.
- Enforce request-body and upload-rate limits at the reverse proxy/load balancer to reduce resource exhaustion from oversized requests before Django validates them.
- Production object storage must remain private, and the deployed HTTPS, host, CSRF-origin, and cookie configuration still needs environment-specific deployment verification.
