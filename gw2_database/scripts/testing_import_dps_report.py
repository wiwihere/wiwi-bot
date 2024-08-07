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
import os
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


y, m, d = today_y_m_d()
y, m, d = 2024, 7, 29
itype_groups = ["raid", "strike", "fractal"]

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
    run_count = 0
    SLEEPTIME = 30
    MAXSLEEPTIME = 60 * SLEEPTIME  # Number of seconds without a log until we stop looking.
    current_sleeptime = MAXSLEEPTIME

    # Initialize local parser
    ei_parser = EliteInisghtsParser()
    ei_parser.make_settings(out_dir=EI_PARSER_FOLDER.joinpath(zfill_y_m_d(y, m, d)), create_html=False)

    if True:
        icgi = None

        # Find logs in directory
        log_paths = list(chain(*(find_log_by_date(log_dir=log_dir, y=y, m=m, d=d) for log_dir in log_dirs)))
        log_paths = sorted(log_paths, key=os.path.getmtime)

        # Process each log

        for processing_type in ["local", "upload"]:
            print(processing_type)

            create_message = False

            for log_path in sorted(set(log_paths).difference(set(log_paths_done)), key=os.path.getmtime):
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
                    # Upload log
                    log_upload = LogUploader.from_path(log_path)
                    uploaded_log = log_upload.run()

                # Create ICGI and update discord message
                fractal_success = False

                if uploaded_log is not False:
                    if processing_type == "upload":
                        log_paths_done.append(log_path)

                    # if fractal_success is True and uploaded_log.encounter.instance.type == "fractal":
                    #     continue  #TODO uncomment

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
                        grp_lst = sorted(set(grp_lst), key=lambda x: x.start_time)

                        # combine embeds
                        embeds = {}
                        for icg in grp_lst:
                            icgi = InstanceClearGroupInteraction.from_name(icg.name)

                            titles, descriptions = icgi.create_message()
                            icg_embeds = create_embeds(titles, descriptions)
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


# %%

DpsLogInteraction.from_local_ei_parser(log_path=log_path, parsed_path=log)

# r2 = EliteInisghtsParser.load_json_gz(js_path=log)

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
for icg in InstanceClearGroup.objects.all():
    ymd = icg.name.split("__")[-1]
    y, m, d = ymd[:4], ymd[4:6], ymd[6:8]
    # y,m,d= 2024,2,6

    icgi = InstanceClearGroupInteraction.create_from_date(y=y, m=m, d=d, itype_group=icg.type)

    # icgi = InstanceClearGroupInteraction.from_name(icg.name)
    titles, descriptions = icgi.create_message()
    embeds = icgi.create_embeds(titles, descriptions)

    icgi.create_or_update_discord_message(embeds=embeds)
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
