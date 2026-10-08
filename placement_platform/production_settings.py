import os

from .settings import *


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


if (
    not SECRET_KEY
    or SECRET_KEY == "django-insecure-dev-key"
    or len(SECRET_KEY) < 50
    or any(
        placeholder in SECRET_KEY.lower()
        for placeholder in ("replace", "generate", "change-me", "your-")
    )
):
    raise RuntimeError(
        "Set DJANGO_SECRET_KEY to a generated secret of at least 50 characters."
    )

if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise RuntimeError("Set DJANGO_ALLOWED_HOSTS to explicit production hostnames.")

DEBUG = env_bool("DEBUG", False)
if DEBUG:
    raise RuntimeError("Production settings require DEBUG=False.")

database_password = os.environ.get("DB_PASSWORD", "")
if not database_password or any(
    placeholder in database_password.lower()
    for placeholder in ("replace", "change-me", "password", "your-")
):
    raise RuntimeError("DB_PASSWORD must be set to a private database credential.")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": database_password,
        "HOST": os.environ["DB_HOST"],
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
        "OPTIONS": {"connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "5"))},
    }
}

STATIC_ROOT = Path(os.getenv("STATIC_ROOT", BASE_DIR / "staticfiles"))
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "media"))
INSTALLED_APPS = [*INSTALLED_APPS, "storages"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "").strip()
if MEDIA_BUCKET_NAME:
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": MEDIA_BUCKET_NAME,
            "region_name": os.getenv("AWS_S3_REGION_NAME", "us-east-1"),
            "endpoint_url": os.getenv("AWS_S3_ENDPOINT_URL") or None,
            "querystring_auth": True,
            "querystring_expire": int(os.getenv("AWS_QUERYSTRING_EXPIRE", "3600")),
            "file_overwrite": False,
            "default_acl": None,
        },
    }

MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
    "whitenoise.middleware.WhiteNoiseMiddleware",
)

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", True)
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "3600"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
