# %%
"""
TODO list
- Change day end to reset time.

Multiple runs on same day/week?
"""

import os
from itertools import chain
from pathlib import Path

if __name__ == "__main__":
    from django_for_jupyter import init_django_from_commands

    init_django_from_commands("gw2_database")
import datetime
import os
import time
from itertools import chain
from pathlib import Path

import scripts.leaderboards as leaderboards
from bot_settings import settings
from scripts import leaderboards
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

# importlib.reload(log_uploader)


# %%
# TODO do something with Ethereal Barrier (47188)
y, m, d = today_y_m_d()
# y, m, d = 2024, 11, 18
itype_groups = ["raid", "strike", "fractal"]
# itype_groups = []

if True:
    if True:
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

            # for processing_type in ["local", "upload"] + ["local"] * 9:
            for processing_type in ["upload"]:
                # Find logs in directory
                log_paths = find_log_by_date(log_dirs=log_dirs, y=y, m=m, d=d)

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
                                log_paths_local_done.append(log_path)
                                log_paths_done.append(log_path)
                                continue
                    except IndexError as e:
                        print("Failed to find bossname, will use log.")
                        pass

                    if processing_type == "local":
                        # Local processing
                        parsed_path = ei_parser.parse_log(evtc_path=log_path)
                        dli = DpsLogInteraction.from_local_ei_parser(log_path=log_path, parsed_path=parsed_path)
                        if dli is False:
                            # Parsing didnt work, too short log maybe.
                            log_paths_local_done.append(log_path)
                            log_paths_done.append(log_path)
                            continue

                        uploaded_log = dli.dpslog

                    elif processing_type == "upload":
                        if log_path not in log_paths_local_done:  # Log must be parsed locally before uploading
                            # Upload log
                            log_upload = LogUploader.from_path(log_path, only_url=False)
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

                        # if fractal_success is True and uploaded_log.encounter.instance.instance_group.name == "fractal":
                        #     continue  #TODO uncomment

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
                time.sleep(10)

            if (current_sleeptime < 0) or ((y, m, d) != today_y_m_d()):
                leaderboards.create_leaderboard(itype="fractal")
                leaderboards.create_leaderboard(itype="raid")
                leaderboards.create_leaderboard(itype="strike")
                print("Finished run")
                break

            current_sleeptime -= SLEEPTIME
            print(f"Run {run_count} done")

            run_count += 1


# %%


# %% Just update or create discord message, dont upload logs.


# y, m, d = today_y_m_d()
y, m, d = 2022, 1, 27


self = icgi = InstanceClearGroupInteraction.create_from_date(y=y, m=m, d=d)
# self = icgi = InstanceClearGroupInteraction.from_name("dummy")

titles, descriptions = icgi.create_message()
embeds = icgi.create_embeds(titles, descriptions)

# print(embeds)

# icgi.create_or_update_discord_message(embeds=embeds)
# ici = InstanceClearInteraction.from_name("w7_the_key_of_ahdashim__20231211")


# %% Update discord messages from a certain date onwards

y, m, d = 2024, 8, 22

if False:
    icgs = InstanceClearGroup.objects.filter(
        start_time__gte=datetime.datetime(year=y, month=m, day=d, tzinfo=datetime.timezone.utc)
    ).order_by("start_time")
    for icg in icgs:
        icgi = InstanceClearGroupInteraction.from_name(name=icg.name)
        icgi.send_discord_message()


# %% Manual uploads without creating discord message

# y, m, d = 2023, 12, 18

# log_dir = Path(settings.DPS_LOGS_DIR)
# log_paths = list(log_dir.rglob(f"{zfill_y_m_d(y,m,d)}*.zevtc"))

# for log_path in log_paths:
#     self = log_upload = LogUploader.from_path(log_path)
#     log_upload.run()
#     break

# log_urls = [
#     r"https://dps.report/dIVa-20231012-213625_void",
#     r"https://dps.report/bUkb-20231018-210130_void",
#     r"https://dps.report/QpUT-20231024-210315_void",
# ]
# for log_url in log_urls:
#     self = log_upload = LogUploader.from_url(log_url=log_url)
#     log_upload.run()


# %% Update all discord messages.
for icg in InstanceClearGroup.objects.all().order_by("start_time"):
    ymd = icg.name.split("__")[-1]
    y, m, d = ymd[:4], ymd[4:6], ymd[6:8]
    # y,m,d= 2024,2,6

    if icg.type in ["raid", "strike"]:
        icgi = InstanceClearGroupInteraction.create_from_date(y=y, m=m, d=d, itype_group=icg.type)

        # icgi = InstanceClearGroupInteraction.from_name(icg.name)
        # titles, descriptions = icgi.create_message()
        # embeds = icgi.create_embeds(titles, descriptions)
        if icgi:
            icgi.send_discord_message()
    # break

# %% Updating emoji ids in bulk
pngs_dir = Path(__file__).parents[1].joinpath("img", "raid")

print("Copy this into discord")
for png in pngs_dir.glob("*.png"):
    png_name = png.stem
    print(f"\:{png.stem}:")

# %%
emote_ids_raw = """paste result from discord here."""
emote_ids = {i.split(":")[1]: i.split(":")[-1].split(">")[0] for i in emote_ids_raw.split("\n")}


for png_name, png_id in emote_ids.items():
    cm = False
    if png_name.endswith("_cm"):
        png_name = png_name[:-3]
        cm = True
    e = Emoji.objects.get(png_name=png_name)

    if png_id:
        if cm:
            e.discord_id_cm = int(png_id)
        else:
            e.discord_id = int(png_id)
        print(f"Update {e.name}. CM:{cm}")

        e.save()


# %%


# %%
if True:
    if True:
        pass

# %%
import pandas as pd

log = LogUploader.from_url(log_url="https://dps.report/sGBv-20240926-211517_qpeer")
log.request_metadata(report_id=None, url=log.log_url)


log = LogUploader.from_url(log_url="https://dps.report/sGBv-20240926-211517_qpeer")
log.request_metadata(report_id=None, url=log.log_url)
