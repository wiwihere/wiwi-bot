# %%

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import datetime
import logging
import time
from ast import In
from typing import Tuple

import numpy as np
import pandas as pd
from django.conf import settings
from django.db.models import Q, QuerySet
from gw2_logs.models import (
    DpsLog,
    Emoji,
    Encounter,
    InstanceClear,
    InstanceClearGroup,
)
from scripts.discord_interaction.build_embeds import create_discord_embeds
from scripts.discord_interaction.build_message import _create_duration_header_with_player_emotes
from scripts.discord_interaction.send_message import create_or_update_discord_message
from scripts.encounters.base import BaseEncounterRunner
from scripts.log_helpers import (
    RANK_EMOTES_CUPS,
    create_discord_time,
    create_rank_emote_dict_percentiles,
    get_duration_str,
    get_rank_emote,
    today_y_m_d,
    zfill_y_m_d,
)
from scripts.log_processing.ei_parser import EliteInsightsParser
from scripts.log_processing.log_files import LogFile, LogFilesDate
from scripts.log_processing.log_uploader import LogUploader
from scripts.log_processing.logfile_processing import process_logs_once
from scripts.model_interactions.dps_log import DpsLogInteraction
from scripts.model_interactions.instance_clear_group import InstanceClearGroupInteraction

logger = logging.getLogger(__name__)

# For cerus always use percentiles.
RANK_EMOTES_CERUS, RANK_BINS_PERCENTILE_CERUS = create_rank_emote_dict_percentiles(
    custom_emoji_name=False, invalid=False
)

CLEAR_GROUP_BASE_NAME = "cerus_cm__"  # followed by y_m_d; e.g. cerus_cm__20240406

# %%
if __name__ == "__main__":
    y, m, d = today_y_m_d()
    y, m, d = 2024, 3, 16
    clear_name = f"{CLEAR_GROUP_BASE_NAME}{zfill_y_m_d(y, m, d)}"


class BaseEncounterRunner:
    encounter_name: str
    webhook_key: str
    use_percentiles: bool = True

    def __init__(self, y, m, d):
        self.y, self.m, self.d = y, m, d
        self.encounter = Encounter.objects.get(name=self.encounter_name)
        self.ei_parser = EliteInsightsParser()

    def setup_parser(self):
        self.ei_parser.create_settings(
            out_dir=settings.EI_PARSED_LOGS_DIR.joinpath(zfill_y_m_d(self.y, self.m, self.d)),
            create_html=False,
        )

    def run(self):
        self.setup_parser()
        self.process_logs()

    def process_logs(self):
        raise NotImplementedError


class CerusCMRunner(BaseEncounterRunner):
    encounter_name = "Temple of Febe"
    webhook_key = "cerus_cm"

    def process_logs(self):
        cm_logs = self.get_cm_logs()
        embed_builder = CerusEmbedBuilder(cm_logs)
        embeds = embed_builder.build()

        # create_or_update_discord_message(
        #     group=embed_builder.group,
        #     webhook_url=settings.WEBHOOKS[self.webhook_key],
        #     embeds_messages_list=embeds,
        # )


class CerusEmbedBuilder:
    def __init__(self, logs: QuerySet[DpsLog]):
        self.logs = logs
        self.group = self._get_or_create_group()

    def build(self) -> list:
        health_df = self._build_health_df()
        return create_discord_embeds(
            titles=self._titles(),
            descriptions=self._descriptions(health_df),
        )


