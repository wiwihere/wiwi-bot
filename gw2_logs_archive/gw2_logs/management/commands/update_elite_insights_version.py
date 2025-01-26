# %%
import datetime
import os
from pathlib import Path
from zipfile import ZipFile

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)


class Command(BaseCommand):
    help = "Update elite insights parser"

    def add_arguments(self, parser):
        # Add the `check_date` argument (as a flag in this case)
        parser.add_argument(
            "--auto_update_check",
            type=bool,  # Makes it bool
            help="Checks the date before updating the parser",
        )

    def handle(self, *args, **options):
        auto_update_check = options.get("auto_update_check", False)  # Retrieve the value of the argument
        url = "https://api.github.com/repos/baaron4/GW2-Elite-Insights-Parser/releases/latest"

        EI_PARSER_FOLDER = settings.PROJECT_DIR.joinpath("GW2EI_parser")
        version_file = EI_PARSER_FOLDER / "version.txt"
        last_checked_file = EI_PARSER_FOLDER / "last_checked.txt"

        # Check if we need to proceed based on auto_update_check flag
        if auto_update_check:
            if last_checked_file.exists():
                last_checked = last_checked_file.read_text()
                last_checked_date = datetime.datetime.strptime(last_checked, "%Y%m%d")
                delta = datetime.datetime.now() - last_checked_date
                if delta.days <= 7:
                    print(
                        f"EI version last checkeded {delta.days} days ago. No need to auto update."
                    )  # TODO debug logging
                    return

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
            EI_PARSER_FOLDER.mkdir(exist_ok=True)

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
                    f.write(f"{ei_version}\ninstalled version from {url}")

                # Unzip
                with ZipFile(EI_PARSER_FOLDER / "download.zip", "r") as zObject:
                    zObject.extractall(path=EI_PARSER_FOLDER)
            print("Update complete")

        # Update the last_checked.txt file
        last_checked_file.write_text(datetime.datetime.now().strftime("%Y%m%d"))
