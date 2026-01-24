# %%
"""Use this to print the reposistory tree."""

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

from pathlib import Path

from django.conf import settings


def print_tree(root: Path, indent: str = ""):
    items = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    for i, item in enumerate(items):
        is_last = i == len(items) - 1
        prefix = "└── " if is_last else "├── "
        stop = False
        if item.suffix in [".pyc", ".png", ".gif"]:
            stop = True

        for n in ["__pycache__", "migrations"]:
            if n in item.parts:
                stop = True

        if stop:
            continue

        print(indent + prefix + item.name)
        if item.is_dir():
            extension = "    " if is_last else "│   "
            print_tree(item, indent + extension)


if __name__ == "__main__":
    indent = ""
    root = settings.BASE_DIR
    print_tree(root)
