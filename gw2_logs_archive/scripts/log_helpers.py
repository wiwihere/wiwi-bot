# %%
"""Helper functions and variables"""

import datetime
import os
import time
from dataclasses import dataclass
from itertools import chain

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)

from pathlib import Path

import discord
import numpy as np
import pandas as pd
import pytz
from bot_settings import settings
from discord import SyncWebhook
from discord.utils import MISSING
from gw2_logs.models import DiscordMessage, Emoji, Encounter, InstanceGroup, Player
from tzlocal import get_localzone

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
        0: f"{getattr(Emoji.objects.get(name='red_full_medal'), tag)()}".format("bin25_percrank{}"),
        1: f"{getattr(Emoji.objects.get(name='red_line_medal'), tag)()}".format("bin50_percrank{}"),
        2: f"{getattr(Emoji.objects.get(name='green_line_medal'), tag)()}".format("bin75_percrank{}"),
        3: f"{getattr(Emoji.objects.get(name='green_full_medal'), tag)()}".format("bin100_percrank{}"),
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
    0: Emoji.objects.get(name="trophy_gold").discord_tag(),
    1: Emoji.objects.get(name="trophy_silver").discord_tag(),
    2: Emoji.objects.get(name="trophy_bronze").discord_tag(),
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


def find_log_by_date(log_dirs, y, m, d) -> list[Path]:
    """Find all log files on a specific date.
    Returns sorted list on maketime
    """
    # return log_dir.rglob(f"{zfill_y_m_d(y,m,d)}*.zevtc")
    log_paths = list(chain(*(log_dir.rglob(f"{zfill_y_m_d(y, m, d)}*.zevtc") for log_dir in log_dirs)))
    return sorted(log_paths, key=os.path.getmtime)


def get_emboldened_wing(log_date: datetime.datetime):
    """Check if a wing had the possibility of emboldened buff
    Embolded was at wing 6 4th week of 2024
    """
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

    if indiv.success and not emboldened:
        rank = group.index(indiv)
    else:
        rank = None

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
    # Ranks 1, 2 and 3.
    elif rank in [0, 1, 2]:
        rank_str = RANK_EMOTES_CUPS[rank]

    else:
        rank_str = emote_dict["average"]
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
                percentile_rank = (inverse_rank + 1) / len(group) * 100
                rank_binned = np.searchsorted(settings.RANK_BINS_PERCENTILE, percentile_rank, side="left")
                rank_str = RANK_EMOTES_CUSTOM[rank_binned].format(int(percentile_rank))

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


def create_or_update_discord_message(group, hook, embeds_mes: list, thread=MISSING):
    """Send message to discord

    group: instance_group or iclear_group
    hook: log_helper.WEBHOOK[itype]
    embeds_mes: [Embed, Embed]
    thread: Thread(settings.LEADERBOARD_THREADS[itype])
    """

    webhook = SyncWebhook.from_url(hook)

    # Try to update message. If message cant be found, create a new message instead.
    try:
        webhook.edit_message(
            message_id=group.discord_message.message_id,
            embeds=embeds_mes,
            thread=thread,
        )
        print(f"Updating discord message: {group.name}")

    except (AttributeError, discord.errors.NotFound, discord.errors.HTTPException):
        mess = webhook.send(wait=True, embeds=embeds_mes, thread=thread)
        disc_mess = DiscordMessage.objects.create(message_id=mess.id)
        group.discord_message = disc_mess
        group.save()
        print(f"New discord message created: {group.name}")
