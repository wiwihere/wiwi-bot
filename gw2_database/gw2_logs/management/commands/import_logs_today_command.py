# %%
import datetime
import os
import time
from itertools import chain
from pathlib import Path

import scripts.leaderboards as leaderboards
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
from scripts.log_instance_interaction import (
    InstanceClearGroup,
    InstanceClearGroupInteraction,
    create_or_update_discord_message,
)
from scripts.log_uploader import LogUploader


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

        print(f"Starting log import for {zfill_y_m_d(y,m,d)}")
        print(f"Selected instance types: {itype_groups}")
        # y, m, d = 2023, 12, 11

        # possible folder names for selected itype_groups
        folder_names = create_folder_names(itype_groups=itype_groups)

        log_dir1 = Path(settings.DPS_LOGS_DIR)
        log_dir2 = Path(settings.ONEDRIVE_LOGS_DIR)
        log_dirs = [log_dir1, log_dir2]

        log_paths_done = []
        run_count = 0
        MAXSLEEPTIME = 60 * 30  # Number of seconds without a log until we stop looking.
        SLEEPTIME = 30
        current_sleeptime = MAXSLEEPTIME
        while True:
            icgi = None

            # Find logs in directory
            log_paths = list(chain(*(find_log_by_date(log_dir=log_dir, y=y, m=m, d=d) for log_dir in log_dirs)))
            log_paths = sorted(log_paths, key=os.path.getmtime)

            # Process each log
            for log_path in sorted(set(log_paths).difference(set(log_paths_done)), key=os.path.getmtime):
                # Skip upload if log is not in itype_group
                try:
                    if itype_groups is not None:
                        boss_name = str(log_path).split("arcdps.cbtlogs")[1].split("/")[1]
                        if boss_name not in folder_names:
                            print(f"Skipped {log_path}")
                            log_paths_done.append(log_path)
                            continue
                except IndexError:
                    pass

                # Upload log
                log_upload = LogUploader.from_path(log_path)
                uploaded_log = log_upload.run()

                # Create ICGI and update discord message
                fractal_success = False
                if uploaded_log is not False:
                    log_paths_done.append(log_path)

                    if fractal_success is True and uploaded_log.encounter.instance.type == "fractal":
                        continue

                    self = icgi = InstanceClearGroupInteraction.create_from_date(
                        y=y, m=m, d=d, itype_group=uploaded_log.encounter.instance.type
                    )
                    if icgi is not None:
                        # Set the same discord message id when strikes and raids are combined.
                        if (ITYPE_GROUPS["raid"] == ITYPE_GROUPS["strike"]) and (
                            icgi.iclear_group.type in ["raid", "strike"]
                        ):
                            if self.iclear_group.discord_message is None:
                                group_names = [
                                    "__".join([f"{j}s", self.iclear_group.name.split("__")[1]])
                                    for j in ITYPE_GROUPS["raid"]
                                ]
                                self.iclear_group.discord_message_id = (
                                    InstanceClearGroup.objects.filter(name__in=group_names)
                                    .exclude(discord_message=None)
                                    .values_list("discord_message", flat=True)
                                    .first()
                                )
                                self.iclear_group.save()

                        # Find the clear groups. e.g. [raids__20240222, strikes__20240222]
                        grp_lst = [icgi.iclear_group]
                        if icgi.iclear_group.discord_message is not None:
                            grp_lst += icgi.iclear_group.discord_message.instance_clear_group.all()
                        grp_lst = set(grp_lst)

                        # combine embeds
                        embeds = {}
                        for icg in grp_lst:
                            icgi = InstanceClearGroupInteraction.from_name(icg.name)

                            titles, descriptions = icgi.create_message()
                            icg_embeds = icgi.create_embeds(titles, descriptions)
                            embeds.update(icg_embeds)
                        embeds_mes = list(embeds.values())

                        create_or_update_discord_message(
                            group=icgi.iclear_group,
                            hook=WEBHOOKS[icgi.iclear_group.type],
                            embeds_mes=embeds_mes,
                        )

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
            print(f"Run {run_count} done")

            time.sleep(SLEEPTIME)
            run_count += 1


# %%
