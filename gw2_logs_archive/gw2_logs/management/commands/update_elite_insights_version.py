# %%
import os
from pathlib import Path
from zipfile import ZipFile

import requests
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Update elite insights parser"

    def handle(self, *args, **options):
        pass


url = "https://api.github.com/repos/baaron4/GW2-Elite-Insights-Parser/releases/latest"


proj_path = os.path.abspath(os.path.dirname(__file__))
EI_PARSER_FOLDER = Path(proj_path).parents[3] / "GW2EI_parser"

version_file = EI_PARSER_FOLDER / "version.txt"

# %%

# Get release info from github
r = requests.get(url)

ei_version = r.json()["name"]

# Check if release available
cont = True
if version_file.exists():
    v = version_file.read_text().split("\n")[0]

    # Dont download when the latest release is the same as the local version.
    if ei_version == v:
        cont = False
        print(f"Version up to date: {v}")
    else:
        print(f"Current version: {v}")

if cont:
    print(f"Updating GW2 Elite Inisghts Parser to version: {ei_version}")
    # Get the zip download url
    dl_url = None
    for asset in r.json()["assets"]:
        if asset["name"] == "GW2EICLI.zip":
            dl_url = asset["browser_download_url"]
            break

    # When found, download and update the version
    if dl_url:
        # Download zip
        response = requests.get(dl_url)
        with open(EI_PARSER_FOLDER / "download.zip", "wb") as f:
            f.write(response.content)

        # Write version file
        with open(version_file, "w") as f:
            f.write(ei_version)
            f.write(f"\ninstalled version from {url}")

        # Unzip
        with ZipFile(EI_PARSER_FOLDER / "download.zip", "r") as zObject:
            zObject.extractall(path=EI_PARSER_FOLDER)
    print("Update complete")


# %%
