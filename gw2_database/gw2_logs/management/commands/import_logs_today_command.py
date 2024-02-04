# %%
import os
import time
from itertools import chain
from pathlib import Path

from bot_settings import settings
from django.core.management.base import BaseCommand
from scripts import leaderboards
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
        icgi = None
        MAXSLEEPTIME = 60 * 20  # Number of seconds without a log until we stop looking.
        SLEEPTIME = 30
        current_sleeptime = MAXSLEEPTIME
        while True:
            print(f"Run {run_count}")

            # Find logs in directory
            log_paths = list(chain(*(find_log_by_date(log_dir=log_dir, y=y, m=m, d=d) for log_dir in log_dirs)))
            log_paths = sorted(log_paths, key=os.path.getmtime)

            # Process each log
            for log_path in sorted(set(log_paths).difference(set(log_paths_done)), key=os.path.getmtime):
                print(log_path)
                log_upload = LogUploader.from_path(log_path)

                success = log_upload.run()
                if success is not False:
                    log_paths_done.append(log_path)

                self = icgi = InstanceClearGroupInteraction.create_from_date(y=y, m=m, d=d)
                titles, descriptions = icgi.create_message()
                embeds = icgi.create_embeds(titles, descriptions)

                icgi.create_or_update_discord_message(embeds=embeds)
                # break

                if icgi is not None:
                    if icgi.iclear_group.success:
                        if icgi.iclear_group.type == "fractal":
                            leaderboards.create_leaderboard(itype="fractal")
                            break

                # Reset sleep timer
                current_sleeptime = MAXSLEEPTIME

            # Stop when its not today, not expecting more logs anyway.
            # Or stop when more than MAXSLEEPTIME no logs.
            if (current_sleeptime < 0) or ((y, m, d) != today_y_m_d()):
                icgi.iclear_group.type
                leaderboards.create_leaderboard(itype="raid")
                leaderboards.create_leaderboard(itype="strike")
                print("Finished run")
                break
            current_sleeptime -= SLEEPTIME

            time.sleep(SLEEPTIME)
            run_count += 1