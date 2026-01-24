# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import gzip
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

from django.conf import settings
from scripts.log_processing.ei_updater import EliteInsightsUpdater

logger = logging.getLogger(__name__)

EI_SETTINGS_DEFAULT = settings.BASE_DIR.joinpath("bot_settings", "gw2ei_settings_default.conf")


class EliteInsightsParser:
    def __init__(self, auto_update: bool = True, auto_update_check: bool = True, days_between_checks: int = 6):
        """Interaction with EliteInsights CLI

        Parameters
        ----------
        auto_update : bool, default True
            Whether to automatically update EliteInsights parser on init.
        auto_update_check : bool, default True
            Whether to check the date before updating the parser.
        days_between_checks : int, default 6
            Number of days between automatic update checks.
        """
        self.out_dir = None  # Set in .create_settings
        self.settings = None  # Set in .create_settings

        # Paths
        self.ei_parser_folder = settings.PROJECT_DIR.joinpath("GW2EI_parser")
        self.EI_exe = self.ei_parser_folder.joinpath("GuildWars2EliteInsights-CLI.exe")

        self.updater = EliteInsightsUpdater(self.ei_parser_folder)

        if auto_update:
            # Download or update EliteInsights CLI
            # Automatically checks version only once every week.
            self.updater.update(auto_update_check=auto_update_check, days_between_checks=days_between_checks)
        if not self.EI_exe.exists():
            self.updater.update(auto_update_check=False)

    def create_settings(
        self,
        out_dir: Path,
        setting_in_path: Path = EI_SETTINGS_DEFAULT,
        create_html: bool = False,
    ) -> None:
        """
        Write conf file to settings_out_path.

        setting_in_path : str
            Path to ei settings to use. Will be edited based on inputs
        out_dir : str
            Directory where output jsons are placed.
        create_html : bool, default False
            Also create html of the fight
        """

        self.out_dir = out_dir
        out_dir.mkdir(exist_ok=True)

        setting_output_path = out_dir.joinpath("gw2ei_settings.conf")

        # Load default settings
        settings_default = setting_in_path.read_text()

        # Format the str with provided variables
        settings_output = settings_default.format(create_html=create_html, out_dir=out_dir)

        # Create settigns in output folder
        setting_output_path.write_text(settings_output)
        self.settings = setting_output_path

    def parse_log(self, evtc_path: Path) -> Optional[Path]:
        """Parse to json locally. Uploading to dps.report is not implemented.
        returns evtc_path=None when process doesnt parse the log. For instance due to
        Program: Fight is too short: 0 < 2200

        evtc_path: str
            Path to original log

        Returns
        -------
        Parsed log path
        """
        evtc_path = Path(evtc_path)

        if self.settings is None:
            raise ValueError("Run self.create_settings first.")

        js_path = self._find_parsed_json(evtc_path=evtc_path)

        if js_path:
            logger.info(f"Log {evtc_path.name} already parsed")
        else:
            # Call the parser
            res = subprocess.run(
                [str(self.EI_exe), "-c", f"{self.settings}", evtc_path], capture_output=True, text=True
            )

            if res.returncode != 0:
                logger.warning(f"EI failed for {evtc_path.name}: {res.stderr}")
                return None

            js_path = self._find_parsed_json(evtc_path=evtc_path)

        return js_path

    def _find_parsed_json(self, evtc_path: Path) -> Optional[Path]:
        """Output gets a bit of a different name, find it."""
        evtc_path = Path(evtc_path)

        files = list(self.out_dir.glob(f"{evtc_path.stem}*.gz"))
        if len(files) > 0:
            file = files[0]
            return file
        else:
            logger.warning(f"File {evtc_path} not found.")

    @staticmethod
    def load_json_gz(js_path: Path) -> dict:
        """Load zipped json as detailed json"""

        with gzip.open(js_path, "r") as fin:
            json_bytes = fin.read()

        json_str = json_bytes.decode("utf-8")
        data = json.loads(json_str)
        return data


# %%

if __name__ == "__main__":
    self = ei_parser = EliteInsightsParser()
    out_dir = settings.EI_PARSED_LOGS_DIR.joinpath("202512081")
    setting_in_path = EI_SETTINGS_DEFAULT
    create_html = True
    ei_parser.create_settings(out_dir=out_dir, setting_in_path=setting_in_path, create_html=create_html)

    d = ei_parser.parse_log(evtc_path=r"")
    r2 = EliteInsightsParser.load_json_gz(js_path=d)
    r2["eiEncounterID"]
# %%
