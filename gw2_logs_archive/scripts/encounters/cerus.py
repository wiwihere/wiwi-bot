# %%

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)

import datetime
import logging
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
from django.conf import settings
from django.db.models import Q
from gw2_logs.models import (
    DpsLog,
    Emoji,
    Encounter,
    InstanceClearGroup,
)
from scripts.ei_parser import EliteInsightsParser
from scripts.helpers.local_folders import LogFile, LogPathsDate
from scripts.log_helpers import (
    RANK_EMOTES_CUPS,
    create_discord_time,
    create_or_update_discord_message,
    create_rank_emote_dict_percentiles,
    get_duration_str,
    today_y_m_d,
    zfill_y_m_d,
)
from scripts.log_instance_interaction import create_embeds
from scripts.log_uploader import DpsLogInteraction, LogUploader

logger = logging.getLogger(__name__)

# For cerus always use percentiles.
RANK_EMOTES = create_rank_emote_dict_percentiles(custom_emoji_name=False, invalid=False)
# %%
if __name__ == "__main__":
    y, m, d = today_y_m_d()
    y, m, d = 2024, 4, 6


def run_cerus_cm(y, m, d):
    print(f"Starting Cerus log import for {zfill_y_m_d(y, m, d)}")

    encounter = Encounter.objects.get(name="Temple of Febe")

    run_count = 0
    SLEEPTIME = 30
    MAXSLEEPTIME = 60 * SLEEPTIME  # Number of seconds without a log until we stop looking.
    current_sleeptime = MAXSLEEPTIME

    # Initialize local parser
    ei_parser = EliteInsightsParser()
    ei_parser.create_settings(out_dir=settings.EI_PARSED_LOGS_DIR.joinpath(zfill_y_m_d(y, m, d)), create_html=False)

    log_paths = LogPathsDate(y=y, m=m, d=d, allowed_folder_names=[encounter.folder_names])

    while True:
        # if True:
        icgi = None

        iclear_group, created = InstanceClearGroup.objects.update_or_create(
            name=f"cerus_cm__{zfill_y_m_d(y, m, d)}", type="strike"
        )

        for processing_type in ["local", "upload"]:
            titles = None
            descriptions = None

            # Find logs in directory
            logs_df = log_paths.update_available_logs()

            # Process each log
            loop_df = logs_df[~logs_df[f"{processing_type}_processed"]]

            # Process each log
            for row in loop_df.itertuples():
                log: LogFile = row.log
                log_path = log.path

                if processing_type == "local":
                    # Local processing
                    parsed_path = ei_parser.parse_log(evtc_path=log_path)
                    dli = DpsLogInteraction.from_local_ei_parser(log_path=log_path, parsed_path=parsed_path)
                    if dli is False:
                        logger.warning(
                            f"Parsing didnt work, too short log maybe. {log_path}. Skipping all further processing."
                        )
                        log.mark_local_processed()
                        log.mark_upload_processed()
                        continue
                    parsed_log = dli.dpslog
                elif processing_type == "upload":
                    if log.local_processed:  # Log must be parsed locally before uploading
                        # Upload log
                        log_upload = LogUploader.from_path(log_path, only_url=True)
                        parsed_log = log_upload.run()
                    else:
                        parsed_log = False

                if parsed_log.url != "":
                    log.mark_upload_processed()
                # skip on fail
                if not parsed_log:
                    continue

                cm_logs = DpsLog.objects.filter(
                    encounter__name="Temple of Febe",
                    start_time__year=y,
                    start_time__month=m,
                    start_time__day=d,
                    cm=True,
                    # final_health_percentage__lt=100,
                ).order_by("start_time")

                titles = {"cerus_cm": {"main": iclear_group.pretty_time}}

                # Set start time of clear
                if cm_logs:
                    start_time = min([i.start_time for i in cm_logs])
                    if iclear_group.start_time != start_time:
                        iclear_group.start_time = start_time
                        iclear_group.save()

                health_df = pd.DataFrame(
                    cm_logs.values_list("id", "final_health_percentage", "lcm"), columns=["id", "health", "lcm"]
                )
                health_df["log"] = cm_logs
                health_df.sort_values("health", inplace=True)

                health_df.reset_index(inplace=True)
                health_df["rank"] = health_df["index"].apply(lambda x: f"`{str(x + 1).zfill(2)}`")  # FIXME v1

                emote_cups = pd.Series(RANK_EMOTES_CUPS.values(), name="rank")
                health_df["cups"] = ""
                health_df.loc[:2, "cups"] = emote_cups[: len(health_df)]

                health_df.sort_values("index", inplace=True)
                health_df.set_index(["index"], inplace=True)

                field_id = 0

                cerus_title = "Cerus CM"
                difficulty = "cm"
                if len(health_df) > 0:
                    if health_df["lcm"].mode().values[0]:
                        cerus_title = "Cerus Legendary CM"
                        difficulty = "lcm"
                field_value = f"{Emoji.objects.get(name='Cerus').discord_tag(difficulty)} **{cerus_title}**\n{create_discord_time(cm_logs[0].start_time)} - {create_discord_time(list(cm_logs)[-1].start_time + list(cm_logs)[-1].duration)}\n\
        <a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414> <a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414>\n"
                # field_value += f"`nr`{BLANK_EMOTE}⠀⠀ `( health | 80%  | 50%  | 10%  )`\n"
                # field_value += f"\n`##`⠀⠀**log** `( health |  80% |  50% |  10% )`+delay\n\n"
                # field_value += f"\n`##`⠀⠀**log** `(health| 80% | 50% | 10% )`+delay\n\n"
                # field_value += f"\n`##`{BLANK_EMOTE}**★** `(health| 80% | 50% | 10% )`+_delay_\n\n"
                table_header = f"\n`##`{RANK_EMOTES[7]}**★** ` health |  80% |  50% |  10% `+_delay_⠀⠀\n\n"
                field_value += table_header
                descriptions = {"cerus_cm": {"main": field_value}}

                titles["cerus_cm"]["field_0"] = ""
                descriptions["cerus_cm"]["field_0"] = ""

                for idx, row in health_df.iterrows():
                    log = row["log"]

                    # Set the delay between tries, only show when larger than 2 minutes.
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

                    # Find the medal for the achived health percentage
                    percentile_rank = 100 - log.final_health_percentage
                    rank_binned = np.searchsorted(settings.RANK_BINS_PERCENTILE, percentile_rank, side="left")
                    rank_emo = RANK_EMOTES[rank_binned].format(int(percentile_rank))

                    health_str = ".".join(
                        [str(int(i)).zfill(2) for i in str(round(log.final_health_percentage, 2)).split(".")]
                    )  # makes 02.20%
                    if health_str == "100.00":
                        health_str = "100.0"

                    # rank_str = f"`{str(idx+1).zfill(2)}`{row['rank']}{rank_emo}`[ {health_str}% ]` "
                    # rank_str = f"{row['rank']}{rank_emo}` {health_str}% ` "  # FIXME v1
                    rank_str = f"{row['rank']}{rank_emo}"  # FIXME v2

                    if log.phasetime_str != "":
                        # phasetime_str = f"`( {log.phasetime_str} )`"
                        phasetime_str = f"` {health_str}% | {log.phasetime_str} `{row['cups']}"  # FIXME v2
                        # phasetime_str = f"`( {health_str}% | {log.phasetime_str} )`{row['cups']}".replace(" ", "")  # FIXME v2
                        # phasetime_str = f"`( {health_str}`[%]({log.url})` | {log.phasetime_str} )`{row['cups']}".replace(" ", "")  # FIXME v3
                        # phasetime_str = phasetime_str.replace("--", "--- ")  # FIXME v3
                        # phasetime_str = phasetime_str.replace("|", " | ")  # FIXME v3
                    else:
                        phasetime_str = ""

                    if log.lcm:
                        log_link_emote = "★"
                    else:
                        log_link_emote = "☆"

                    if log.url != "":
                        log_tag = f"{rank_str}[{log_link_emote}]({log.url}) {phasetime_str}"
                    else:
                        log_tag = f"{rank_str}{log_link_emote} {phasetime_str}"

                    log_str = f"{log_tag}{duration_str}\n"

                    # Break into multiple embed fields if too many tries.
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

                    # Reset sleep timer
                    current_sleeptime = MAXSLEEPTIME

            if titles is not None:
                embeds = create_embeds(titles=titles, descriptions=descriptions)
                embeds_mes = list(embeds.values())

                day_count = len(
                    InstanceClearGroup.objects.filter(
                        Q(name__contains="cerus_cm__")
                        & Q(
                            start_time__lte=datetime.datetime(year=y, month=m, day=d + 1, tzinfo=datetime.timezone.utc)
                        )
                    )
                )
                embeds_mes[0] = embeds_mes[0].set_author(name=f"#{str(day_count).zfill(2)}")
                if len(embeds_mes) > 0:
                    for i, _ in enumerate(embeds_mes):
                        if i > 0:
                            embeds_mes[i].description = table_header + embeds_mes[i].description

                create_or_update_discord_message(
                    group=iclear_group, hook=settings.WEBHOOKS["cerus_cm"], embeds_mes=embeds_mes
                )

        if (current_sleeptime < 0) or ((y, m, d) != today_y_m_d()):
            print("Finished run")
            return

        current_sleeptime -= SLEEPTIME
        print(f"Run {run_count} done")

        time.sleep(SLEEPTIME)
        run_count += 1
        # break

    # %%
