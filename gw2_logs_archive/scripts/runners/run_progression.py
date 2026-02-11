# %% gw2_logs_archive\scripts\runners\run_progression_cerus.py
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import logging
import time
from typing import Optional

from django.conf import settings
from scripts.discord_interaction.build_message_progression import send_progression_discord_message
from scripts.encounter_progression.configurable_progression_service import ConfigurableProgressionService
from scripts.log_helpers import (
    today_y_m_d,
    zfill_y_m_d,
)
from scripts.log_processing.ei_parser import EliteInsightsParser
from scripts.log_processing.log_files import LogFilesDate
from scripts.log_processing.logfile_processing import process_logs_once

logger = logging.getLogger(__name__)


def run_progression_service(
    clear_group_base_name: str,
    y: Optional[int] = None,
    m: Optional[int] = None,
    d: Optional[int] = None,
) -> None:
    run_count = 0
    SLEEPTIME = 30
    MAXSLEEPTIME = 60 * SLEEPTIME  # Number of seconds without a log until we stop looking.
    current_sleeptime = MAXSLEEPTIME

    # Initialize local parser
    ei_parser = EliteInsightsParser()
    ei_parser.create_settings(out_dir=settings.EI_PARSED_LOGS_DIR.joinpath(zfill_y_m_d(y, m, d)), create_html=False)

    progression_service = ConfigurableProgressionService(clear_group_base_name=clear_group_base_name, y=y, m=m, d=d)

    log_files_date_cls = LogFilesDate(
        y=y, m=m, d=d, allowed_folder_names=progression_service.encounter.folder_names.split(";")
    )

    # Flow start
    PROCESSING_SEQUENCE = ["local", "upload"] + ["local"] * 9

    while True:
        for processing_type in PROCESSING_SEQUENCE:
            processed_logs = process_logs_once(
                processing_type=processing_type,
                log_files_date_cls=log_files_date_cls,
                ei_parser=ei_parser,
            )

            if processed_logs:
                current_sleeptime = MAXSLEEPTIME

            if len(processed_logs) > 0:
                progression_service.update_dpslogs(processed_logs=processed_logs)
                progression_service.update_instance_clear_start_time_and_duration()
                send_progression_discord_message(progression_service)

            if processing_type == "local":
                time.sleep(SLEEPTIME / 10)

        current_sleeptime -= SLEEPTIME
        logger.info(f"Run {run_count} done")
        run_count += 1
        if (current_sleeptime < 0) or ((y, m, d) != today_y_m_d()):
            logger.info("Finished run")
            break


# %%
if __name__ == "__main__":
    y, m, d = today_y_m_d()
    y, m, d = 2024, 4, 20
    clear_group_base_name = "cerus_cm"

    y, m, d = 2025, 12, 8
    clear_group_base_name = "decima_cm"
