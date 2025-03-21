# %%
import logging
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

import pandas as pd
from django.conf import settings

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)

from scripts.log_helpers import zfill_y_m_d

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
            self.boss_name = str(self.path).split("arcdps.cbtlogs")[1].split("\\")[1]
        except IndexError as e:
            logger.info("Failed to find bossname, will use log.")
            self.boss_name = None

        self._path_short = None

    @property
    def path_short(self) -> str:
        """Short name of the log file. Short name is the name without the extension."""
        if self._path_short is None:
            try:
                parents = 2
                parents = min(len(self.path.parts) - 2, parents)  # avoids index-error
                self._path_short = self.path.as_posix().split(self.path.parents[parents].as_posix(), maxsplit=1)[-1]
            except Exception as e:
                logger.warning("Could not get short name of %s", self.path)
                self._path_short = self.path
        return self._path_short

    def mark_local_processed(self):
        """Mark the log as processed locally."""
        logger.debug(f"Marking {self.path_short} as processed locally.")
        self.local_processed = True

    def mark_upload_processed(self):
        """Mark the log as processed externally on dps.report."""
        logger.debug(f"Marking {self.path_short} as processed externally on dps.report.")
        self.upload_processed = True


@dataclass
class LogPathsDate:
    y: int
    m: int
    d: int
    log_search_dirs: list[Path] | None = None
    allowed_folder_names: list[str] | None = None
    """This class finds logs by date and returns the paths to them as a dataframe.
    
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
    update_available_logs()
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
                raise ValueError(f"Log directory {dir} does not exist. Check your .env")

    def _to_dataframe(self) -> pd.DataFrame:
        """Convert the logs to a pandas DataFrame.
        used by self.update_available_logs to return a df
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

    def update_available_logs(self) -> pd.DataFrame:
        """Find all log files on a specific date.
        Returns sorted list on maketime
        """

        log_paths = list(
            chain(*(folder.rglob(f"{zfill_y_m_d(self.y, self.m, self.d)}*.zevtc") for folder in self.log_search_dirs))
        )

        for log in log_paths:
            logfile = LogFile(log)
            if logfile.id in self.logs:
                continue

            # Check if the log file is allowed to be processedd
            if self.allowed_folder_names is not None:
                if logfile.boss_name is not None:
                    if logfile.boss_name not in self.allowed_folder_names:
                        logger.info(f"Skipped {logfile.path_short} because it is not in the allowed_folder_names")
                        logfile.local_processed = True
                        logfile.upload_processed = True

            self.logs[logfile.id] = logfile

        return self._to_dataframe()


# %%
if __name__ == "__main__":
    y, m, d = 2025, 1, 23
    log_dirs = [settings.DPS_LOGS_DIR]

    self = logpaths = LogPathsDate(y, m, d, log_dirs)
    self.get_logs()
    df = self.to_dataframe()

    for log_row in df.where(~df["local_processed"]).itertuples():
        log = log_row.log

# %%
