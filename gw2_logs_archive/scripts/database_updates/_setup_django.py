# Required in every scripts folder to allow running django in the ipykernel
import os
import sys
from pathlib import Path


def init_django(script_path, marker="manage.py"):
    """Find the Django project root by looking for a marker file.
    Adds the project directory to sys.path if it's not already there.
    Initializes Django if it's not already initialized.
    """
    path = Path(script_path).resolve()
    for parent in path.parents:
        if (parent / marker).exists():
            project_dir = str(parent)
            root_dir = str(parent.parent)

    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)

    # Initialize Django
    os.chdir(root_dir)
    from gw2_logs_archive.scripts.utilities.django_for_jupyter import init_django_from_commands

    init_django_from_commands("gw2_logs_archive")
    print(f"Initialized Django at {project_dir}")
