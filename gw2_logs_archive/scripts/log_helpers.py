# %%
"""Helper functions and variables"""

import datetime
import logging
import os
import time
from dataclasses import dataclass
from itertools import chain
from typing import Optional, Union

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)

from pathlib import Path

import discord
import numpy as np
import pandas as pd
import pytz
from discord import SyncWebhook
from discord.utils import MISSING
from django.conf import settings
from gw2_logs.models import DiscordMessage, DpsLog, Emoji, Encounter, Instance, InstanceClearGroup, InstanceGroup
from tzlocal import get_localzone

logger = logging.getLogger(__name__)

WIPE_EMOTES = {
    0: Emoji.objects.get(name="wipe 13").discord_tag_custom_name(),  # OLC can still be bugged and give 0 health.
    1: Emoji.objects.get(name="wipe 13").discord_tag_custom_name(),  # Between 0 and 12.5%
    2: Emoji.objects.get(name="wipe 25").discord_tag_custom_name(),
    3: Emoji.objects.get(name="wipe 38").discord_tag_custom_name(),
    4: Emoji.objects.get(name="wipe 50").discord_tag_custom_name(),
    5: Emoji.objects.get(name="wipe 63").discord_tag_custom_name(),
    6: Emoji.objects.get(name="wipe 75").discord_tag_custom_name(),
    7: Emoji.objects.get(name="wipe 88").discord_tag_custom_name(),
    8: Emoji.objects.get(name="wipe 100").discord_tag_custom_name(),  # Full health
}
EMBED_COLOR = {
    "raid": 7930903,
    "strike": 6603422,
    "fractal": 5512822,
    "cerus_cm": 7930903,
}
PLAYER_EMOTES = {
    "core": Emoji.objects.get(name="core").discord_tag(),
    "friend": Emoji.objects.get(name="friend").discord_tag(),
    "pug": Emoji.objects.get(name="pug").discord_tag(),
}


def create_rank_emote_dict(custom_emoji_name: bool, invalid: bool):
    tag = "discord_tag"
    if custom_emoji_name:
        tag = "discord_tag_custom_name"

    invalid_str = ""
    if invalid:
        invalid_str = " invalid"

    d = {
        0: f"{getattr(Emoji.objects.get(name=f'first{invalid_str}'), tag)()}",
        1: f"{getattr(Emoji.objects.get(name=f'second{invalid_str}'), tag)()}",
        2: f"{getattr(Emoji.objects.get(name=f'third{invalid_str}'), tag)()}",
        "above_average": f"{Emoji.objects.get(name=f'above average{invalid_str}').discord_tag_custom_name()}".format(
            settings.MEAN_OR_MEDIAN
        ),
        "below_average": f"{Emoji.objects.get(name=f'below average{invalid_str}').discord_tag_custom_name()}".format(
            settings.MEAN_OR_MEDIAN
        ),
        "average": f"{Emoji.objects.get(name=f'average{invalid_str}').discord_tag_custom_name()}".format(
            settings.MEAN_OR_MEDIAN
        ),
        "emboldened": f"{Emoji.objects.get(name='emboldened').discord_tag()}",
    }
    return d


