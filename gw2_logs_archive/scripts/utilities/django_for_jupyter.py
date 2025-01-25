import os


def init_django_from_commands(project_name=None):
    """Spin up Django when its a command."""
    # os.chdir(pwd)
    project_name = project_name or os.environ.get("DJANGO_PROJECT") or None
    if project_name is None:
        raise Exception("""Set an enviroment variable:\n
`DJANGO_PROJECT=your_project_name`\n
or call:\n
`init_django(your_project_name)`
""")
    # sys.path.insert(0, str(pwd.parent))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"{project_name}.bot_settings.settings")
    os.environ["DJANGO_SETTINGS_MODULE"] = "{project_name}.bot_settings.settings"
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    import django

    django.setup()
