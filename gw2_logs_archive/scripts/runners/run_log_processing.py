# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging
import time
from typing import Literal, Optional

from django.conf import settings
from scripts.log_helpers import (
    create_folder_names,
    today_y_m_d,
    zfill_y_m_d,
)
from scripts.log_processing.ei_parser import EliteInsightsParser
from scripts.log_processing.log_files import LogFilesDate
from scripts.log_processing.logfile_processing import process_logs_once
from scripts.model_interactions.instance_clear_group import InstanceClearGroupInteraction
from scripts.runners.run_leaderboard import run_leaderboard

logger = logging.getLogger(__name__)

SLEEPTIME = 30
MAXSLEEPTIME = 60 * SLEEPTIME  # Number of seconds without a log until we stop looking.


def run_log_processing(
    y: Optional[int] = None,
    m: Optional[int] = None,
    d: Optional[int] = None,
    itype_groups: Optional[list[Literal["raid", "strike", "fractal"]]] = None,
) -> None:
    """Run complete log processing flow for a given date and instance type groups."""
    if y is None:
        y, m, d = today_y_m_d()
    if itype_groups is None:
        itype_groups = ["raid", "strike", "fractal"]

    logger.info(f"Starting log import for {zfill_y_m_d(y, m, d)}")
    logger.info(f"Selected instance types: {itype_groups}")

    # Initialize local parser
    ei_parser = EliteInsightsParser()
    ei_parser.create_settings(out_dir=settings.EI_PARSED_LOGS_DIR.joinpath(zfill_y_m_d(y, m, d)), create_html=False)

    # possible folder names for selected itype_groups
    allowed_folder_names = create_folder_names(itype_groups=itype_groups)
    log_files_date_cls = LogFilesDate(y=y, m=m, d=d, allowed_folder_names=allowed_folder_names)

    # Flow start
    PROCESSING_SEQUENCE = ["local", "upload"] + ["local"] * 9
    run_count = 0
    current_sleeptime = MAXSLEEPTIME
    while True:
        for processing_type in PROCESSING_SEQUENCE:
            icgi = None
            processed_logs = process_logs_once(
                processing_type=processing_type,
                log_files_date_cls=log_files_date_cls,
                ei_parser=ei_parser,
            )

            for log in processed_logs:
                icgi = InstanceClearGroupInteraction.create_from_date(
                    y=y, m=m, d=d, itype_group=log.encounter.instance.instance_group.name
                )

                # Build and send Discord message
                if icgi is not None:
                    icgi.sync_discord_message_id()

            if len(processed_logs) > 0:
                # Update discord, only do it on the last log, so we dont spam the discord api too often.
                current_sleeptime = MAXSLEEPTIME
                icgi.send_discord_message()

            if processing_type == "local":
                time.sleep(SLEEPTIME / 10)

        # 6. Update leaderboards and exit
        # Only update when there hasnt been a new log parsed for the duration of sleeptime.
        if (current_sleeptime < 0) or ((y, m, d) != today_y_m_d()):
            logger.info("Updating leaderboards")
            run_leaderboard(instance_type="fractal")
            run_leaderboard(instance_type="raid")
            run_leaderboard(instance_type="strike")
            logger.info("Finished run")
            break

        current_sleeptime -= SLEEPTIME
        logger.info(f"Run {run_count} done")

        run_count += 1


if __name__ == "__main__":
    y, m, d = 2026, 2, 19
    itype_groups = ["raid", "strike"]
    processing_type = "local"

    # Process logs
    # run_log_processing(y=y, m=m, d=d, itype_groups=itype_groups)

    # Just update message:
    # icgi = InstanceClearGroupInteraction.create_from_date(y=y, m=m, d=d, itype_group=itype_groups[0])
    # icgi.send_discord_message()

# %%
