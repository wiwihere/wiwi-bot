# %%
import logging
import os
import time
from pathlib import Path
from typing import Literal

from django.conf import settings
from django.core.management.base import BaseCommand

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)

import scripts.leaderboards as leaderboards
from gw2_logs.models import DpsLog
from scripts.ei_parser import EliteInsightsParser
from scripts.helpers.local_folders import LogFile, LogPathsDate
from scripts.log_helpers import (
    ITYPE_GROUPS,
    create_folder_names,
    today_y_m_d,
    zfill_y_m_d,
)
from scripts.log_instance_interaction import (
    InstanceClearGroup,
    InstanceClearGroupInteraction,
)
from scripts.log_uploader import DpsLogInteraction, LogUploader

logger = logging.getLogger(__name__)

# %%


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
        SLEEPTIME = 30
        MAXSLEEPTIME = 60 * SLEEPTIME  # Number of seconds without a log until we stop looking.
        current_sleeptime = MAXSLEEPTIME

        # Initialize local parser
        ei_parser = EliteInsightsParser()
        ei_parser.create_settings(
            out_dir=settings.EI_PARSED_LOGS_DIR.joinpath(zfill_y_m_d(y, m, d)), create_html=False
        )

        log_paths = LogPathsDate(y=y, m=m, d=d, allowed_folder_names=allowed_folder_names)

        def parse_or_upload_log(
            logfile: LogFile,
            processing_type: Literal["local", "upload"],
            ei_parser: EliteInsightsParser,
        ) -> DpsLog | None:
            """Proces a single log

            Parameters
            ----------
            log : LogFile
                The log class that tracks the processing and hold the path to the logfile
            processing_type : Literal["local", "upload"]
                local -> proces log locally with the EliteInsightsParser
                upload -> proces log externally on dps.report
            ei_parser : EliteInsightsParser
            """
            log_path = logfile.path
            # 2. Parse locally with EI
            if processing_type == "local":
                parsed_path = ei_parser.parse_log(evtc_path=log_path)
                dli = DpsLogInteraction.from_local_ei_parser(log_path=log_path, parsed_path=parsed_path)
                if dli is False:
                    parsed_log = None
                else:
                    parsed_log = dli.dpslog

            # 3. Upload to dps.report
            elif processing_type == "upload":
                if logfile.local_processed:  # Log must be parsed locally before uploading
                    # Upload log
                    log_upload = LogUploader.from_path(log_path, only_url=True)
                    parsed_log = log_upload.run()
                else:
                    parsed_log = None

            return parsed_log

        def process_logs_once(
            *,
            processing_type: Literal["local", "upload"],
            log_paths: LogPathsDate,
            ei_parser: EliteInsightsParser,
            y: int,
            m: int,
            d: int,
            current_sleeptime: int,
        ) -> bool:
            # 1. Find unprocessed logs for date
            logs_df = log_paths.update_available_logs()
            loop_df = logs_df[~logs_df[f"{processing_type}_processed"]]

            # Process each log
            for idx, row in enumerate(loop_df.itertuples()):
                logfile: LogFile = row.log

                parsed_log = parse_or_upload_log(logfile=logfile, processing_type=processing_type, ei_parser=ei_parser)

                # 4. Create/update InstanceClearGroup
                fractal_success = False

                if parsed_log is None:
                    if processing_type == "local":
                        logger.warning(
                            f"Parsing didn't work, too short log maybe. {logfile.path}. Skipping all further processing."
                        )
                        logfile.mark_local_processed()
                        logfile.mark_upload_processed()

                if parsed_log is not None:
                    if processing_type == "local":
                        logfile.mark_local_processed()
                        if parsed_log.url != "":
                            logfile.mark_upload_processed()

                    if processing_type == "upload":
                        logfile.mark_upload_processed()

                    if fractal_success is True and parsed_log.encounter.instance.instance_group.name == "fractal":
                        continue

                    icgi = InstanceClearGroupInteraction.create_from_date(
                        y=y, m=m, d=d, itype_group=parsed_log.encounter.instance.instance_group.name
                    )

                    # 5. Build and send Discord message
                    if icgi is not None:
                        icgi.sync_discord_message_id()

                        # Update discord, only do it on the last log, so we dont spam the discord api too often.
                        if idx == len(loop_df) - 1:
                            icgi.send_discord_message()

                        # 6. Update leaderboards
                        if icgi.iclear_group.success:
                            if icgi.iclear_group.type == "fractal":
                                leaderboards.create_leaderboard(itype="fractal")
                                fractal_success = True

                    current_sleeptime = MAXSLEEPTIME
            return log_paths, current_sleeptime

        # Flow start
        while True:
            for processing_type in ["local", "upload"] + ["local"] * 9:
                # FIXME log_paths currently updates log_paths.logs this hidden state needs to be kept up to date
                log_paths, current_sleeptime = process_logs_once(
                    processing_type=processing_type,
                    log_paths=log_paths,
                    ei_parser=ei_parser,
                    y=y,
                    m=m,
                    d=d,
                    current_sleeptime=current_sleeptime,
                )

                if processing_type == "local":
                    time.sleep(SLEEPTIME / 10)

            # 6. Update leaderboards and exit
            # Only update when there hasnt been a new log parsed for the duration of sleeptime.
            if (current_sleeptime < 0) or ((y, m, d) != today_y_m_d()):
                logger.info("Updating leaderboards")
                leaderboards.create_leaderboard(itype="fractal")
                leaderboards.create_leaderboard(itype="raid")
                leaderboards.create_leaderboard(itype="strike")
                logger.info("Finished run")
                break

            current_sleeptime -= SLEEPTIME
            logger.info(f"Run {run_count} done")

            run_count += 1


if __name__ == "__main__":
    options = {}
    options["y"] = 2026
    options["m"] = 1
    options["d"] = 19
    options["itype_groups"] = False
