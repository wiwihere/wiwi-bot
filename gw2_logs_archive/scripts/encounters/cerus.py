# %%

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import logging
import time
from typing import Tuple

import numpy as np
import pandas as pd
from django.conf import settings
from django.db.models import Q
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
from scripts.log_helpers import (
    RANK_EMOTES_CUPS_PROGRESSION,
    create_rank_emote_dict_percentiles,
    get_duration_str,
    today_y_m_d,
    zfill_y_m_d,
)
from scripts.log_processing.ei_parser import EliteInsightsParser
from scripts.log_processing.log_files import LogFilesDate
from scripts.log_processing.logfile_processing import process_logs_once
from scripts.model_interactions.dps_log import DpsLogInteraction

logger = logging.getLogger(__name__)

# For cerus always use percentiles.
RANK_EMOTES_CERUS, RANK_BINS_PERCENTILE_CERUS = create_rank_emote_dict_percentiles(
    custom_emoji_name=False, invalid=False
)

CLEAR_GROUP_BASE_NAME = "cerus_cm__"  # followed by y_m_d; e.g. cerus_cm__20240406


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
    health_df["log_idx"] = health_df["index"]
    health_df.rename(columns={"index": "log_nr"}, inplace=True)
    health_df["log_nr"] = health_df["log_nr"].apply(lambda x: f"`{str(x + 1).zfill(2)}`")

    # Add rank based on health
    health_df.sort_values("health", inplace=True)
    health_df.reset_index(inplace=True, drop=True)
    health_df.reset_index(inplace=True, drop=False)
    health_df.rename(columns={"index": "rank"}, inplace=True)
    health_df["rank"] += 1

    # Add rank cups for the best 3 logs
    emote_cups = pd.Series(RANK_EMOTES_CUPS_PROGRESSION.values(), name="rank")
    health_df["cups"] = ""
    health_df.loc[:2, "cups"] = emote_cups[: len(health_df)]
    health_df.loc[:2, "cups"] = health_df.loc[:2, "cups"].apply(lambda x: x.format(len(health_df)))

    # Revert to chronological order
    health_df.sort_values("log_idx", inplace=True)
    health_df.reset_index(inplace=True, drop=True)

    # Add time_diff between logs. delay_str is only shown if time_diff > minimal_delay_seconds
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


def add_line_to_descriptions(
    titles: dict,
    descriptions: dict,
    current_field: int,
    log_message_line: str,
    dummy_group: str,
    table_header: str,
) -> Tuple[dict, dict, str]:
    """Add a line to the descriptions dict, creating new fields if the discord limit
    of 4060 characters would be hit.
    """
    if (
        len(descriptions[dummy_group]["main"]) + len(descriptions[dummy_group][current_field]) + len(log_message_line)
        > 4060
    ):
        # Make a new field
        current_field = f"field_{int(current_field.split('_')[1]) + 1}"

    if current_field not in descriptions[dummy_group]:
        logger.info(f"Character limit hit for description. Adding new field {current_field} for discord message")
        titles[dummy_group][current_field] = ""
        descriptions[dummy_group][current_field] = table_header

    descriptions[dummy_group][current_field] += log_message_line

    return titles, descriptions, current_field


