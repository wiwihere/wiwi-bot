# %%
import logging
from dataclasses import dataclass
from typing import Literal, Tuple

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)

import scripts.leaderboards as leaderboards
from gw2_logs.models import DpsLog
from scripts.ei_parser import EliteInsightsParser
from scripts.helpers.local_folders import LogFile, LogPathsDate
from scripts.log_instance_interaction import (
    InstanceClearGroupInteraction,
)
from scripts.log_uploader import DpsLogInteraction, LogUploader

logger = logging.getLogger(__name__)


def _parse_or_upload_log(
    logfile: LogFile,
    processing_type: Literal["local", "upload"],
    ei_parser: EliteInsightsParser,
) -> DpsLog | None:
    """Parse (EliteInsights, local) or upload (dps.report, upload) a single log file depending on processing type.

    Parameters
    ----------
    log : LogFile
        The log class that tracks the processing and hold the path to the logfile
    processing_type : Literal["local", "upload"]
        local -> proces log locally with the EliteInsightsParser
        upload -> upload the log to dps.report and retrieve the result
    ei_parser : EliteInsightsParser

    Returns
    -------
    DpsLog | None
        Parsed DpsLog on success, or None if parsing/upload failed
        or the log is not eligible for the requested processing step.
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
) -> bool:
    """
    Process all unprocessed logs once for a given date and processing type.

    This function:
    - Detects unprocessed logs for the given date
    - Parses or uploads each log
    - Marks logs as processed
    - Creates or updates InstanceClearGroups
    - Syncs and optionally sends Discord messages
    - Updates leaderboards when a clear is completed

    Parameters
    ----------
    processing_type : Literal["local", "upload"]
        Which processing step to run for the logs.
    log_paths : LogPathsDate
        LogPathsDate instance managing available logs and state.
    ei_parser : EliteInsightsParser
        Configured Elite Insights parser instance.
    y, m, d : int
        Date used for InstanceClearGroup grouping.

    Returns
    -------
    bool
        True if at least one log was processed, False otherwise.
    """
    # 1. Find unprocessed logs for date
    logs_df = log_paths.update_available_logs()
    # Filter for unprocessed logs
    loop_df = logs_df[~logs_df[f"{processing_type}_processed"]]

    # Process each log
    processed_any = False
    for idx, row in enumerate(loop_df.itertuples()):
        logfile: LogFile = row.log

        parsed_log = _parse_or_upload_log(logfile=logfile, processing_type=processing_type, ei_parser=ei_parser)

        # 4. Create/update InstanceClearGroup
        fractal_success = False  # FIXME dead

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

            processed_any = True
    return processed_any
