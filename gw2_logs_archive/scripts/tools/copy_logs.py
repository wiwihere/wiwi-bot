# %%
import logging
import os
import shutil
from pathlib import Path

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)

from django.conf import settings
from scripts.log_helpers import (
    create_folder_names,
    find_log_by_date,
    today_y_m_d,
)

logger = logging.getLogger(__name__)


def copy_logs(y, m, d, itype_groups):
    """Copy logs from a date to a folder"""
    log_dir_source = Path(settings.DPS_LOGS_DIR)
    log_dir_dst = Path(settings.ONEDRIVE_LOGS_DIR)
    logger.info(f"Selected itype groups: {itype_groups}")
    logger.info(f"Src dir: {log_dir_source}")
    logger.info(f"Dst dir: {log_dir_dst}")

    # Find logs in directory
    log_paths = find_log_by_date(log_dirs=[log_dir_source], y=y, m=m, d=d)
    folder_names = create_folder_names(itype_groups=itype_groups)

    log_paths_loop = sorted(log_paths, key=os.path.getmtime)

    # Process each log
    for idx, log_path in enumerate(log_paths_loop):
        # Skip upload if log is not in itype_group
        try:
            if itype_groups not in [None, []]:
                boss_name = str(log_path).split("arcdps.cbtlogs")[1].split("\\")[1]
                if boss_name not in folder_names:
                    continue

            dst = log_dir_dst.joinpath(log_path.name)
            logger.info(f"Moved: {log_path}")
            shutil.copyfile(src=log_path, dst=dst)

        except IndexError as e:
            logger.error(e)
            pass


if __name__ == "__main__":
    y, m, d = today_y_m_d()
    # y, m, d = 2024, 7, 29
    itype_groups = ["raid", "strike", "fractal"]

    if True:
        if y is None:
            y, m, d = today_y_m_d()

    copy_logs(y, m, d, itype_groups)
