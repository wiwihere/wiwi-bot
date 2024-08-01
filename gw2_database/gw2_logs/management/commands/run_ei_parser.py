# %%

import gzip
import json
import os
import subprocess
from pathlib import Path

proj_path = Path(os.path.abspath(os.path.dirname(__file__))).parents[3]
EI_PARSER_FOLDER = proj_path / "GW2EI_parser"

EI_SETTINGS_DEFAULT = proj_path / "gw2_database" / "bot_settings" / "gw2ei_settings_default.conf"
EI_SETTINGS = proj_path / "gw2_database" / "bot_settings" / "gw2ei_settings.conf"


class EliteInisghtsParser:
    def __init__(self):
        self.settings_created = False
        self.out_dir = None
        self.EI_exe = EI_PARSER_FOLDER.joinpath("GuildWars2EliteInsights.exe")

    def make_settings(self, default_path, out_path, out_dir, create_html=False):
        """
        ei_settings: str
            Path to ei settings to use. Will be edited based on inputs
        out_dir: str
            Directory where output jsons are placed.
        create_html: bool, default False
            Also create html of the fight
        """

        self.out_dir = out_dir

        with open(default_path, "r") as f:
            set_default = f.read()

            set_str = set_default.format(create_html=create_html, out_dir=out_dir)

        with open(out_path, "w") as f:
            f.write(set_str)

        self.settings_created = True

    def parse_log(self, evtc_path):
        """Parse to json locally. Uploading to dpsreport is not implemented.

        evtc_path: str
            Path to log

        Returns
        -------
        Parsed log as json
        """
        if self.settings_created is False:
            raise ValueError("Run self.make_settings first.")

        js_path = self.find_parsed_json(evtc_path=evtc_path)

        if js_path.exists():
            print(f"Log {evtc_path.name} already parsed")
        else:
            # Download EI
            if not self.EI_exe.exists():
                print("EI parser not found. Run bin/elite_insights_update.cmd")
                # TODO call download command

            # Call the parser
            subprocess.run([str(self.EI_exe), "-c", f"{ei_settings}", p])

        json_data = self.load_json_gz(js_path=js_path)
        return json_data

    def find_parsed_json(self, evtc_path):
        """ "The output gets a bit of a different name, find it."""

        evtc_path.stem

        self.out_dir

    def load_json_gz(self, js_path):
        """Load zipped json"""

        with gzip.open(js_path, "r") as fin:
            json_bytes = fin.read()

        json_str = json_bytes.decode("utf-8")
        data = json.loads(json_str)
        return data


# %%


# %%

out_dir = 1
ei_settings = EI_SETTINGS
create_html = False
upload_dpsreport = False
