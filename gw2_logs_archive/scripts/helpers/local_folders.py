# %%
import datetime
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)


@dataclass
class LogPaths:
    y: int
    m: int
    d: int

    def __init__(self, y, m, d) -> None:
        self.log_dirs = [Path(settings.LOG_DIR), Path(settings.LOG_DIR + "/2019")]

    def get_logs(log_dirs) -> list[Path]:
        """Find all log files on a specific date.
        Returns sorted list on maketime
        """
        # return log_dir.rglob(f"{zfill_y_m_d(y,m,d)}*.zevtc")
        log_paths = list(chain(*(log_dir.rglob(f"{zfill_y_m_d(y, m, d)}*.zevtc") for log_dir in log_dirs)))
        return sorted(log_paths, key=os.path.getmtime)
