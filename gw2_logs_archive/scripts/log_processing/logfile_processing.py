# %%
"""Logfile processing orchestration

Small orchestrator that detects unprocessed log files for a given date,
parses them locally with the Elite Insights parser, or uploads them to
dps.report. Creation and updating of database records is delegated to
`DpsLogService` so this module focuses on file-level flow and marking
processing state.
"""

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import logging
from pathlib import Path
from typing import Literal, Optional

from gw2_logs.models import DpsLog
from scripts.log_processing.ei_parser import EliteInsightsParser
from scripts.log_processing.log_files import LogFile, LogFilesDate
from scripts.log_processing.log_uploader import LogUploader
from scripts.model_interactions.dpslog_service import DpsLogService
from scripts.utilities.parsed_log import ParsedLog

logger = logging.getLogger(__name__)


def _parse_or_upload_log(
    log_path: Path,
    processing_type: Literal["local", "upload"],
    ei_parser: EliteInsightsParser,
) -> Optional[DpsLog]:
    """Parse (EliteInsights, local) or upload (dps.report, upload) a single log file depending on processing type.

    Parameters
    ----------
    log_path : Path
        Path to the logfile
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
    # Parse locally with EI
    if processing_type == "local":
        parsed_path = ei_parser.parse_log(log_path=log_path)
        # Use centralized service for creating DpsLog from EI parsed JSON
        dps_log = None
        if parsed_path is not None:
            parsed_log = ParsedLog.from_ei_parsed_path(parsed_path=parsed_path)
            dps_log = DpsLogService().get_update_create_from_ei_parsed_log(parsed_log=parsed_log, log_path=log_path)

    # Upload to dps.report
    elif processing_type == "upload":
        if log_path.local_processed:  # Log must be parsed locally before uploading
            parsed_path = ei_parser.find_parsed_json(log_path=log_path)
            log_upload = LogUploader(log_path=log_path, parsed_path=parsed_path, only_url=True)
            dps_log = log_upload.run()
        else:
            dps_log = None

    return dps_log


def process_logs_once(
    *,
    processing_type: Literal["local", "upload"],
    log_files_date_cls: LogFilesDate,
    ei_parser: EliteInsightsParser,
) -> list[DpsLog]:
    """
    Process all unprocessed logs once for a given date and processing type.

    This function:
    - Detects unprocessed logs for the given date
    - Parses or uploads each log
    - Marks logs as processed
    - Creates or updates InstanceClearGroups

    Parameters
    ----------
    processing_type : Literal["local", "upload"]
        Which processing step to run for the logs.
    log_files_date_cls : LogFilesDate
        LogPathsDate instance managing available logs and state.
    ei_parser : EliteInsightsParser
        Configured Elite Insights parser instance.

    Returns
    -------
    bool
        True if at least one log was processed, False otherwise.
    """
    # Find unprocessed logs for date
    logfiles: list[LogFile] = log_files_date_cls.get_unprocessed_logs(processing_type=processing_type)

    # Process each log
    processed_logs = []
    for logfile in logfiles:
        log_path = logfile.path
        dpslog = _parse_or_upload_log(log_path=log_path, processing_type=processing_type, ei_parser=ei_parser)

        # Mark processing status
        if dpslog is None:
            if processing_type == "local":
                logger.warning(
                    f"Parsing didn't work, too short log maybe. {log_path}. Skipping all further processing."
                )
                logfile.mark_local_processed()
                logfile.mark_upload_processed()

        if dpslog is not None:
            if processing_type == "local":
                logfile.mark_local_processed()
                if dpslog.url != "":
                    logfile.mark_upload_processed()

            if processing_type == "upload":
                logfile.mark_upload_processed()

            processed_logs += [dpslog]
    return processed_logs


# %%