def create_rank_emote_dict_percentiles(custom_emoji_name: bool, invalid: bool):
    tag = "discord_tag"
    if custom_emoji_name:
        tag = "discord_tag_custom_name"

    invalid_str = ""
    if invalid:
        invalid_str = " invalid"
    # RANK_BINS_PERCENTILE=[20, 40, 50, 60, 70, 80, 90, 100] # in .env

    d = {
        0: f"{getattr(Emoji.objects.get(name='1_junk'), tag)()}".format("bin20_percrank{}"),
        1: f"{getattr(Emoji.objects.get(name='2_basic'), tag)()}".format("bin40_percrank{}"),
        2: f"{getattr(Emoji.objects.get(name='3_fine'), tag)()}".format("bin50_percrank{}"),
        3: f"{getattr(Emoji.objects.get(name='4_masterwork'), tag)()}".format("bin60_percrank{}"),
        4: f"{getattr(Emoji.objects.get(name='5_rare'), tag)()}".format("bin70_percrank{}"),
        5: f"{getattr(Emoji.objects.get(name='6_exotic'), tag)()}".format("bin80_percrank{}"),
        6: f"{getattr(Emoji.objects.get(name='7_ascended'), tag)()}".format("bin90_percrank{}"),
        7: f"{getattr(Emoji.objects.get(name='8_legendary'), tag)()}".format("bin100_percrank{}"),
        "above_average": f"{Emoji.objects.get(name=f'above average{invalid_str}').discord_tag_custom_name()}".format(
            settings.MEAN_OR_MEDIAN
        ),
        "below_average": f"{Emoji.objects.get(name=f'below average{invalid_str}').discord_tag_custom_name()}".format(
            settings.MEAN_OR_MEDIAN
        ),
        "average": f"{Emoji.objects.get(name=f'average{invalid_str}').discord_tag_custom_name()}".format(
            settings.MEAN_OR_MEDIAN
        ),
        "emboldened": f"{Emoji.objects.get(name='emboldened').discord_tag()}",
    }
    return d


def create_rank_emote_dict_newgame(custom_emoji_name: bool, invalid: bool):
    """4 rank bins, green + red and filled + line."""
    tag = "discord_tag"
    if custom_emoji_name:
        tag = "discord_tag_custom_name"

    invalid_str = ""
    if invalid:
        invalid_str = " invalid"

    d = {
        0: f"{getattr(Emoji.objects.get(name='red_full_medal'), tag)()}".format("r{}_of{}_percrank{}"),
        1: f"{getattr(Emoji.objects.get(name='red_line_medal'), tag)()}".format("r{}_of{}_percrank{}"),
        2: f"{getattr(Emoji.objects.get(name='green_line_medal'), tag)()}".format("r{}_of{}_percrank{}"),
        3: f"{getattr(Emoji.objects.get(name='green_full_medal'), tag)()}".format("r{}_of{}_percrank{}"),
        "above_average": f"{Emoji.objects.get(name=f'above average{invalid_str}').discord_tag_custom_name()}".format(
            settings.MEAN_OR_MEDIAN
        ),
        "below_average": f"{Emoji.objects.get(name=f'below average{invalid_str}').discord_tag_custom_name()}".format(
            settings.MEAN_OR_MEDIAN
        ),
        "average": f"{Emoji.objects.get(name='blank').discord_tag_custom_name()}".format(settings.MEAN_OR_MEDIAN),
        "emboldened": f"{Emoji.objects.get(name='emboldened').discord_tag()}",
    }
    return d


if settings.MEDALS_TYPE == "original":
    rank_func = create_rank_emote_dict
elif settings.MEDALS_TYPE == "percentile":
    rank_func = create_rank_emote_dict_percentiles
elif settings.MEDALS_TYPE == "newgame":
    rank_func = create_rank_emote_dict_newgame
else:
    raise ValueError(
        f"MEDALS_TYPE = {settings.MEDALS_TYPE} in .env is unknown. Choose from ['original', 'percentile', 'newgame']"
    )

RANK_EMOTES = rank_func(custom_emoji_name=False, invalid=False)
RANK_EMOTES_INVALID = rank_func(custom_emoji_name=False, invalid=True)
RANK_EMOTES_CUSTOM = rank_func(custom_emoji_name=True, invalid=False)
RANK_EMOTES_CUSTOM_INVALID = rank_func(custom_emoji_name=True, invalid=True)

RANK_EMOTES_CUPS = {
    1: Emoji.objects.get(name="trophy_gold").discord_tag_custom_name().format("r{}_of{}_faster{}s"),
    2: Emoji.objects.get(name="trophy_silver").discord_tag_custom_name().format("r{}_of{}_faster{}s"),
    3: Emoji.objects.get(name="trophy_bronze").discord_tag_custom_name().format("r{}_of{}_faster{}s"),
}


