import os

import django


def run():
    os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
    django.setup()
