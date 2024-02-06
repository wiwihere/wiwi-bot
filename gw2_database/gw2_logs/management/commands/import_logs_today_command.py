# %%
import os
import time
from itertools import chain
from pathlib import Path

import scripts.leaderboards as leaderboards
from bot_settings import settings
from django.core.management.base import BaseCommand
from scripts.log_helpers import (
    find_log_by_date,
    today_y_m_d,
    zfill_y_m_d,
)
from scripts.log_instance_interaction import InstanceClearGroupInteraction
from scripts.log_uploader import LogUploader


class Command(BaseCommand):
    help = "Update leaderboards on discord"

    def add_arguments(self, parser):
        parser.add_argument("y", type=int, nargs="?", default=None)
        parser.add_argument("m", type=int, nargs="?", default=None)
        parser.add_argument("d", type=int, nargs="?", default=None)

    def handle(self, *args, **options):
        y = options["y"]
        m = options["m"]
        d = options["d"]
        if y is None:
            y, m, d = today_y_m_d()

        print(f"Starting log import for {zfill_y_m_d(y,m,d)}")

        # y, m, d = 2023, 12, 11

        log_dir1 = Path(settings.DPS_LOGS_DIR)
        log_dir2 = Path(settings.ONEDRIVE_LOGS_DIR)
        log_dirs = [log_dir1, log_dir2]

        log_paths_done = []
        run_count = 0
        MAXSLEEPTIME = 60 * 30  # Number of seconds without a log until we stop looking.
        SLEEPTIME = 30
        current_sleeptime = MAXSLEEPTIME
        while True:
            print(f"Run {run_count}")

            icgi = None

            # Find logs in directory
            log_paths = list(chain(*(find_log_by_date(log_dir=log_dir, y=y, m=m, d=d) for log_dir in log_dirs)))
            log_paths = sorted(log_paths, key=os.path.getmtime)

            # Process each log
            raid_success = False
            fractal_success = False

            for log_path in sorted(set(log_paths).difference(set(log_paths_done)), key=os.path.getmtime):
                print(log_path)
                log_upload = LogUploader.from_path(log_path)

                upload_success = log_upload.run()
                if upload_success is not False:
                    log_paths_done.append(log_path)

                    if not raid_success:
                        self = icgi_raid = InstanceClearGroupInteraction.create_from_date(
                            y=y, m=m, d=d, itype_group="raid"
                        )
                    else:
                        icgi_raid = None
                    if not fractal_success:
                        self = icgi_fractal = InstanceClearGroupInteraction.create_from_date(
                            y=y, m=m, d=d, itype_group="fractal"
                        )
                    else:
                        icgi_fractal = None

                for icgi in [icgi_raid, icgi_fractal]:
                    if icgi is not None:
                        titles, descriptions = icgi.create_message()
                        embeds = icgi.create_embeds(titles, descriptions)

                        icgi.create_or_update_discord_message(embeds=embeds)

                        if icgi.iclear_group.success:
                            if icgi.iclear_group.type == "fractal":
                                leaderboards.create_leaderboard(itype="fractal")
                                fractal_success = True

                # Reset sleep timer
                current_sleeptime = MAXSLEEPTIME

            # Stop when its not today, not expecting more logs anyway.
            # Or stop when more than MAXSLEEPTIME no logs.
            if (current_sleeptime < 0) or ((y, m, d) != today_y_m_d()):
                leaderboards.create_leaderboard(itype="fractal")
                leaderboards.create_leaderboard(itype="raid")
                leaderboards.create_leaderboard(itype="strike")
                print("Finished run")
                return
            current_sleeptime -= SLEEPTIME
            time.sleep(SLEEPTIME)
            run_count += 1