def create_health_df(cm_logs: list[DpsLog], minimal_delay_seconds: int) -> pd.DataFrame:
    """Create dataframe with health and rank information for cm logs.
    This dataframe is used to build the discord message line by line

    Parameters
    ----------
    cm_logs : QuerySet[DpsLog]
        Queryset of cm DpsLogs
    minimal_timediff_seconds : int
        Minimal time difference in seconds between logs to show delay in discord message.
    """
    health_df = pd.DataFrame(
        [(x.id, x.final_health_percentage, x.lcm) for x in cm_logs], columns=["id", "health", "lcm"]
    )
    health_df["log"] = cm_logs

    # Add log counter
    health_df.reset_index(inplace=True)
    health_df.rename(columns={"index": "log_nr"}, inplace=True)
    health_df["log_nr"] = health_df["log_nr"].apply(lambda x: f"`{str(x + 1).zfill(2)}`")

    # Add rank based on health
    health_df.sort_values("health", inplace=True)
    health_df.reset_index(inplace=True, drop=True)
    health_df.reset_index(inplace=True, drop=False)
    health_df.rename(columns={"index": "rank"}, inplace=True)
    health_df["rank"] += 1

    # Add rank cups for the best 3 logs
    emote_cups = pd.Series(RANK_EMOTES_CUPS.values(), name="rank")
    health_df["cups"] = ""
    health_df.loc[:2, "cups"] = emote_cups[: len(health_df)]

    # Revert to chronological order
    health_df.sort_values("log_nr", inplace=True)
    health_df.reset_index(inplace=True, drop=True)

    # time_diff between logs
    # extract times
    start_time = health_df["log"].apply(lambda x: x.start_time)
    end_time = health_df["log"].apply(lambda x: x.start_time + x.duration)
    health_df["time_diff"] = start_time - end_time.shift(1)
    health_df["delay_str"] = health_df["time_diff"].apply(
        lambda x: f"_+{get_duration_str(x.seconds)}_" if x.seconds > minimal_delay_seconds else ""
    )

    return health_df


def build_log_message_line_cerus(row: pd.Series) -> str:
    dpslog: DpsLog = row["log"]

    # -------------------------------
    # Build rank_emote -> "<:4_masterwork:1218309092477767810>"
    # -------------------------------
    # Find the medal for the achieved health percentage
    percentile_rank = 100 - dpslog.final_health_percentage
    rank_binned = np.searchsorted(RANK_BINS_PERCENTILE_CERUS, percentile_rank, side="left")
    rank_emote = RANK_EMOTES_CERUS[rank_binned].format(int(percentile_rank))

    if dpslog.lcm:
        log_url_emote = "★"
    else:
        log_url_emote = "☆"

    # -------------------------------
    # Build phasetime_str -> "` 52.05% | 8:24 |  --  |  -- `"
    # -------------------------------
    health_str = DpsLogInteraction(dpslog).build_health_str()
    if dpslog.phasetime_str != "":
        phasetime_str = f"` {health_str}% | {dpslog.phasetime_str} `{row['cups']}"
    else:
        phasetime_str = ""

    # -------------------------------
    # Combine
    # -------------------------------
    if dpslog.url != "":
        log_message_line = (
            f"{row['log_nr']}{rank_emote}[{log_url_emote}]({dpslog.url}) {phasetime_str}{row['delay_str']}\n"
        )
    else:
        log_message_line = f"{row['log_nr']}{rank_emote}{log_url_emote} {phasetime_str}{row['delay_str']}\n"

    return log_message_line


def build_cerus_discord_message(iclear_group: InstanceClearGroup) -> tuple[dict, dict]:
    cm_logs = iclear_group.dps_logs_all

    # Set start time of clear
    # TODO move out of message building

    field_id = 0

    health_df = create_health_df(cm_logs=cm_logs, minimal_delay_seconds=120)

    # Make title and description for discord message
    cerus_title = "Cerus CM"
    difficulty = "cm"
    if len(health_df) > 0:
        if health_df["lcm"].mode().iloc[0]:
            cerus_title = "Cerus Legendary CM"
            difficulty = "lcm"

    table_header = f"\n`##`{RANK_EMOTES_CERUS[7]}**★** ` health |  80% |  50% |  10% `+_delay_⠀⠀\n\n"

    description_main = f"{Emoji.objects.get(name='Cerus').discord_tag(difficulty)} **{cerus_title}**\n"
    description_main += _create_duration_header_with_player_emotes(all_logs=cm_logs)
    # description_main += table_header

    titles = {}
    descriptions = {}

    titles["cerus_cm"] = {"main": iclear_group.pretty_time}
    descriptions["cerus_cm"] = {"main": description_main}

    titles["cerus_cm"]["field_0"] = table_header
    descriptions["cerus_cm"]["field_0"] = ""

    for idx, row in health_df.iterrows():
        log_message_line = build_log_message_line_cerus(row=row)

        # Break into multiple embed fields if too many tries.
        if (
            len(descriptions["cerus_cm"]["main"])
            + len(descriptions["cerus_cm"][f"field_{field_id}"])
            + len(log_message_line)
            > 4060
        ):
            field_id += 1
            # break
        if f"field_{field_id}" not in descriptions["cerus_cm"]:
            logger.info(f"Adding new field field_{field_id} for discord message")
            titles["cerus_cm"][f"field_{field_id}"] = table_header
            descriptions["cerus_cm"][f"field_{field_id}"] = ""

        descriptions["cerus_cm"][f"field_{field_id}"] += log_message_line

    return titles, descriptions


