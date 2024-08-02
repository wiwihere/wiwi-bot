# %%

import gzip
import json
import os
import subprocess
from pathlib import Path

proj_path = Path(os.path.abspath(os.path.dirname(__file__))).parents[1]
EI_PARSER_FOLDER = proj_path / "GW2EI_parser"

EI_SETTINGS_DEFAULT = proj_path / "gw2_database" / "bot_settings" / "gw2ei_settings_default.conf"


class EliteInisghtsParser:
    def __init__(self):
        self.EI_exe = EI_PARSER_FOLDER.joinpath("GuildWars2EliteInsights.exe")
        self.out_dir = None  # Set in .make_settings
        self.settings = None  # Set in .make_settings

    def make_settings(self, out_dir, setting_in_path=EI_SETTINGS_DEFAULT, create_html=False):
        """
        ei_settings: str
            Path to ei settings to use. Will be edited based on inputs
        out_dir: str
            Directory where output jsons are placed.
        create_html: bool, default False
            Also create html of the fight
        """

        self.out_dir = out_dir
        setting_out_path = out_dir.joinpath("gw2ei_settings.conf")

        # Load default settings and format them with the variables.
        with open(setting_in_path, "r") as f:
            set_default = f.read()

            set_str = set_default.format(create_html=create_html, out_dir=out_dir)

        # Create settigns in output folder
        with open(setting_out_path, "w") as f:
            f.write(set_str)

        self.settings = setting_out_path

        self.out_dir.mkdir(exist_ok=True)

    def parse_log(self, evtc_path) -> Path:
        """Parse to json locally. Uploading to dpsreport is not implemented.

        evtc_path: str
            Path to log

        Returns
        -------
        Parsed log path
        """
        evtc_path = Path(evtc_path)

        if self.settings is None:
            raise ValueError("Run self.make_settings first.")

        js_path = self.find_parsed_json(evtc_path=evtc_path)

        if js_path:
            print(f"Log {evtc_path.name} already parsed")
        else:
            # Download EI
            if not self.EI_exe.exists():
                print("EI parser not found. Run bin/elite_insights_update.cmd")
                # TODO call download command

            # Call the parser
            subprocess.run([str(self.EI_exe), "-c", f"{self.settings}", evtc_path])
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
        """Load zipped json"""

        with gzip.open(js_path, "r") as fin:
            json_bytes = fin.read()

        json_str = json_bytes.decode("utf-8")
        data = json.loads(json_str)
        return data


# %%

# if __name__ == "__main__":
# ei_parser = EliteInisghtsParser()
# ei_parser.make_settings(out_dir=EI_PARSER_FOLDER.joinpath("20240729"), create_html=False)

# d = ei_parser.parse_log(
#     evtc_path=
# )
# r2 = EliteInisghtsParser.load_json_gz(js_path=d)
# r2['eiEncounterID']
# %%
