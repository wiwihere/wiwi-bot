# %%
import datetime
import logging
import os
from pathlib import Path
from zipfile import ZipFile

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)


logger = logging.getLogger(__name__)


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
                    logger.debug(f"EI version last checked {delta.days} days ago. No need to auto update.")
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
                logger.info(f"EI version up to date: {v}")

        if cont:
            logger.info(f"Updating GW2 Elite Inisghts Parser to version from {v} to {ei_version}")
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
                    f.write(f"installed version from {url}")

                # Unzip
                with ZipFile(EI_PARSER_FOLDER / "download.zip", "r") as zObject:
                    zObject.extractall(path=EI_PARSER_FOLDER)
            logger.info("EI update complete")

        # Update the last_checked.txt file
        last_checked_file.write_text(datetime.datetime.now().strftime("%Y%m%d"))