# %%


def update_instance_clear(
    iclear: InstanceClear, iclear_group: InstanceClearGroup
) -> Tuple[InstanceClear, InstanceClearGroup]:
    dps_logs_all = iclear_group.dps_logs_all
    if dps_logs_all:
        start_time = min([i.start_time for i in dps_logs_all])
        # Set iclear_group start time
        if iclear_group.start_time != start_time:
            logger.info(f"Updating start time for {iclear_group.name} from {iclear_group.start_time} to {start_time}")
            iclear_group.start_time = start_time
            iclear_group.save()

        # Set iclear start time
        if iclear.start_time != start_time:
            logger.info(f"Updating start time for {iclear.name} from {iclear.start_time} to {log0.start_time}")
            iclear.start_time = start_time
            iclear.save()

        # Set iclear duration
        last_log = dps_logs_all.order_by("start_time").last()
        calculated_duration = last_log.start_time + last_log.duration - iclear.start_time
        if iclear.duration != calculated_duration:
            logger.info(f"Updating duration for {iclear.name} from {iclear.duration} to {calculated_duration}")
            iclear.duration = calculated_duration
            iclear.save()

    return iclear, iclear_group


def run_cerus_cm(y, m, d):
    logger.info(f"Starting Cerus log import for {zfill_y_m_d(y, m, d)}")

    encounter = Encounter.objects.get(name="Temple of Febe")

    run_count = 0
    SLEEPTIME = 30
    MAXSLEEPTIME = 60 * SLEEPTIME  # Number of seconds without a log until we stop looking.
    current_sleeptime = MAXSLEEPTIME

    # Initialize local parser
    ei_parser = EliteInsightsParser()
    ei_parser.create_settings(out_dir=settings.EI_PARSED_LOGS_DIR.joinpath(zfill_y_m_d(y, m, d)), create_html=False)

    log_files_date = LogFilesDate(y=y, m=m, d=d, allowed_folder_names=[encounter.folder_names])

    # Flow start
    PROCESSING_SEQUENCE = ["local", "upload"] + ["local"] * 9

    iclear_group, created = InstanceClearGroup.objects.get_or_create(name=clear_name, type="strike")
    iclear, created = InstanceClear.objects.get_or_create(
        defaults={
            "instance": encounter.instance,
            "instance_clear_group": iclear_group,
        },
        name=clear_name,
    )

    # icgi = InstanceClearGroupInteraction(iclear_group=iclear_group, update_total_duration=False)

    while True:
        # if True:

        for processing_type in PROCESSING_SEQUENCE:
            processed_logs = process_logs_once(
                processing_type=processing_type,
                log_files_date_cls=log_files_date,
                ei_parser=ei_parser,
            )

            if processed_logs:
                current_sleeptime = MAXSLEEPTIME

            titles, descriptions = build_cerus_discord_message(iclear_group=iclear_group)

            # Build discord message
            titles = None
            descriptions = None

            if titles is not None:
                embeds = create_discord_embeds(titles=titles, descriptions=descriptions)
                embeds_mes = list(embeds.values())

                # The progression_days_count is the total days up to this point for this progression
                progression_days_count = len(
                    InstanceClearGroup.objects.filter(
                        Q(name__contains=CLEAR_GROUP_BASE_NAME)
                        & Q(
                            start_time__lte=datetime.datetime(year=y, month=m, day=d + 1, tzinfo=datetime.timezone.utc)
                        )
                    )
                )
                embeds_mes[0] = embeds_mes[0].set_author(name=f"Day #{str(progression_days_count).zfill(2)}")
                # TODO disabled, trying to use title field.
                # if len(embeds_mes) > 0:
                #     for i, _ in enumerate(embeds_mes):
                #         if i > 0:
                #             embeds_mes[i].description = table_header + embeds_mes[i].description

                # create_or_update_discord_message(
                #     group=iclear_group, webhook_url=settings.WEBHOOKS["cerus_cm"], embeds_messages_list=embeds_mes
                # )

        if (current_sleeptime < 0) or ((y, m, d) != today_y_m_d()):
            print("Finished run")
            return

        current_sleeptime -= SLEEPTIME
        print(f"Run {run_count} done")

        time.sleep(SLEEPTIME)
        run_count += 1
        # break
