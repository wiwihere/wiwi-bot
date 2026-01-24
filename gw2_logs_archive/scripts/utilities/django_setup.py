import os

import django


def run():
    """Together with PYTHONPATH and DJANGO_SETTINGS_MODULE in the .env,
    this  will setup django to work within jupyter interactive windows.
    """
    os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
    django.setup()
