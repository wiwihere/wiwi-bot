# %%
import datetime
import os
import time
from itertools import chain
from pathlib import Path

import scripts.leaderboards as leaderboards
from bot_settings import settings
from django.core.management.base import BaseCommand
from scripts.ei_parser import EI_PARSER_FOLDER, EliteInisghtsParser
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
    create_embeds,
    create_or_update_discord_message,
)
from scripts.log_uploader import DpsLogInteraction, LogUploader


class Command(BaseCommand):
    help = "Update leaderboards on discord"

    def add_arguments(self, parser):
        parser.add_argument("--y", type=int, nargs="?", default=None)
        parser.add_argument("--m", type=int, nargs="?", default=None)
        parser.add_argument("--d", type=int, nargs="?", default=None)
        parser.add_argument("--itype_groups", nargs="*")  # default doesnt work wtih nargs="*"

    def handle(self, *args, **options):
        y = options["y"]
        m = options["m"]
        d = options["d"]

        if not options["itype_groups"]:
            options["itype_groups"] = ["raid", "strike", "fractal"]
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
        log_paths_local_done = []  # make sure we process log locally first.
        run_count = 0
        SLEEPTIME = 30
        MAXSLEEPTIME = 60 * SLEEPTIME  # Number of seconds without a log until we stop looking.
        current_sleeptime = MAXSLEEPTIME

        # Initialize local parser
        ei_parser = EliteInisghtsParser()
        ei_parser.make_settings(out_dir=EI_PARSER_FOLDER.joinpath(zfill_y_m_d(y, m, d)), create_html=False)

        while True:
            icgi = None

            for processing_type in ["local", "upload"] + ["local"] * 9:
                # Find logs in directory
                log_paths = list(chain(*(find_log_by_date(log_dir=log_dir, y=y, m=m, d=d) for log_dir in log_dirs)))
                log_paths = sorted(log_paths, key=os.path.getmtime)

                # check a different set when local or uploading.
                if processing_type == "local":
                    log_paths_check = log_paths_local_done
                elif processing_type == "upload":
                    log_paths_check = log_paths_done

                log_paths_loop = sorted(set(log_paths).difference(set(log_paths_check)), key=os.path.getmtime)
                # Process each log
                for idx, log_path in enumerate(log_paths_loop):
                    # Skip upload if log is not in itype_group
                    try:
                        if itype_groups is not None:
                            boss_name = str(log_path).split("arcdps.cbtlogs")[1].split("\\")[1]
                            if boss_name not in folder_names:
                                print(f"Skipped {log_path}")
                                log_paths_done.append(log_path)
                                continue
                    except IndexError as e:
                        print("Failed to find bossname, will use log.")
                        pass

                    if processing_type == "local":
                        # Local processing
                        parsed_path = ei_parser.parse_log(evtc_path=log_path)
                        dli = DpsLogInteraction.from_local_ei_parser(log_path=log_path, parsed_path=parsed_path)
                        uploaded_log = dli.dpslog
                    elif processing_type == "upload":
                        if log_path in log_paths_local_done:  # Log must be parsed locally before uploading
                            # Upload log
                            log_upload = LogUploader.from_path(log_path, only_url=True)
                            uploaded_log = log_upload.run()
                        else:
                            uploaded_log = False

                    # Create ICGI and update discord message
                    fractal_success = False

                    if uploaded_log is not False:
                        if processing_type == "local":
                            log_paths_local_done.append(log_path)
                            if uploaded_log.url != "":
                                log_paths_done.append(log_path)

                        if processing_type == "upload":
                            log_paths_done.append(log_path)

                        if (
                            fractal_success is True
                            and uploaded_log.encounter.instance.instance_group.name == "fractal"
                        ):
                            continue

                        self = icgi = InstanceClearGroupInteraction.create_from_date(
                            y=y, m=m, d=d, itype_group=uploaded_log.encounter.instance.instance_group.name
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

                            # Update discord, only do it on the last log, so we dont spam the discord api too often.
                            if idx == len(log_paths_loop) - 1:
                                icgi.send_discord_message()

                            if icgi.iclear_group.success:
                                if icgi.iclear_group.type == "fractal":
                                    leaderboards.create_leaderboard(itype="fractal")
                                    fractal_success = True

                    current_sleeptime = MAXSLEEPTIME
                if processing_type == "local":
                    time.sleep(SLEEPTIME / 10)

            if (current_sleeptime < 0) or ((y, m, d) != today_y_m_d()):
                leaderboards.create_leaderboard(itype="fractal")
                leaderboards.create_leaderboard(itype="raid")
                leaderboards.create_leaderboard(itype="strike")
                print("Finished run")
                break

            current_sleeptime -= SLEEPTIME
            print(f"Run {run_count} done")

            run_count += 1
