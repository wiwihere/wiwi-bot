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
from gw2_logs.models import (
    DpsLog,
    Emoji,
)
from scripts.discord_interaction.build_embeds import create_discord_embeds, create_discord_embeds_v3
from scripts.discord_interaction.message_helpers import (
    add_line_to_descriptions,
    create_duration_header_with_player_emotes,
)
from scripts.discord_interaction.send_message import Thread, create_or_update_discord_message
from scripts.model_interactions.dpslog import DpsLogMessageBuilder
from scripts.progression.base_progression_service import ProgressionService

logger = logging.getLogger(__name__)


def _build_log_message_line_progression(progression_service: ProgressionService, row: pd.Series) -> str:
    """Row of logs_rank_health_df created by
    encounter_progression/base_progression_service.py/ProgressionService.create_logs_rank_health_df.
    """
    dpslog: DpsLog = row["log"]

    # -------------------------------
    # Find the medal for the achieved health percentage -> "<:4_masterwork:1218309092477767810>"
    # -------------------------------
    rank_emote = progression_service.get_rank_emote_for_log(dpslog)

    if dpslog.lcm:
        url_emote = "★"
    elif dpslog.cm:
        url_emote = "☆"
    else:
        url_emote = Emoji.objects.get(name="PepoHands").discord_tag_custom_name().format("normal_mode")

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
    health_phasetime_str = (
        f"` {health_str}% | {dli.build_phasetime_str(progression_service.display_health_percentages)} `"
    )

    # -------------------------------
    # Combine
    # -------------------------------
    log_message_line = (
        f"{row['log_nr']}{rank_emote}{url_emote_str} {health_phasetime_str}{row['cups']}{row['delay_str']}\n"
    )

    return log_message_line


def _build_progression_discord_message(
    progression_service: ProgressionService, colour_key="dummy"
) -> tuple[dict, dict, str]:
    """Build the titles and descriptions for the progression message embeds.
    The actual embeds are created in send_progression_discord_message,
    after which they are sent to discord.
    """
    progression_logs: list = progression_service.iclear_group.dps_logs_all
    logs_rank_health_df = progression_service.create_logs_rank_health_df(minimal_delay_seconds=120)

    # Make title and description for discord message
    difficulty = progression_service.get_difficulty(logs_rank_health_df)  # normal, cm or lcm
    boss_title = progression_service.get_boss_title(difficulty)

    embed_header = progression_service.get_table_header()
    description_main = [f"{progression_service.encounter.emoji.discord_tag(difficulty)} **{boss_title}**\n"]
    description_main += [create_duration_header_with_player_emotes(all_logs=progression_logs)]
    description_main += [embed_header]

    titles = {}
    descriptions = {}

    # General header with boss name, duration and player emotes
    titles[colour_key] = {"main": [progression_service.iclear_group.pretty_time]}
    descriptions[colour_key] = {"main": description_main}

    # All lines with logs go here.
    titles[colour_key]["lines"] = [""]
    descriptions[colour_key]["lines"] = []

    for idx, row in logs_rank_health_df.iterrows():
        log_message_line = _build_log_message_line_progression(progression_service=progression_service, row=row)
        descriptions[colour_key]["lines"].append(log_message_line)

    return titles, descriptions, embed_header


def send_progression_discord_message(progression_service: ProgressionService) -> None:
    """Build and send or update the progression discord message for the given InstanceClearGroup."""
    colour_key = "dummy"  # needed for embed colour parsing.
    titles, descriptions, embed_header = _build_progression_discord_message(
        progression_service=progression_service, colour_key=colour_key
    )

    if titles is not None:
        embeds = create_discord_embeds_v3(
            titles=titles,
            descriptions=descriptions,
            embed_header=embed_header,
            author=progression_service.get_message_author(),
            footer=progression_service.get_message_footer(),
            embed_colour_dict={colour_key: progression_service.embed_colour},
        )
        embeds_messages_list = list(embeds.values())

        logger.debug("Ready to send discord message")
        create_or_update_discord_message(
            group=progression_service.iclear_group,
            webhook_url=progression_service.webhook_url,
            embeds_messages_list=embeds_messages_list,
            thread=Thread(progression_service.webhook_thread_id),
        )


# %%
if __name__ == "__main__":
    from scripts.log_helpers import today_y_m_d
    from scripts.progression.configurable_progression_service import ConfigurableProgressionService

    y, m, d = today_y_m_d()
    y, m, d = 2025, 12, 8
    progression_service = ConfigurableProgressionService(clear_group_base_name="decima_cm", y=y, m=m, d=d)

    dpslog = progression_service.iclear_group.dps_logs_all[0]

    # %%
