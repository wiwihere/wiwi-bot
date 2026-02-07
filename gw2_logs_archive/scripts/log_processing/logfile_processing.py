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

logger = logging.getLogger(__name__)


def _process_log_local(
    log_path: Path,
    ei_parser: EliteInsightsParser,
) -> Optional[DpsLog]:
    """Parse log locally with the EliteInsightsParser and create or update DpsLog in database.

    Parameters
    ----------
    log_path : Path
        Path to the logfile
    ei_parser : EliteInsightsParser
        Initialized EliteInsightsParser instance for parsing the log
    """

    parsed_path = ei_parser.parse_log(log_path=log_path)
    if parsed_path is not None:
        detailed_parsed_log = EliteInsightsParser.load_parsed_json(parsed_path=parsed_path)
        dpslog = DpsLogService().get_update_create_from_ei_parsed_log(
            detailed_parsed_log=detailed_parsed_log, log_path=log_path
        )
    else:
        dpslog = None

    return dpslog


def _process_log_upload(
    log_path: Path,
    ei_parser: EliteInsightsParser,
) -> Optional[DpsLog]:
    """Upload log to dps.report and update the DpsLog in database.

    Parameters
    ----------
    log_path : Path
        Path to the logfile
    ei_parser : EliteInsightsParser
        Initialized EliteInsightsParser instance for parsing the log
    """
    # Upload to dps.report
    if log_path.local_processed:  # Log must be parsed locally before uploading
        parsed_path = ei_parser.find_parsed_json(log_path=log_path)
        log_upload = LogUploader(log_path=log_path, parsed_path=parsed_path, only_url=True)
        dpslog = log_upload.run()
    else:
        dpslog = None

    return dpslog


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
    processed_logs: list[DpsLog] = []
    for logfile in logfiles:
        log_path = logfile.path

        # Handle local processing
        if processing_type == "local":
            dpslog = _process_log_local(log_path=log_path, ei_parser=ei_parser)

            if dpslog is None:
                logger.warning(
                    f"Parsing didn't work, too short log maybe. {log_path}. Skipping all further processing."
                )
                logfile.mark_local_processed()
                logfile.mark_upload_processed()
            else:
                logfile.mark_local_processed()
                if dpslog.url != "":
                    logfile.mark_upload_processed()

        # Handle upload processing
        if processing_type == "upload":
            dpslog = _process_log_upload(log_path=log_path, ei_parser=ei_parser)

            if dpslog is not None:
                logfile.mark_upload_processed()

        # Add log to processed logs if it was processed in this step
        if dpslog is not None:
            processed_logs += [dpslog]
    return processed_logs


# %%
