# %%
import ast
import logging  # noqa:F401
import logging.config
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Add the project directory to sys.path so we can import local_settings.
path = Path(__file__).resolve()
for parent in path.parents:
    if (parent / "manage.py").exists():
        project_dir = str(parent)
        root_dir = str(parent.parent)

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
try:
    import data.local_settings as local_settings
except ImportError as e:
    raise e

    class local_settings(object):
        pass


class MissingEnvironmentVariable(Exception):
    pass


def get_env(name):
    """Get variable from .env, otherwise raise exception"""
    try:
        return os.environ[name]
    except KeyError:
        raise MissingEnvironmentVariable(rf"Add {name} variable to your .env file.")


DISCORD_API_SECRET = get_env("DISCORD_API_TOKEN")

WEBHOOKS = {
    "raid": get_env("WEBHOOK_BOT_CHANNEL_RAID"),
    "strike": get_env("WEBHOOK_BOT_CHANNEL_STRIKE"),
    "fractal": get_env("WEBHOOK_BOT_CHANNEL_FRACTAL"),
    "leaderboard": get_env("WEBHOOK_BOT_CHANNEL_LEADERBOARD"),
    "cerus_cm": get_env("WEBHOOK_BOT_CHANNEL_CERUS_CM"),
}


LEADERBOARD_THREADS = {  # thread channel ids in discord.
    "raid": get_env("WEBHOOK_BOT_CHANNEL_LEADERBOARD_RAIDS"),
    "strike": get_env("WEBHOOK_BOT_CHANNEL_LEADERBOARD_STRIKES"),
    "fractal": get_env("WEBHOOK_BOT_CHANNEL_LEADERBOARD_FRACTALS"),
}

CORE_MINIMUM = {
    "raid": int(get_env("CORE_MINIMUM_RAID")),
    "strike": int(get_env("CORE_MINIMUM_STRIKE")),
    "fractal": int(get_env("CORE_MINIMUM_FRACTAL")),
}
INCLUDE_NON_CORE_LOGS = get_env("INCLUDE_NON_CORE_LOGS") == "True"  # Include non core logs on leaderboards

DPS_REPORT_USERTOKEN = get_env("DPS_REPORT_USERTOKEN")
MEAN_OR_MEDIAN = get_env("MEAN_OR_MEDIAN")
MEDALS_TYPE = get_env("MEDALS_TYPE")  # Options=['original', 'percentile', 'newgame']
RANK_BINS_PERCENTILE = ast.literal_eval(get_env("RANK_BINS_PERCENTILE"))  # Distribution of percentile bins.
# Defaults to [20, 40, 50, 60, 70, 80, 90, 100]. This means if a log is faster than
# 90% to 100% of other logs, it will be assigned to the last bin.

DEBUG = get_env("DEBUG") == "True"
LOGLEVEL = get_env("LOGLEVEL") or "INFO"


if DEBUG:
    LOGFORMAT = "%(asctime)s|%(levelname)-8s| %(module)-30s:%(lineno)-4d| %(message)s"
    # LOGFORMAT = "%(asctime)s|%(levelname)-8s| %(name)s:%(lineno)-4d| %(message)s"  # name could get a bit long.
else:
    LOGFORMAT = "%(asctime)s|%(levelname)-8s| %(message)s"


BASE_DIR = Path(__file__).resolve().parents[1]  # gw2_logs_archive
PROJECT_DIR = Path(__file__).resolve().parents[2]  # git repo
EI_PARSED_LOGS_DIR = PROJECT_DIR.joinpath("Data", "parsed_logs")


DPS_LOGS_DIR = rf"{Path.home()}\Documents\Guild Wars 2\addons\arcdps\arcdps.cbtlogs"
DPS_LOGS_DIR = Path(get_env("DPS_LOGS_DIR"))
EXTRA_LOGS_DIR = Path(get_env("EXTRA_LOGS_DIR"))
# Shared drive with other static members, they can post logs there to upload.


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": LOGFORMAT,
            "datefmt": "%H:%M:%S",
        },
    },
    "handlers": {
        "null": {
            "class": "logging.NullHandler",
        },
        "console": {
            "level": "NOTSET",
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "stderr": {
            "level": "ERROR",
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "": {  # root logger
            "level": "WARNING",
            "handlers": ["console", "stderr"],
        },
        "__main__": {
            "level": "DEBUG",
        },
        "scripts": {
            "level": LOGLEVEL,
        },
        "gw2_logs": {
            "level": LOGLEVEL,
        },
    },
}
# Django will do this by default, but easier to follow if its explicit.
logging.config.dictConfig(LOGGING)

logger = logging.getLogger(__name__)

if not DPS_LOGS_DIR.exists():
    logger.warning("ArcDPS folder not found. Set the DPS_LOGS_DIR variable in the .env")

"""
Django settings for gw2_logs_archive project.

Generated by 'django-admin startproject' using Django 4.2.8.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""


# Build paths inside the project like this: BASE_DIR / 'subdir'.


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-=x2b*%fr15axa)c(=^#-6uk4wi%_)rta069m9ts!0mny%7s@%*"

# SECURITY WARNING: don't run with debug turned on in production!

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "gw2_logs",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "bot_settings.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "bot_settings.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
DB_SETTINGS = getattr(local_settings, "DATABASES", {})
DB_SETTINGS_DEFAULT = DB_SETTINGS.get("default", {})


if DB_SETTINGS_DEFAULT != {}:
    DATABASES = {"default": DB_SETTINGS_DEFAULT}
    # Example postgresql database settings. Place this in a new file;
    # data/local_settings.py
    #
    # DATABASES = {
    #     "default": {
    #         "NAME": "gw2_logs_archive",
    #         "ENGINE": "django.db.backends.postgresql",
    #         "USER": "",
    #         "PASSWORD": "",
    #         "HOST": "",  # empty string for localhost.
    #         "PORT": "",  # empty string for default.
    #     },
    # }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": PROJECT_DIR.joinpath("data", "db.sqlite3"),
        },
    }
logger.warning(f"DATABASE ENGINE: {DATABASES['default'].get('ENGINE')}")
logger.warning(f"DATABASE NAME: {DATABASES['default'].get('NAME')}")

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "static/"

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
