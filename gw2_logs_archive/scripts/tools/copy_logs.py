# %%
import logging
import os
import shutil

from django.conf import settings

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)

from scripts.helpers.local_folders import LogFile, LogPathsDate
from scripts.log_helpers import (
    create_folder_names,
    today_y_m_d,
)

logger = logging.getLogger(__name__)


def copy_logs(y, m, d, itype_groups):
    """Copy logs from a date to a folder"""
    log_dir_source = settings.DPS_LOGS_DIR
    log_dir_dst = settings.EXTRA_LOGS_DIR
    logger.info(f"Selected itype groups: {itype_groups}")
    logger.info(f"Src dir: {log_dir_source}")
    logger.info(f"Dst dir: {log_dir_dst}")

    # Find logs in directory
    allowed_folder_names = create_folder_names(itype_groups=itype_groups)
    log_paths = LogPathsDate(
        y=y, m=m, d=d, allowed_folder_names=allowed_folder_names, log_search_dirs=[log_dir_source]
    )

    logs_df = log_paths.update_available_logs()

    # Process each log
    for row in logs_df.itertuples():
        log: LogFile = row.log
        log_path = log.path
        # Skip upload if log is not in itype_group

        dst = log_dir_dst.joinpath(log_path.name)
        logger.info(f"Moved: {log_path}")
        shutil.copyfile(src=log_path, dst=dst)


# %%
if __name__ == "__main__":
    # y, m, d = today_y_m_d()
    y, m, d = 2025, 1, 23
    itype_groups = ["raid", "strike", "fractal"]

    if True:
        if y is None:
            y, m, d = today_y_m_d()

    copy_logs(y, m, d, itype_groups)
