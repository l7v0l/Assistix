import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _ascii_cacert():
    # curl_cffi (used by yt-dlp to impersonate a browser) cannot open a CA file
    # whose path has non-ASCII characters, so copy it to an ASCII temp path.
    import shutil
    import tempfile

    import certifi

    src = certifi.where()
    if src.isascii():
        return
    dst = Path(tempfile.gettempdir()) / "assistix_cacert.pem"
    if not dst.exists():
        shutil.copyfile(src, dst)
    os.environ["SSL_CERT_FILE"] = str(dst)


_ascii_cacert()


def _required(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


SECRET_KEY = _required("DJANGO_SECRET_KEY")
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost").split(",") if h.strip()]

BOT_TOKEN = _required("BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "bot",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# No DB needed: bot is stateless.
DATABASES = {}

USE_TZ = True
TIME_ZONE = "UTC"
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"bot": {"handlers": ["console"], "level": "INFO"}},
}
