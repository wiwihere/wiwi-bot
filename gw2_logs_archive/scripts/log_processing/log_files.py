# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging
import os
from dataclasses import dataclass
from functools import cached_property
from itertools import chain
from pathlib import Path

import pandas as pd
from django.conf import settings
from scripts.log_helpers import get_log_path_view, zfill_y_m_d

logger = logging.getLogger(__name__)


# %%
@dataclass
class LogFile:
    """Store information about a log file.
    During processing the local_processed and upload_processed bools
    can be updated to reflect if the file has been processed locally or uploaded.
    The mtime is used for sorting files by modification time.
    """

    path: Path
    local_processed: bool = False
    upload_processed: bool = False

    def __post_init__(self):
        self.mtime = self.path.stat().st_mtime

        # Id cant be just the name because it can be found in multiple places.
        if self.path.parent == settings.EXTRA_LOGS_DIR:
            self.id = "extra" + self.path.stem
        else:
            self.id = self.path.stem

        # Try to find the boss name of the log file. If not possible, we need to parse it first.
        try:
            # Its the first folder inside arcdps.cbtlogs
            self.boss_name = str(self.path).split("arcdps.cbtlogs")[1].split(os.sep)[1]
        except IndexError as e:
            logger.info("Failed to find bossname, will use log.")
            self.boss_name = None

        parts = self.path.parts
        if "arcdps.cbtlogs" in parts:
            idx = parts.index("arcdps.cbtlogs")
            self.boss_name = parts[idx + 1] if len(parts) > idx + 1 else None
        else:
            self.boss_name = None

        self._path_short = None

    @cached_property
    def path_short(self) -> str:
        """Short name of the log file. Short name is the name without the extension."""
        return get_log_path_view(self.path)

    def mark_local_processed(self):
        """Mark the log as processed locally."""
        logger.debug(f"{self.path_short}: Marking as processed locally.")
        self.local_processed = True

    def mark_upload_processed(self):
        """Mark the log as processed externally on dps.report."""
        logger.debug(f"{self.path_short}: Marking as processed externally on dps.report.")
        self.upload_processed = True


@dataclass
class LogFilesDate:
    y: int
    m: int
    d: int
    log_search_dirs: list[Path] | None = None
    allowed_folder_names: list[str] | None = None
    """This class finds logs by date and tracks them in the internal state self.logs 
    It returns the paths to the logs as a dataframe.

    Parameters
    ----------
    y (int): The year of the date.
    m (int): The month of the date.
    d (int): The day of the date.
    log_search_dirs : list[Path]), Defaults to None.
        A list of directories in which to search for logs. When None is passed,
        the directories from the .env; DPS_LOGS_DIR and EXTRA_LOGS_DIR will be used.
    allowed_folder_names : list[str]): Defaults to None.
        A list of allowed folder names, can be retrieved with create_folder_names
        to filter the logs. For instance, the processing of golem logs might not be
        required.

    Methods
    -------
    refresh_and_get_logs()
        Finds the currently available logs by date and returns a dataframe.
    """

    def __post_init__(self):
        if self.log_search_dirs is None:
            log_search_dir1 = settings.DPS_LOGS_DIR
            log_search_dir2 = settings.EXTRA_LOGS_DIR

            self.log_search_dirs = [dir for dir in [log_search_dir1, log_search_dir2] if dir is not None]

        self._verify_log_dirs()

        self.logs = {}

    def _verify_log_dirs(self):
        """Check if all log directories exist"""

        for folder in self.log_search_dirs:
            if not folder.exists():
                raise ValueError(f"Log directory {folder} does not exist. Check your .env")

    def _to_dataframe(self) -> pd.DataFrame:
        """Convert the logs in self.logs to a pandas DataFrame.
        used by self.refresh_and_get_logs to return a df
        """
        data = [
            {
                "id": log.id,
                "boss_name": log.boss_name,  # Just for inspection
                "local_processed": log.local_processed,
                "upload_processed": log.upload_processed,
                "path": log.path,
                "mtime": log.mtime,  # For sorting
                "log": log,
            }
            for log in self.logs.values()
        ]
        df = pd.DataFrame(data)
        if df.empty:
            df = pd.DataFrame(
                columns=["id", "boss_name", "local_processed", "upload_processed", "path", "mtime", "log"]
            )
        df.sort_values(by="mtime", inplace=True)
        df.reset_index(inplace=True, drop=True)
        return df

    def refresh_and_get_logs(self) -> pd.DataFrame:
        """Find all log files on a specific date.
        Mutates internal state: adds newly discovered logs to self.logs.
        Returns a DataFrame snapshot of the current state.
        """

        log_paths = list(
            chain(*(folder.rglob(f"{zfill_y_m_d(self.y, self.m, self.d)}*.zevtc") for folder in self.log_search_dirs))
        )

        for log in log_paths:
            logfile = LogFile(log)
            if logfile.id in self.logs:
                continue

            # Check if the log file is allowed to be processed
            if self.allowed_folder_names is not None:
                if logfile.boss_name is not None:
                    if logfile.boss_name not in self.allowed_folder_names:
                        logger.info(f"{logfile.path_short}: Skipped because it is not in the allowed_folder_names")
                        logfile.mark_local_processed()
                        logfile.mark_upload_processed()

            self.logs[logfile.id] = logfile

        return self._to_dataframe()


# %%
if __name__ == "__main__":
    y, m, d = 2025, 1, 23
    log_dirs = [settings.DPS_LOGS_DIR]

    self = logpaths = LogFilesDate(y, m, d, log_dirs)
    self.refresh_and_get_logs()
    df = self._to_dataframe()

    for log_row in df.where(~df["local_processed"]).itertuples():
        log = log_row.log

# %%
