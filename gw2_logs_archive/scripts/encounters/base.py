# %%

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import datetime
import logging
import time

import numpy as np
import pandas as pd
from django.conf import settings
from django.db.models import Q
from gw2_logs.models import (
    DpsLog,
    Emoji,
    Encounter,
    InstanceClearGroup,
)
from scripts.discord_interaction.build_embeds import create_discord_embeds
from scripts.discord_interaction.send_message import create_or_update_discord_message
from scripts.log_helpers import (
    RANK_EMOTES_CUPS,
    create_discord_time,
    create_rank_emote_dict_percentiles,
    get_duration_str,
    today_y_m_d,
    zfill_y_m_d,
)
from scripts.log_processing.ei_parser import EliteInsightsParser
from scripts.log_processing.log_files import LogFile, LogFilesDate
from scripts.log_processing.log_uploader import LogUploader
from scripts.model_interactions.dps_log import DpsLogInteraction


class BaseEncounterRunner:
    encounter_name: str
    webhook_key: str
    use_percentiles: bool = True

    def __init__(self, y, m, d):
        self.y, self.m, self.d = y, m, d
        self.encounter = Encounter.objects.get(name=self.encounter_name)
        self.ei_parser = EliteInsightsParser()

    def setup_parser(self):
        self.ei_parser.create_settings(
            out_dir=settings.EI_PARSED_LOGS_DIR.joinpath(zfill_y_m_d(self.y, self.m, self.d)),
            create_html=False,
        )

    def run(self):
        self.setup_parser()
        self.process_logs()

    def process_logs(self):
        raise NotImplementedError