BLANK_EMOTE = Emoji.objects.get(name="blank").discord_tag()
# Combine raids and strikes into the same group.

WEBHOOKS = settings.WEBHOOKS

# Strikes and raids are combined in the same message when they are posted to the same channel
if WEBHOOKS["raid"] == WEBHOOKS["strike"]:
    ITYPE_GROUPS = {
        "raid": ["raid", "strike"],
        "strike": ["raid", "strike"],
        "fractal": ["fractal"],
    }
else:
    ITYPE_GROUPS = {
        "raid": ["raid"],
        "strike": ["strike"],
        "fractal": ["fractal"],
    }


@dataclass
class Thread:
    """Discordpy seems to be rather picky about threads.
    When sending a message it just needs a class with an id
    to work. So here we are.
    """

    id: int


def create_unix_time(t):
    tz = pytz.timezone(str(get_localzone()))
    t = t.astimezone(tz=tz)
    return int(time.mktime(t.timetuple()))


def create_discord_time(t: datetime.datetime):
    """time.mktime uses local time while the times in django are in utc.
    So we need to convert and then make discord str of it
    """
    return f"<t:{create_unix_time(t)}:t>"


def get_duration_str(seconds: int, add_space: bool = False):
    """Get seconds with datetime.timedelta.seconds"""
    mins, secs = divmod(seconds, 60)
    if mins < 60:
        if add_space:
            if len(str(mins)) == 1:
                mins = f" {mins}"
        return f"{mins}:{str(secs).zfill(2)}"

    hours, mins = divmod(mins, 60)
    return f"{hours}:{str(mins).zfill(2)}:{str(secs).zfill(2)}"


def today_y_m_d():
    now = datetime.datetime.now()
    return now.year, now.month, now.day


def zfill_y_m_d(y, m, d):
    return f"{y}{str(m).zfill(2)}{str(d).zfill(2)}"


def get_emboldened_wing(log_date: datetime.datetime):
    """Check if a wing had the possibility of emboldened buff
    Embolded was at wing 6 4th week of 2024
    """
    # FIXME WING8 probably broke this.
    start_year = 2022
    start_week = 26
    start_wing = 1

    year = log_date.year
    week = log_date.isocalendar()[1]

    # Check if the input date is before the start date
    if year < start_year or (year == start_year and week < start_week):
        # The buff 'emboldened' did not start until the 26th week of 2021."
        return False

    # Calculate the total number of weeks passed since the start
    total_weeks_passed = (year - start_year) * 52 + week - start_week

    # Calculate the current wing
    current_wing = (total_weeks_passed % 7) + start_wing
    return current_wing


