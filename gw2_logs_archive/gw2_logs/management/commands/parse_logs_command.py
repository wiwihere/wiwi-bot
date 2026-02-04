# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand
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


class Command(BaseCommand):
    """
    FLOW:
    1. Find unprocessed logs for date
    2. Parse locally with EI
    3. Upload to dps.report
    4. Create/update InstanceClearGroup
    5. Build and send Discord message
    6. Update leaderboards and exit
    """

    help = "Parse logs and create message on discord"

    def add_arguments(self, parser):
        parser.add_argument("--y", type=int, nargs="?", default=None)
        parser.add_argument("--m", type=int, nargs="?", default=None)
        parser.add_argument("--d", type=int, nargs="?", default=None)
        parser.add_argument("--itype_groups", nargs="*")  # default doesnt work with nargs="*"

    def handle(self, *args, **options):
        # Initialize variables
        y = options["y"]
        m = options["m"]
        d = options["d"]

        if not options["itype_groups"]:
            options["itype_groups"] = ["raid", "strike", "fractal"]
        itype_groups = options["itype_groups"]

        if y is None:
            y, m, d = today_y_m_d()

        logger.info(f"Starting log import for {zfill_y_m_d(y, m, d)}")
        logger.info(f"Selected instance types: {itype_groups}")
        # y, m, d = 2023, 12, 11

        # possible folder names for selected itype_groups
        # TODO move to class
        allowed_folder_names = create_folder_names(itype_groups=itype_groups)

        run_count = 0
        current_sleeptime = MAXSLEEPTIME

        # Initialize local parser
        ei_parser = EliteInsightsParser()
        ei_parser.create_settings(
            out_dir=settings.EI_PARSED_LOGS_DIR.joinpath(zfill_y_m_d(y, m, d)), create_html=False
        )

        log_files_date_cls = LogFilesDate(y=y, m=m, d=d, allowed_folder_names=allowed_folder_names)

        # Flow start
        PROCESSING_SEQUENCE = ["local", "upload"] + ["local"] * 9

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

                    # 5. Build and send Discord message
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
    options = {}
    options["y"] = 2026
    options["m"] = 2
    options["d"] = 4
    options["itype_groups"] = False

# %%
