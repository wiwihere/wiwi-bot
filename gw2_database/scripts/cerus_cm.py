# %%
import datetime
from dataclasses import dataclass
from distutils.command import upload
from itertools import chain

import discord
import numpy as np
import pandas as pd
from discord import SyncWebhook
from django.db.models import Q

if __name__ == "__main__":
    from django_for_jupyter import init_django_from_commands

    init_django_from_commands("gw2_database")
import os
import time
from pathlib import Path

from bot_settings import settings
from gw2_logs.models import (
    DiscordMessage,
    DpsLog,
    Emoji,
    Encounter,
    Instance,
    InstanceClear,
    InstanceClearGroup,
    Player,
)
from scripts.log_helpers import (
    BLANK_EMOTE,
    EMBED_COLOR,
    ITYPE_GROUPS,
    RANK_EMOTES,
    RANK_EMOTES_CUPS,
    WEBHOOKS,
    WIPE_EMOTES,
    create_discord_time,
    create_folder_names,
    create_or_update_discord_message,
    find_log_by_date,
    get_duration_str,
    get_rank_emote,
    today_y_m_d,
    zfill_y_m_d,
)
from scripts.log_instance_interaction import InstanceClearGroupInteraction, create_embeds
from scripts.log_uploader import LogUploader

# %%

y, m, d = today_y_m_d()
y, m, d = 2024, 3, 16

print(f"Starting Cerus log import for {zfill_y_m_d(y,m,d)}")
# y, m, d = 2023, 12, 11

# possible folder names for selected itype_groups
folder_names = ["Cerus", 25989]

log_dir1 = Path(settings.DPS_LOGS_DIR)
log_dir2 = Path(settings.ONEDRIVE_LOGS_DIR)
log_dirs = [log_dir1, log_dir2]

log_paths_done = []
run_count = 0
MAXSLEEPTIME = 60 * 30  # Number of seconds without a log until we stop looking.
SLEEPTIME = 30
current_sleeptime = MAXSLEEPTIME
# while True:
if True:
    icgi = None

    # Find logs in directory
    log_paths = list(chain(*(find_log_by_date(log_dir=log_dir, y=y, m=m, d=d) for log_dir in log_dirs)))
    log_paths = sorted(log_paths, key=os.path.getmtime)

    # Process each log
    for log_path in sorted(set(log_paths).difference(set(log_paths_done)), key=os.path.getmtime):
        # Skip upload if log is not in itype_group
        try:
            boss_name = str(log_path).split("arcdps.cbtlogs")[1].split("\\")[1]
            if boss_name not in folder_names:
                print(f"Skipped {log_path}")
                log_paths_done.append(log_path)
                continue
        except IndexError as e:
            print("Failed to find bossname, will use log.")
            pass

        # Upload log
        log_upload = LogUploader.from_path(log_path)
        uploaded_log = log_upload.run()

        # if not uploaded_log:
        #     continue

        if uploaded_log.phasetime_str is None:
            print(f"Request detailed {uploaded_log.id}")
            data = log_upload.request_detailed_info()["phases"]
            filtered_data = [d for d in data if "Cerus Breakbar" in d["name"]]
            df = pd.DataFrame(filtered_data)
            if not df.empty:
                df["time"] = df["end"].apply(
                    lambda x: datetime.timedelta(minutes=10) - datetime.timedelta(milliseconds=x)
                )

                phasetime_lst = [
                    get_duration_str(i.astype("timedelta64[s]").astype(np.int32)) for i in df["time"].to_numpy()
                ]
            else:
                phasetime_lst = []

            while len(phasetime_lst) < 3:
                phasetime_lst.append(" -- ")

            phasetime_str = " | ".join(phasetime_lst)

            uploaded_log.phasetime_str = phasetime_str
            uploaded_log.save()

        titles = {"cerus_cm": {"main": "Sat 16 Mar 2024"}}

        cm_logs = DpsLog.objects.filter(
            encounter__name="Temple of Febe", start_time__year=y, start_time__month=m, start_time__day=d, cm=True
        ).order_by("start_time")

        health_df = pd.DataFrame(cm_logs.values_list("id", "final_health_percentage"), columns=["id", "health"])
        health_df["log"] = cm_logs
        health_df.sort_values("health", inplace=True)

        health_df.reset_index(inplace=True)
        health_df["rank"] = BLANK_EMOTE
        health_df["rank"] = "⠀⠀"
        emote_cups = pd.Series(RANK_EMOTES_CUPS.values(), name="rank")
        health_df.loc[:2, "rank"] = emote_cups

        health_df.sort_values("index", inplace=True)
        health_df.set_index(["index"], inplace=True)

        field_id = 0
        field_value = f"{Emoji.objects.get(name='Cerus').discord_tag_cm} {create_discord_time(cm_logs[0].start_time)} - {create_discord_time(list(cm_logs)[-1].start_time+list(cm_logs)[-1].duration)}\n\
<a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414> <a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414>\n"
        descriptions = {"cerus_cm": {"main": field_value}}

        titles["cerus_cm"]["field_0"] = ""
        descriptions["cerus_cm"]["field_0"] = ""

        for idx, row in health_df.iterrows():
            log = row["log"]
            if idx == 0:
                duration_str = ""
            else:
                diff_time = log.start_time - (
                    health_df.loc[idx - 1, "log"].start_time + health_df.loc[idx - 1, "log"].duration
                )
                if diff_time.seconds > 120:
                    duration_str = f"_+{get_duration_str(diff_time.seconds)}_"
                else:
                    duration_str = ""

            percentile_rank = 100 - log.final_health_percentage
            rank_binned = np.searchsorted(settings.RANK_BINS_PERCENTILE, percentile_rank, side="left")
            rank_emo = RANK_EMOTES[rank_binned].format(int(percentile_rank))

            health_str = "{:.2f}".format(log.final_health_percentage)

            rank_str = f"`{str(idx+1).zfill(2)}`{row['rank']}{rank_emo}`[ {health_str}% ]` "

            mins, secs = divmod(log.duration.seconds, 60)
            if log.phasetime_str != "":
                phasetime_str = f"`( {log.phasetime_str} )`"
            else:
                phasetime_str = ""

            log_tag = f"{rank_str}[Cerus CM]({log.url}) {phasetime_str}"

            log_str = f"{log_tag}{duration_str}\n"

            if (
                len(descriptions["cerus_cm"]["main"])
                + len(descriptions["cerus_cm"][f"field_{field_id}"])
                + len(log_str)
                > 4060
            ):
                field_id += 1
                # break
            if f"field_{field_id}" not in descriptions["cerus_cm"]:
                titles["cerus_cm"][f"field_{field_id}"] = ""
                descriptions["cerus_cm"][f"field_{field_id}"] = ""
            descriptions["cerus_cm"][f"field_{field_id}"] += log_str

        # # create message
        # group = InstanceClearGroup.objects.get(name="cerus_cm__20240316")

    # create_or_update_discord_message(group=group, hook=settings.WEBHOOKS["cerus_cm"], embeds_mes=[embed])
    embeds = create_embeds(titles=titles, descriptions=descriptions)
    embeds_mes = list(embeds.values())

    group = InstanceClearGroup.objects.get(name="cerus_cm__20240316")

    create_or_update_discord_message(group=group, hook=settings.WEBHOOKS["cerus_cm"], embeds_mes=embeds_mes)


