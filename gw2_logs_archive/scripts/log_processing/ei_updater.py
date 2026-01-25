# %%

import datetime
import logging
from pathlib import Path
from typing import Optional, Tuple
from zipfile import ZipFile

import requests

logger = logging.getLogger(__name__)


class EliteInsightsUpdater:
    """Update Elite Insights Parser from github releases. Keeps track of version and last checked date.
    Will not check github for updates more often than specified number of days.
    """

    def __init__(self, ei_parser_folder: Path):
        self.ei_parser_folder = ei_parser_folder
        self.version_file = ei_parser_folder / "version.txt"
        self.last_checked_file = ei_parser_folder / "last_checked.txt"

    def get_latest_version_from_github(self) -> Tuple[dict, str]:
        logger.info("Retrieving latest Elite Insights version from github")
        url = "https://api.github.com/repos/baaron4/GW2-Elite-Insights-Parser/releases/latest"

        # Get release info from github
        release_info_raw = requests.get(url)
        release_info_raw.raise_for_status()
        release_info = release_info_raw.json()

        # Extract ei_version
        ei_version = release_info["name"]

        return release_info, ei_version

    def _should_check_for_update(self, days_between_checks: int) -> bool:
        """Read the lat_checked.txt file and see if we need to check for an update again.
        If the version was changed within the last `days_between_checks` days, no need to check again.
        This saves github api calls.
        """
        if self.last_checked_file.exists():
            last_checked = self.last_checked_file.read_text()
            last_checked_date = datetime.datetime.strptime(last_checked, "%Y%m%d")
            delta = datetime.datetime.now() - last_checked_date
            if delta.days <= days_between_checks:
                logger.debug(f"EI version last checked {delta.days} days ago. No need to auto update.")
                return False
        return True

    def _download(self, release_info: dict, ei_version: str) -> None:
        dl_url = None
        for asset in release_info["assets"]:
            if asset["name"] == "GW2EICLI.zip":
                dl_url = asset["browser_download_url"]
                break

        # When found, download and update the version
        if dl_url:
            logger.info(f"Downloading EI version {ei_version} from {dl_url}")

            # Download zip
            response = requests.get(dl_url)
            response.raise_for_status()

            with open(self.ei_parser_folder / "download.zip", "wb") as f:
                f.write(response.content)

            # Write version file
            with open(self.version_file, "w") as f:
                f.write(ei_version)
                f.write(f"\ninstalled version from {dl_url}")

            # Unzip
            with ZipFile(self.ei_parser_folder / "download.zip", "r") as zObject:
                zObject.extractall(path=self.ei_parser_folder)

    def update(self, auto_update_check: bool, days_between_checks: Optional[int] = 6) -> None:
        # Check if we need to proceed based on auto_update_check flag
        self.ei_parser_folder.mkdir(exist_ok=True)

        if auto_update_check:
            if not self._should_check_for_update(days_between_checks=days_between_checks):
                return

        release_info, ei_version = self.get_latest_version_from_github()

        # Check if release available
        should_update = True
        version = "unknown"
        if self.version_file.exists():
            version = self.version_file.read_text().split("\n")[0]

            # Dont download when the latest release is the same as the local version.
            if ei_version == version:
                should_update = False
                logger.info(f"EI version up to date: {version}")

        if should_update:
            logger.info(f"Updating GW2 Elite Insights Parser to version from {version} to {ei_version}")

            # Get the zip download url
            self._download(release_info=release_info, ei_version=ei_version)

            logger.info("EI update complete")

        # Update the last_checked.txt file
        self.last_checked_file.write_text(datetime.datetime.now().strftime("%Y%m%d"))
