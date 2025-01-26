# %%
import datetime
import logging
import os
import time
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

from django.conf import settings

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)

from scripts.log_helpers import zfill_y_m_d


@dataclass
class LogPathsDate:
    y: int
    m: int
    d: int
    log_dirs: list[Path] | None = None

    def __post_init__(self):
        if self.log_dirs is None:
            log_dir1 = settings.DPS_LOGS_DIR
            log_dir2 = settings.EXTRA_LOGS_DIR
            self.log_dirs = [log_dir1, log_dir2]

        # Track finished logs here
        self.done = []
        self.local_done = []

    def get_logs(self) -> list[Path]:
        """Find all log files on a specific date.
        Returns sorted list on maketime
        """

        log_paths = list(
            chain(*(log_dir.rglob(f"{zfill_y_m_d(self.y, self.m, self.d)}*.zevtc") for log_dir in self.log_dirs))
        )
        return sorted(log_paths, key=os.path.getmtime)


# %%
if __name__ == "__main__":
    y, m, d = 2024, 11, 20
    log_dirs = [settings.DPS_LOGS_DIR]