# InstanceClearGroupInteraction.from_name(icg.name)


# %%

titles["cerus_cm"]["field_2"] = titles["cerus_cm"]["field_1"]
descriptions["cerus_cm"]["field_2"] = descriptions["cerus_cm"]["field_1"]

# %%
# titles = {"cerus_cm": {"main": "Sat 16 Mar 2024"}}
# descriptions = {"cerus_cm": {"main": field_value}}
embeds = create_embeds(titles=titles, descriptions=descriptions)
embeds_mes = list(embeds.values())
# field_value = """
# Day 1
# <t:1710446183:t> - <t:1710449140:t>
# <a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414> <a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414>
# <:cerus_cm:1198740269806395402><:bin50_percrank50:1218307650580647976>[Temple of Febe CM](https://dps.report/hKBH-20240314-214549_cerus) (**4:51**)+0:00
# <:cerus_cm:1198740269806395402><:bin50_percrank50:1218307650580647976>[Temple of Febe CM](https://dps.report/hKBH-20240314-214549_cerus) (**4:51**)+4:08
# <:cerus_cm:1198740269806395402><:bin50_percrank50:1218307650580647976>[Temple of Febe CM](https://dps.report/hKBH-20240314-214549_cerus) (**4:51**)+2:08
# """

# embed = discord.Embed(
#     title="Sat 16 Mar 2024",
#     description=field_value,
#     colour=EMBED_COLOR["cerus_cm"],
# )

group = InstanceClearGroup.objects.get(name="cerus_cm__20240316")

create_or_update_discord_message(group=group, hook=settings.WEBHOOKS["cerus_cm"], embeds_mes=embeds_mes)

# %%


data = a["phases"]
filtered_data = [d for d in data if "Cerus Breakbar" in d["name"]]
df = pd.DataFrame(filtered_data)
df["time"] = df["end"].apply(lambda x: datetime.timedelta(minutes=10) - datetime.timedelta(milliseconds=x))
phasetime_str = "|".join(
    [get_duration_str(i.astype("timedelta64[s]").astype(np.int32)) for i in df["time"].to_numpy()]
)
