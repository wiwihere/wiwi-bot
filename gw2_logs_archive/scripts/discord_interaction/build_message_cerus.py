# %% gw2_logs_archive\scripts\discord_interaction\build_message_cerus.py
"""Build Cerus-specific discord messages

Helpers to create the Cerus progression message embed. The functions in
this module build message lines from `DpsLog` objects and the Cerus
progression dataframes. These are presentation-focused utilities and should
use the service layer for domain concerns when needed.
"""

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import logging

import pandas as pd
from django.conf import settings
from gw2_logs.models import (
    DpsLog,
)
from scripts.discord_interaction.build_embeds import create_discord_embeds
from scripts.discord_interaction.message_helpers import (
    add_line_to_descriptions,
    create_duration_header_with_player_emotes,
)
from scripts.discord_interaction.send_message import Thread, create_or_update_discord_message
from scripts.encounter_progression.cerus_service import CerusProgressionService
from scripts.model_interactions.dpslog import DpsLogMessageBuilder

logger = logging.getLogger(__name__)


def _build_log_message_line_cerus(row: pd.Series) -> str:
    """Row of health_df created by encounter_progression/base.py/ProgressionService.create_health_df"""
    dpslog: DpsLog = row["log"]

    # -------------------------------
    # Find the medal for the achieved health percentage -> "<:4_masterwork:1218309092477767810>"
    # -------------------------------
    rank_emote = CerusProgressionService.get_rank_emote_for_log(dpslog)

    if dpslog.lcm:
        url_emote = "★"
    else:
        url_emote = "☆"

    if dpslog.url != "":
        url_emote_str = f"[{url_emote}]({dpslog.url})"
    else:
        url_emote_str = url_emote

    # -------------------------------
    # Build phasetime_str -> "` 52.05% | 8:24 |  --  |  -- `"
    # -------------------------------
    # Note the ` at the start and end of the str, this makes it appear as a code block in discord,
    # which is a nice way to align the text and make it more readable.
    dli = DpsLogMessageBuilder(dpslog)
    health_str = dli.build_health_str()
    health_phasetime_str = f"` {health_str}% | {dli.build_phasetime_str()} `"

    # -------------------------------
    # Combine
    # -------------------------------
    log_message_line = (
        f"{row['log_nr']}{rank_emote}{url_emote_str} {health_phasetime_str}{row['cups']}{row['delay_str']}\n"
    )

    return log_message_line


def _build_cerus_discord_message(progression_service: CerusProgressionService) -> tuple[dict, dict]:
    progression_logs: list = progression_service.iclear_group.dps_logs_all
    logs_rank_health_df = progression_service.create_logs_rank_health_df(minimal_delay_seconds=120)

    # Make title and description for discord message
    difficulty = progression_service.get_difficulty(logs_rank_health_df)  # normal, cm or lcm
    boss_title = progression_service.get_boss_title(difficulty)

    table_header = progression_service.get_table_header()
    description_main = f"{progression_service.encounter.emoji.discord_tag(difficulty)} **{boss_title}**\n"
    description_main += create_duration_header_with_player_emotes(all_logs=progression_logs)
    description_main += table_header

    titles = {}
    descriptions = {}

    colour_group = "cerus_cm"  # needed for embed parsing, needs to be in EMBED_COLOR
    titles[colour_group] = {"main": progression_service.iclear_group.pretty_time}
    descriptions[colour_group] = {"main": description_main}

    current_field = "field_0"
    titles[colour_group][current_field] = ""
    descriptions[colour_group][current_field] = ""

    for idx, row in logs_rank_health_df.iterrows():
        log_message_line = _build_log_message_line_cerus(row=row)

        # Add line to descriptions, breaking into new fields if character limit is hit
        titles, descriptions, current_field = add_line_to_descriptions(
            titles=titles,
            descriptions=descriptions,
            current_field=current_field,
            log_message_line=log_message_line,
            dummy_group=colour_group,
            table_header=table_header,
        )
    return titles, descriptions


def send_cerus_progression_discord_message(progression_service: CerusProgressionService) -> None:
    """Build and send or update the cerus progression discord message for the given InstanceClearGroup."""
    titles, descriptions = _build_cerus_discord_message(progression_service=progression_service)

    if titles is not None:
        embeds = create_discord_embeds(titles=titles, descriptions=descriptions)
        embeds_messages_list = list(embeds.values())
        embeds_messages_list[0] = embeds_messages_list[0].set_author(name=progression_service.get_message_author())

        logger.debug("Ready to send discord message")
        create_or_update_discord_message(
            group=progression_service.iclear_group,
            webhook_url=settings.WEBHOOKS["progression"],
            embeds_messages_list=embeds_messages_list,
            thread=Thread(getattr(settings.ENV_SETTINGS, "webhook_bot_thread_cerus_cm")),
        )


# %%
