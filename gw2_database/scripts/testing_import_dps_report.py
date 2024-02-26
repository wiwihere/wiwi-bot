# %%
"""
TODO list
- Change day end to reset time.

Multiple runs on same day/week?
"""

import datetime
import os
import time
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

import discord
import numpy as np
import requests
from dateutil.parser import parse
from discord import SyncWebhook
from django.db.models import Q

if __name__ == "__main__":
    from django_for_jupyter import init_django_from_commands

    init_django_from_commands("gw2_database")
import importlib

import log_uploader
from bot_settings import settings
from gw2_logs.models import DpsLog, Emoji, Encounter, Instance, InstanceClear, InstanceClearGroup, Player
from log_helpers import (
    EMBED_COLOR,
    ITYPE_GROUPS,
    RANK_EMOTES,
    WIPE_EMOTES,
    create_discord_time,
    create_unix_time,
    find_log_by_date,
    get_duration_str,
    get_emboldened_wing,
    get_rank_emote,
    today_y_m_d,
    zfill_y_m_d,
)
from log_instance_interaction import InstanceClearGroupInteraction
from log_uploader import LogUploader
from scripts import leaderboards

importlib.reload(log_uploader)


# %%


y, m, d = today_y_m_d()
y, m, d = 2024, 2, 22

if True:
    print(f"Starting log import for {zfill_y_m_d(y,m,d)}")

    # y, m, d = 2023, 12, 11
    if True:
        log_dir1 = Path(settings.DPS_LOGS_DIR)
        log_dir2 = Path(settings.ONEDRIVE_LOGS_DIR)
        log_dirs = [log_dir1, log_dir2]

        log_paths_done = []
        run_count = 0
        MAXSLEEPTIME = 60 * 30  # Number of seconds without a log until we stop looking.
        SLEEPTIME = 30
        current_sleeptime = MAXSLEEPTIME
        if True:
            print(f"Run {run_count}")
            # WEBHOOK_BOT_CHANNEL_STRIKE='https://discord.com/api/webhooks/1210730645953974312/stSp-bvSQsCu5_ZOSWmuVIG47yXMf3VGb8-Asi7oxFKbRd0HaPVa7sgUfNf3fX1a4ebo'

            icgi = None

            # Find logs in directory
            log_paths = list(chain(*(find_log_by_date(log_dir=log_dir, y=y, m=m, d=d) for log_dir in log_dirs)))
            log_paths = sorted(log_paths, key=os.path.getmtime)

            # Process each log
            success = {"raid": False, "strike": False, "fractal": False}

            for log_path in sorted(set(log_paths).difference(set(log_paths_done)), key=os.path.getmtime):
                log_upload = LogUploader.from_path(log_path)

                upload_success = log_upload.run()

                # instance clear group interaction 's
                icgi = None
                if upload_success is not False:
                    log_paths_done.append(log_path)

                    log_itype = log_upload.log.encounter.instance.type

                    if log_itype in ITYPE_GROUPS:
                        if not success[log_itype]:
                            self = icgi = InstanceClearGroupInteraction.create_from_date(
                                y=y, m=m, d=d, itype_group=log_itype
                            )

                    if icgi is not None:
                        titles, descriptions = icgi.create_message()
                        embeds = icgi.create_embeds(titles, descriptions)

                        icgi.create_or_update_discord_message(embeds=embeds)

                        if icgi.iclear_group.success:
                            success[log_itype] = True
                            if icgi.iclear_group.type == "fractal":
                                # leaderboards.create_leaderboard(itype="fractal")
                                pass

            # Reset sleep timer
            current_sleeptime = MAXSLEEPTIME

            # %%
            # Stop when its not today, not expecting more logs anyway.
            # Or stop when more than MAXSLEEPTIME no logs.
            if (current_sleeptime < 0) or ((y, m, d) != today_y_m_d()):
                leaderboards.create_leaderboard(itype="raid")
                leaderboards.create_leaderboard(itype="strike")
                leaderboards.create_leaderboard(itype="fractal")
                print("Finished run")
                # return
            current_sleeptime -= SLEEPTIME
            time.sleep(SLEEPTIME)
            run_count += 1

            # break

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

es = Emoji.objects.filter(type="other")
for e in es:
    if e.png_name is None:
        e.png_name = e.name.replace(" ", "_").lower()
        e.save()


# %%
if True:
    if True:
        self.all_logs = list(chain(*[i.dps_logs.order_by("start_time") for i in self.clears_by_date]))

        instance_types = np.unique([i.instance.type for i in self.clears_by_date])

        descriptions = {}
        titles = {}

        # Put raid, strike, fractal in separate embeds.
        for instance_type in instance_types:
            core_emote = Emoji.objects.get(name="core").discord_tag
            pug_emote = Emoji.objects.get(name="pug").discord_tag
            try:
                core_count = int(np.median([log.core_player_count for log in self.all_logs]))
                pug_count = int(np.median([log.player_count for log in self.all_logs])) - core_count
            except TypeError:
                core_count = 0
                pug_count = 0

            # Nina's space, add space after 5 ducks for better readability.
            pug_split_str = f"{core_emote*core_count}{pug_emote*pug_count}".split(">")
            pug_split_str[5] = f" {pug_split_str[5]}"  # empty str here:`⠀`
            pug_str = ">".join(pug_split_str)

            # title description with start - end time and colored ducks for core/pugs
            description = f"""{create_discord_time(self.all_logs[0].start_time)} - \
{create_discord_time(self.all_logs[-1].start_time+self.all_logs[-1].duration)} \
\n{pug_str}\n
"""
            # Add total instance group time if all bosses finished.
            # Loop through both the
            if instance_type not in titles:
                titles[instance_type] = {"main": ""}

            for icg in set([self.iclear_group] + list(self.iclear_group.discord_message.instance_clear_group.all())):
                title = self.iclear_group.pretty_time
                if icg.success:
                    # Get rank compared to all cleared instancecleargroups
                    group = list(
                        InstanceClearGroup.objects.filter(success=True, type=icg.type)
                        .filter(
                            Q(start_time__gte=icg.start_time - datetime.timedelta(days=9999))
                            & Q(start_time__lte=icg.start_time)
                        )
                        .order_by("duration")
                    )
                    rank_str = get_rank_emote(
                        indiv=icg,
                        group=group,
                        core_minimum=settings.CORE_MINIMUM[icg.type],
                    )

                    duration_str = get_duration_str(icg.duration.seconds)
                    title += f"⠀⠀⠀⠀{rank_str} **{duration_str}** {rank_str} \n"

                titles[icg.type] = {}
                titles[icg.type]["main"] = title
            descriptions[instance_type] = {"main": description}

titles
