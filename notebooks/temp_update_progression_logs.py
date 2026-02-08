# %%

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import logging
import time
from pathlib import Path
from typing import Literal, Optional

from django.conf import settings
from gw2_logs.models import (
    DiscordMessage,
    DpsLog,
    Encounter,
    InstanceClearGroup,
)
from scripts.discord_interaction.build_message_cerus import send_cerus_progression_discord_message
from scripts.encounter_progression.cerus_service import CerusProgressionService
from scripts.log_helpers import (
    today_y_m_d,
    zfill_y_m_d,
)
from scripts.log_processing.ei_parser import EliteInsightsParser
from scripts.log_processing.log_files import LogFile, LogFilesDate
from scripts.log_processing.log_uploader import LogUploader
from scripts.log_processing.logfile_processing import _process_log_local, process_logs_once
from scripts.model_interactions.dpslog_service import DpsLogService
from scripts.model_interactions.instance_clear_group import InstanceClearGroupInteraction

logger = logging.getLogger(__name__)

# %%
if __name__ == "__main__":
    y, m, d = today_y_m_d()
    y, m, d = 2024, 4, 20
    clear_group_base_name = "cerus_cm"
    processing_type = "local"
    force_update = True

    # Initialize local parser
    ei_parser = EliteInsightsParser()
    ei_parser.create_settings(out_dir=settings.EI_PARSED_LOGS_DIR.joinpath(zfill_y_m_d(y, m, d)), create_html=False)

    progression_service = CerusProgressionService(clear_group_base_name=clear_group_base_name, y=y, m=m, d=d)

    log_files_date_cls = LogFilesDate(y=y, m=m, d=d, allowed_folder_names=[progression_service.encounter.folder_names])
    logfiles = log_files_date_cls.get_unprocessed_logs(processing_type="local")

    for logfile in logfiles:
        log_path = logfile.path

        parsed_path = ei_parser.parse_log(log_path=log_path)
        if parsed_path is not None:
            detailed_parsed_log = EliteInsightsParser.load_parsed_json(parsed_path=parsed_path)
            dpslog = DpsLogService().get_update_create_from_ei_parsed_log(
                detailed_parsed_log=detailed_parsed_log, log_path=log_path, force_update=force_update
            )

        break

    # processed_logs = process_logs_once(
    #     processing_type=processing_type,
    #     log_files_date_cls=log_files_date_cls,
    #     ei_parser=ei_parser,
    # )
    # # %%
