import os, sys
from pathlib import Path

# PWD = os.getenv('PWD')
"""https://www.youtube.com/watch?v=t3mk_u0rprM"""
PWD = os.path.dirname(os.getcwd())
PROJ_MISSING_MSG = """Set an enviroment variable:\n
`DJANGO_PROJECT=your_project_name`\n
or call:\n
`init_django(your_project_name)`
"""


def init_django(project_name=None):
    """Spin up Django"""
    os.chdir(PWD)
    project_name = project_name or os.environ.get("DJANGO_PROJECT") or None
    if project_name is None:
        raise Exception(PROJ_MISSING_MSG)
    sys.path.insert(0, PWD)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "spoc_settings.settings")
    os.environ["DJANGO_SETTINGS_MODULE"] = "spoc_settings.settings"
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    import django

    django.setup()


def init_django_production(project_name=None):
    """Spin up Django"""
    os.chdir(PWD)
    project_name = project_name or os.environ.get("DJANGO_PROJECT") or None
    if project_name is None:
        raise Exception(PROJ_MISSING_MSG)
    sys.path.insert(0, PWD)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "spoc_settings.settings")
    os.environ["DJANGO_SETTINGS_MODULE"] = "spoc_settings.settings"
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    import django

    django.setup()


def init_django_from_commands(project_name=None, pwd=Path(__file__).parents[1]):
    """Spin up Django when its a command."""
    os.chdir(pwd)
    project_name = project_name or os.environ.get("DJANGO_PROJECT") or None
    if project_name is None:
        raise Exception(PROJ_MISSING_MSG)
    sys.path.insert(0, str(pwd.parent))

    print(pwd)

    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "gw2_database.gw2_database.settings"
    )
    os.environ["DJANGO_SETTINGS_MODULE"] = "gw2_database.gw2_database.settings"
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    import django

    django.setup()