def get_rank_emote(indiv, group, core_minimum: int, custom_emoji_name=False):
    """Find the rank of the indiv in the group.

    Parameters
    ----------
    indiv: [DpsLog, InstanceClear, InstanceClearGroup]
    group: list[[DpsLog, InstanceClear, InstanceClearGroup]]
    core_minimum : (int)
    custom_emoji_name: Bool
        Return emoji with a format option for the emoji. The returned rank_str
        should be formatted e.g.; rank_str.format("custom_name").
    """

    emboldened = False
    if hasattr(indiv, "emboldened"):
        emboldened = indiv.emboldened

    # When amount of players is below the minimum it will still show rank but with a different emote.
    if indiv.core_player_count < core_minimum:
        if custom_emoji_name:
            emote_dict = RANK_EMOTES_CUSTOM_INVALID
        else:
            emote_dict = RANK_EMOTES_INVALID
    else:
        if custom_emoji_name:
            emote_dict = RANK_EMOTES_CUSTOM
        else:
            emote_dict = RANK_EMOTES

    # Other ranks
    if emboldened:
        rank_str = emote_dict["emboldened"]
    elif not indiv.success:
        rank_str = emote_dict["average"]  # dault rank string
    elif indiv.success:
        rank = group.index(indiv) + 1

        # Top 3
        if rank in [1, 2, 3]:
            # Calculate seconds improvement over previous ranked log;
            try:
                dur_sec = (group[rank].duration - indiv.duration).seconds
                dur_micro = (group[rank].duration - indiv.duration).microseconds / 1e6
                dur = str(round(dur_sec + dur_micro, 1)).replace(".", "_")
            except IndexError:
                dur = "_inf_"

            # e.g. 1_2s_r1_of10 -> 1.2 seconds faster than rank 2, rank 1 of 10 logs
            rank_str = RANK_EMOTES_CUPS[rank].format(rank, len(group), dur)

        else:
            if indiv.success:
                if settings.MEDALS_TYPE == "original":
                    if indiv.duration.seconds < (
                        getattr(np, settings.MEAN_OR_MEDIAN)([i.duration.seconds for i in group]) - 5
                    ):
                        rank_str = emote_dict["above_average"]
                    elif indiv.duration.seconds > (
                        getattr(np, settings.MEAN_OR_MEDIAN)([i.duration.seconds for i in group]) + 5
                    ):
                        rank_str = emote_dict["below_average"]

                else:
                    inverse_rank = group[::-1].index(indiv)
                    percentile_rank = (inverse_rank) / len(group) * 100
                    rank_binned = np.searchsorted(settings.RANK_BINS_PERCENTILE, percentile_rank, side="left")
                    # Fill percrank and samples
                    rank_str = RANK_EMOTES_CUSTOM[rank_binned].format(
                        rank,
                        len(group),
                        int(percentile_rank),
                    )

    return rank_str


def create_folder_names(itype_groups: list):
    """Create list of possible folder names for the selected itype_group.
    This makes it possible to filter logs before uploading them.
    """
    if itype_groups in [None, []]:
        itype_groups = [i[0] for i in InstanceGroup.objects.all().values_list("name")]

    # Create df of encounter foldernames and boss_ids
    encounter_folders = Encounter.objects.all().values_list(
        "folder_names", "dpsreport_boss_id", "instance__instance_group__name"
    )
    enc_df = pd.DataFrame(encounter_folders, columns=["folder", "boss_id", "itype"])

    # Create a list of all possible folder names with selected itype_groups
    folder_names = enc_df[enc_df["itype"].isin(itype_groups)][["folder", "boss_id"]].to_numpy().tolist()
    folder_names = list(chain(*[str(i).split(";") for i in chain(*folder_names)]))
    return folder_names


def get_rank_duration_str(indiv, group, itype, pretty_time: bool = False, url=None):
    """Find rank of indiv instance in group. And add duration to string.

    pretty_time (bool):
        replace the rank string with a pretty time.
    """
    duration_str = get_duration_str(indiv.duration.seconds, add_space=True)

    rank_str = get_rank_emote(
        indiv=indiv, group=list(group), core_minimum=settings.CORE_MINIMUM[itype], custom_emoji_name=pretty_time
    )

    if pretty_time:
        if hasattr(indiv, "instance_clears"):
            replace_str = indiv.instance_clears.first().dps_logs.first().pretty_time.replace(" ", "_")
        elif hasattr(indiv, "dps_logs"):
            replace_str = indiv.dps_logs.first().pretty_time.replace(" ", "_")
        else:
            replace_str = indiv.pretty_time.replace(" ", "_")

        rank_str = rank_str.format(replace_str)

    if url:
        return f"[{rank_str}]({url})`{duration_str}` "
    return f"{rank_str}`{duration_str}` "


def get_avg_duration_str(group):
    """Create string with rank emote and average duration"""
    avg_time = int(getattr(np, settings.MEAN_OR_MEDIAN)([e[0].seconds for e in group.values_list("duration")]))
    avg_duration_str = get_duration_str(avg_time, add_space=True)
    return f"{RANK_EMOTES['average']}`{avg_duration_str}`"


