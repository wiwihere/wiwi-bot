# %%

import gzip
import json
import logging
import os
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management import call_command

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)


logger = logging.getLogger(__name__)

EI_PARSER_FOLDER = settings.PROJECT_DIR.joinpath("GW2EI_parser")
EI_SETTINGS_DEFAULT = settings.BASE_DIR.joinpath("bot_settings", "gw2ei_settings_default.conf")


class EliteInsightsParser:
    def __init__(self):
        """Interaction with EliteInisghts CLI"""
        self.EI_exe = EI_PARSER_FOLDER.joinpath("GuildWars2EliteInsights-CLI.exe")
        self.out_dir = None  # Set in .create_settings
        self.settings = None  # Set in .create_settings

        self.download_or_update_EI()

    def download_or_update_EI(self):
        """Download or update EliteInisghts CLI

        Automatically checks version every week.
        """
        call_command("update_elite_insights_version", auto_update_check=True)

    def create_settings(self, out_dir, setting_in_path=EI_SETTINGS_DEFAULT, create_html=False):
        """
        ei_settings: str
            Path to ei settings to use. Will be edited based on inputs
        out_dir: str
            Directory where output jsons are placed.
        create_html: bool, default False
            Also create html of the fight
        """

        self.out_dir = out_dir
        out_dir.mkdir(exist_ok=True)

        setting_out_path = out_dir.joinpath("gw2ei_settings.conf")

        # Load default settings
        set_default = setting_in_path.read_text()

        # Format the str with provided variables
        set_str = set_default.format(create_html=create_html, out_dir=out_dir)

        # Create settigns in output folder
        setting_out_path.write_text(set_str)
        self.settings = setting_out_path

    def parse_log(self, evtc_path) -> Path:
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

        js_path = self.find_parsed_json(evtc_path=evtc_path)

        if js_path:
            logger.info(f"Log {evtc_path.name} already parsed")
        else:
            # Call the parser
            res = subprocess.run([str(self.EI_exe), "-c", f"{self.settings}", evtc_path])
            js_path = self.find_parsed_json(evtc_path=evtc_path)

        return js_path

    def find_parsed_json(self, evtc_path):
        """Output gets a bit of a different name, find it."""
        evtc_path = Path(evtc_path)

        files = list(self.out_dir.glob(f"{evtc_path.stem}*.gz"))
        if len(files) > 0:
            file = files[0]
            return file

    @staticmethod
    def load_json_gz(js_path):
        """Load zipped json as detailed json"""

        with gzip.open(js_path, "r") as fin:
            json_bytes = fin.read()

        json_str = json_bytes.decode("utf-8")
        data = json.loads(json_str)
        return data


# %%

if __name__ == "__main__":
    self = ei_parser = EliteInsightsParser()
    out_dir = settings.EI_PARSED_LOGS_DIR.joinpath("20250125")
    setting_in_path = EI_SETTINGS_DEFAULT
    create_html = False
    ei_parser.create_settings(out_dir=out_dir, setting_in_path=setting_in_path, create_html=False)

    d = ei_parser.parse_log(evtc_path=r"")
    r2 = EliteInsightsParser.load_json_gz(js_path=d)
    r2["eiEncounterID"]
# %%
