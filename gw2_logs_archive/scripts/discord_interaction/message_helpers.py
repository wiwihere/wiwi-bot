# %% gw2_logs_archive\scripts\discord_interaction\message_helpers.py
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging
from typing import Tuple

import discord
import numpy as np
from gw2_logs.models import (
    DpsLog,
)
from scripts.log_helpers import (
    PLAYER_EMOTES,
    create_discord_time,
)

logger = logging.getLogger(__name__)


def create_duration_header_with_player_emotes(all_logs: list[DpsLog]) -> str:
    """Create the embed header with the core, friend and pugs having a different emote, as configured in PLAYER_EMOTES (ducks) for each player.
    Returns this string with the start and endtime as well, like so;
    19:45 - 22:00
    duck duck duck ... etc
    """
    # Calculate the median players in the instancecleargroup
    try:
        core_count = int(np.median([log.core_player_count for log in all_logs]))
        friend_count = int(np.median([log.friend_player_count for log in all_logs]))
        pug_count = int(np.median([log.player_count for log in all_logs])) - core_count - friend_count
    except TypeError:
        logger.error("Couldnt find core_count")
        core_count = 0
        friend_count = 0
        pug_count = 10

    # Create the string with emotes for each player. After 5 players a space is added
    pug_split_str = f"{PLAYER_EMOTES['core'] * core_count}{PLAYER_EMOTES['friend'] * friend_count}{PLAYER_EMOTES['pug'] * pug_count}".split(
        ">"
    )
    if len(pug_split_str) > 5:
        pug_split_str[5] = f" {pug_split_str[5]}"  # empty str here:`⠀`
    pug_str = ">".join(pug_split_str)

    # title description with start - end time and colored ducks for core/pugs
    description = f"""{create_discord_time(all_logs[0].start_time)} - \
{create_discord_time(all_logs[-1].start_time + all_logs[-1].duration)} \
\n{pug_str}\n
"""
    return description


def add_line_to_descriptions(
    titles: dict,
    descriptions: dict,
    current_field: str,
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


def calculate_embed_size(embed: discord.Embed) -> int:
    """Calculate the size of the embed in characters."""
    total_length = len(embed.author) + len(embed.title) + len(embed.description) + len(embed.footer)
    for field in embed.fields:
        total_length += len(field.name) + len(field.value)
    return total_length