def create_or_update_discord_message(
    group: Union[Instance, InstanceGroup, InstanceClearGroup],
    hook,
    embeds_mes: list,
    thread=MISSING,
):
    """Send message to discord

    group: instance_group or iclear_group
    hook: log_helper.WEBHOOK[itype]
    embeds_mes: [Embed, Embed]
    thread: Thread(settings.LEADERBOARD_THREADS[itype])
    discord_message:
        When none, read from the group. Provided to update a current message
        for instance, when updating the FAST channel.
    """

    webhook = SyncWebhook.from_url(hook)

    # Try to update message. If message cant be found, create a new message instead.
    try:
        discord_message = group.discord_message

        webhook.edit_message(
            message_id=discord_message.message_id,
            embeds=embeds_mes,
            thread=thread,
        )

        discord_message.increase_counter()
        logger.info(f"Updating discord message: {discord_message.name}")

    except (AttributeError, discord.errors.NotFound, discord.errors.HTTPException):
        mess = webhook.send(wait=True, embeds=embeds_mes, thread=thread)

        if isinstance(group, Instance):
            name = f"leaderboard_{group.instance_group.name}{group.nr}"
        elif isinstance(group, InstanceGroup):
            name = f"leaderboard_{group.name}_all"
        elif isinstance(group, InstanceClearGroup):
            name = group.name

        discord_message = DiscordMessage.objects.create(message_id=mess.id, name=name)
        discord_message.increase_counter()
        group.discord_message = discord_message
        group.save()
        logger.info(f"New discord message created: {discord_message.name}")


def create_or_update_discord_message_current_week(
    group,
    hook,
    embeds_mes: list,
    thread=MISSING,
    discord_message: Optional[DiscordMessage] = None,
):
    """Send message to discord. This will update or create the message in the current
    week channel. This channel only holds logs for the current week.

    Parameters
    ----------
    group: iclear_group
    hook: log_helper.WEBHOOK[itype]
    embeds_mes: [Embed, Embed]
    thread: Thread(settings.LEADERBOARD_THREADS[itype])
    discord_message:
        When none, read from the group. Provided to update a current message
        for instance, when updating the FAST channel.
    """

    weekdate = int(f"{group.start_time.strftime('%Y%V')}")  # e.g. 202510 -> year2025, week10
    weekdate_current = int(f"{datetime.date.today().strftime('%Y%V')}")

    # Only update current week.
    if weekdate == weekdate_current:
        # Remove old messages from previous weeks from the channel
        dms = DiscordMessage.objects.filter(weekdate__lt=weekdate_current)
        for dm in dms:
            if dm.message_id is not None:
                logger.info(f"Removing discord message {dm.message_id} from date {dm.weekdate}")
                webhook = SyncWebhook.from_url(settings.WEBHOOKS_CURRENT_WEEK[group.type])
                webhook.delete_message(dm.message_id)
                dm.message_id = None
                dm.weekdate = None
                dm.save()

        # Update the message weekdate
        day_str = group.start_time.strftime("%a")
        message_name = f"current_week_message_{day_str}"
        discord_message, created = DiscordMessage.objects.get_or_create(name=message_name)
        if discord_message.weekdate is None:
            discord_message.weekdate = weekdate
            discord_message.save()

        webhook = SyncWebhook.from_url(hook)

        # Try to update message. If message cant be found, create a new message instead.
        try:
            webhook.edit_message(
                message_id=discord_message.message_id,
                embeds=embeds_mes,
                thread=thread,
            )

            discord_message.increase_counter()
            logger.info(f"Updating discord message: {discord_message.name}")

        except (AttributeError, discord.errors.NotFound, discord.errors.HTTPException):
            mess = webhook.send(wait=True, embeds=embeds_mes, thread=thread)

            discord_message.message_id = mess.id
            discord_message.increase_counter()
            discord_message.save()

            logger.info(f"New discord message created: {discord_message.name}")


# %%
