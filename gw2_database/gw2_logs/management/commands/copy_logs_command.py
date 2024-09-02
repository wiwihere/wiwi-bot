# %%
import os
import shutil
from itertools import chain
from pathlib import Path

from bot_settings import settings
from django.core.management.base import BaseCommand
from scripts.log_helpers import (
    ITYPE_GROUPS,
    WEBHOOKS,
    create_folder_names,
    find_log_by_date,
    today_y_m_d,
    zfill_y_m_d,
)


class Command(BaseCommand):
    help = "Update leaderboards on discord"

    def add_arguments(self, parser):
        parser.add_argument("--y", type=int, nargs="?", default=None)
        parser.add_argument("--m", type=int, nargs="?", default=None)
        parser.add_argument("--d", type=int, nargs="?", default=None)
        parser.add_argument("--itype_groups", nargs="*", default=["raid", "strike", "fractal"])

    def handle(self, *args, **options):
        y = options["y"]
        m = options["m"]
        d = options["d"]
        itype_groups = options["itype_groups"]
        if y is None:
            y, m, d = today_y_m_d()

        log_dir_source = Path(settings.DPS_LOGS_DIR)
        log_dir_dst = Path(settings.ONEDRIVE_LOGS_DIR)

        # Find logs in directory
        log_paths = list(chain(*(find_log_by_date(log_dir=log_dir, y=y, m=m, d=d) for log_dir in [log_dir_source])))
        log_paths = sorted(log_paths, key=os.path.getmtime)

        folder_names = create_folder_names(itype_groups=itype_groups)

        log_paths_loop = sorted(log_paths, key=os.path.getmtime)

        # Process each log
        for idx, log_path in enumerate(log_paths_loop):
            # Skip upload if log is not in itype_group
            try:
                if itype_groups is not None:
                    boss_name = str(log_path).split("arcdps.cbtlogs")[1].split("\\")[1]
                    if boss_name not in folder_names:
                        continue

                dst = log_dir_dst.joinpath(log_path.name)

                shutil.copyfile(src=log_path, dst=dst)

            except IndexError as e:
                pass
