# %%
"""Helper functions and variables"""

import datetime
import time
from dataclasses import dataclass
from itertools import chain

import discord
import numpy as np
import pandas as pd
import pytz
from bot_settings import settings
from discord import SyncWebhook
from discord.utils import MISSING
from gw2_logs.models import DiscordMessage, Emoji, Encounter
from tzlocal import get_localzone

WIPE_EMOTES = {
    0: Emoji.objects.get(name="wipe 13").discord_tag,  # OLC can still be bugged and give 0 health.
    1: Emoji.objects.get(name="wipe 13").discord_tag,  # Between 0 and 12.5%
    2: Emoji.objects.get(name="wipe 25").discord_tag,
    3: Emoji.objects.get(name="wipe 38").discord_tag,
    4: Emoji.objects.get(name="wipe 50").discord_tag,
    5: Emoji.objects.get(name="wipe 63").discord_tag,
    6: Emoji.objects.get(name="wipe 75").discord_tag,
    7: Emoji.objects.get(name="wipe 88").discord_tag,
    8: Emoji.objects.get(name="wipe 100").discord_tag,  # Full health
}
EMBED_COLOR = {
    "raid": 7930903,
    "strike": 6603422,
    "fractal": 5512822,
}
RANK_EMOTES = {
    0: f"{Emoji.objects.get(name='first').discord_tag}",
    1: f"{Emoji.objects.get(name='second').discord_tag}",
    2: f"{Emoji.objects.get(name='third').discord_tag}",
    "above_average": f"{Emoji.objects.get(name='above average').discord_tag}".replace(
        "average", settings.MEAN_OR_MEDIAN
    ),
    "below_average": f"{Emoji.objects.get(name='below average').discord_tag}".replace(
        "average", settings.MEAN_OR_MEDIAN
    ),
    "average": f"{Emoji.objects.get(name='average').discord_tag}".replace("average", settings.MEAN_OR_MEDIAN),
    "emboldened": f"{Emoji.objects.get(name='emboldened').discord_tag}",
}

RANK_EMOTES_INVALID = {
    0: f"{Emoji.objects.get(name='first invalid').discord_tag}",
    1: f"{Emoji.objects.get(name='second invalid').discord_tag}",
    2: f"{Emoji.objects.get(name='third invalid').discord_tag}",
    "above_average": f"{Emoji.objects.get(name='above average invalid').discord_tag}".replace(
        "average", settings.MEAN_OR_MEDIAN
    ),
    "below_average": f"{Emoji.objects.get(name='below average invalid').discord_tag}".replace(
        "average", settings.MEAN_OR_MEDIAN
    ),
    "average": f"{Emoji.objects.get(name='average invalid').discord_tag}".replace("average", settings.MEAN_OR_MEDIAN),
    "emboldened": f"{Emoji.objects.get(name='emboldened').discord_tag}",
}
BLANK_EMOTE = Emoji.objects.get(name="blank").discord_tag
# Combine raids and strikes into the same group.

WEBHOOKS = {
    "raid": settings.WEBHOOK_BOT_CHANNEL_RAID,
    "strike": settings.WEBHOOK_BOT_CHANNEL_STRIKE,
    "fractal": settings.WEBHOOK_BOT_CHANNEL_FRACTAL,
    "leaderboard": settings.WEBHOOK_BOT_CHANNEL_LEADERBOARD,
}

# Strikes and raids are combined in the same message when they are posted to the same channel
if settings.WEBHOOK_BOT_CHANNEL_RAID == settings.WEBHOOK_BOT_CHANNEL_STRIKE:
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


def find_log_by_date(log_dir, y, m, d):
    """Find all log files on a specific date.
    Returns generator
    """
    return log_dir.rglob(f"{zfill_y_m_d(y,m,d)}*.zevtc")


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


def get_rank_emote(indiv, group, core_minimum: int):
    """Find the rank of the indiv in the group.

    Parameters
    ----------
    indiv: [DpsLog, InstanceClear, InstanceClearGroup]
    group: list[[DpsLog, InstanceClear, InstanceClearGroup]]
    core_minimum : (int)
    """
    if indiv.success:
        rank = group.index(indiv)
    else:
        rank = None

    # When amount of players is below the minimum it will still show rank but with a different emote.
    if indiv.core_player_count < core_minimum:
        emote_dict = RANK_EMOTES_INVALID
    else:
        emote_dict = RANK_EMOTES

    # Ranks 1, 2 and 3.
    if rank in emote_dict:
        rank_str = emote_dict[rank]

        # FIXME remove this
        # Strikes as an instance dont have cleartimes.
        if indiv.__class__.__name__ == "InstanceClear":
            if indiv.instance.type == "strike":
                rank_str = emote_dict["average"]

    # Other ranks
    else:
        rank_str = emote_dict["average"]
        if indiv.success:
            if indiv.duration.seconds < (
                getattr(np, settings.MEAN_OR_MEDIAN)([i.duration.seconds for i in group]) - 5
            ):
                rank_str = emote_dict["above_average"]
            elif indiv.duration.seconds > (
                getattr(np, settings.MEAN_OR_MEDIAN)([i.duration.seconds for i in group]) + 5
            ):
                rank_str = emote_dict["below_average"]

    if hasattr(indiv, "emboldened"):
        if indiv.emboldened:
            rank_str = emote_dict["emboldened"]

    return rank_str


def create_folder_names(itype_groups: list):
    """Create list of possible folder names for the selected itype_group.
    This makes it possible to filter logs before uploading them.
    """
    if itype_groups is None:
        return
    else:
        # Create df of encounter foldernames and boss_ids
        encounter_folders = Encounter.objects.all().values_list("folder_names", "dpsreport_boss_id", "instance__type")
        enc_df = pd.DataFrame(encounter_folders, columns=["folder", "boss_id", "itype"])

        # Create a list of all possible folder names with selected itype_groups
        folder_names = enc_df[enc_df["itype"].isin(itype_groups)][["folder", "boss_id"]].to_numpy().tolist()
        folder_names = list(chain(*[str(i).split(";") for i in chain(*folder_names)]))
        return folder_names


def get_rank_duration_str(indiv, group, itype):
    """Find rank of indiv instance in group. And add duration to string."""
    duration_str = get_duration_str(indiv.duration.seconds, add_space=True)

    rank_str = get_rank_emote(
        indiv=indiv,
        group=list(group),
        core_minimum=settings.CORE_MINIMUM[itype],
    )
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