def build_cerus_discord_message(iclear_group: InstanceClearGroup) -> tuple[dict, dict]:
    cm_logs = iclear_group.dps_logs_all

    # Set start time of clear
    # TODO move out of message building

    health_df = create_health_df(cm_logs=cm_logs, minimal_delay_seconds=120)

    # Make title and description for discord message
    cerus_title = "Cerus CM"
    difficulty = "cm"
    if len(health_df) > 0:
        if health_df["lcm"].mode().iloc[0]:
            cerus_title = "Cerus Legendary CM"
            difficulty = "lcm"

    table_header = f"`##`{RANK_EMOTES_CERUS[7]}**★** ` health |  80% |  50% |  10% `+_delay_⠀⠀\n\n"

    description_main = f"{Emoji.objects.get(name='Cerus').discord_tag(difficulty)} **{cerus_title}**\n"
    description_main += _create_duration_header_with_player_emotes(all_logs=cm_logs)
    description_main += table_header

    titles = {}
    descriptions = {}

    dummy_group = "cerus_cm"  # needed for embed parsing
    titles[dummy_group] = {"main": iclear_group.pretty_time}
    descriptions[dummy_group] = {"main": description_main}

    current_field = "field_0"
    titles[dummy_group][current_field] = ""
    descriptions[dummy_group][current_field] = ""

    for idx, row in health_df.iterrows():
        log_message_line = build_log_message_line_cerus(row=row)

        # Add line to descriptions, breaking into new fields if character limit is hit
        titles, descriptions, current_field = add_line_to_descriptions(
            titles=titles,
            descriptions=descriptions,
            current_field=current_field,
            log_message_line=log_message_line,
            dummy_group=dummy_group,
            table_header=table_header,
        )
    return titles, descriptions


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
            logger.info(f"Updating start time for {iclear.name} from {iclear.start_time} to {start_time}")
            iclear.start_time = start_time
            iclear.save()

        # Set iclear duration
        last_log = dps_logs_all[-1]
        calculated_duration = last_log.start_time + last_log.duration - iclear.start_time
        if iclear.duration != calculated_duration:
            logger.info(f"Updating duration for {iclear.name} from {iclear.duration} to {calculated_duration}")
            iclear.duration = calculated_duration
            iclear.save()

    return iclear, iclear_group


def create_message_author_progression_days(iclear_group: InstanceClearGroup) -> str:
    """Create author name for discord message.
    The author is displayed at the top of the message.
    """
    # The progression_days_count is the total days up to this point for this progression
    progression_days_count = len(
        InstanceClearGroup.objects.filter(
            Q(name__contains=CLEAR_GROUP_BASE_NAME) & Q(start_time__lte=iclear_group.start_time)
        )
    )
    return f"Day #{str(progression_days_count).zfill(2)}"


def send_cerus_progression_discord_message(iclear_group: InstanceClearGroup) -> None:
    """Build and send or update the cerus progression discord message for the given InstanceClearGroup."""
    titles, descriptions = build_cerus_discord_message(iclear_group=iclear_group)

    if titles is not None:
        embeds = create_discord_embeds(titles=titles, descriptions=descriptions)
        embeds_messages_list = list(embeds.values())

        message_author = create_message_author_progression_days(iclear_group=iclear_group)

        embeds_messages_list[0] = embeds_messages_list[0].set_author(name=message_author)

        create_or_update_discord_message(
            group=iclear_group,
            webhook_url=settings.WEBHOOKS["cerus_cm"],
            embeds_messages_list=embeds_messages_list,
        )


def run_cerus_cm(y: int, m: int, d: int, clear_name: str) -> None:
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

    while True:
        for processing_type in PROCESSING_SEQUENCE:
            processed_logs = process_logs_once(
                processing_type=processing_type,
                log_files_date_cls=log_files_date,
                ei_parser=ei_parser,
            )

            if processed_logs:
                current_sleeptime = MAXSLEEPTIME

            if len(processed_logs) > 0:
                iclear, iclear_group = update_instance_clear(iclear=iclear, iclear_group=iclear_group)
                send_cerus_progression_discord_message(iclear_group=iclear_group)

            if processing_type == "local":
                time.sleep(SLEEPTIME / 10)

        current_sleeptime -= SLEEPTIME
        logger.info(f"Run {run_count} done")
        run_count += 1
        if (current_sleeptime < 0) or ((y, m, d) != today_y_m_d()):
            logger.info("Finished run")
            break


# %%
if __name__ == "__main__":
    y, m, d = today_y_m_d()
    y, m, d = 2024, 3, 16
    clear_name = f"{CLEAR_GROUP_BASE_NAME}{zfill_y_m_d(y, m, d)}"
