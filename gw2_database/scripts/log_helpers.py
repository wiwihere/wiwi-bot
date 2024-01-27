# %%
"""Helper functions and variables"""
import datetime
import time

import numpy as np
import pytz
from gw2_logs.models import Emoji
from tzlocal import get_localzone

WIPE_EMOTES = {
    1: Emoji.objects.get(name="skull_1_8").discord_tag,  # Between 0 and 12.5%
    2: Emoji.objects.get(name="skull_2_8").discord_tag,
    3: Emoji.objects.get(name="skull_3_8").discord_tag,
    4: Emoji.objects.get(name="skull_4_8").discord_tag,
    5: Emoji.objects.get(name="skull_5_8").discord_tag,
    6: Emoji.objects.get(name="skull_6_8").discord_tag,
    7: Emoji.objects.get(name="skull_7_8").discord_tag,
    8: Emoji.objects.get(name="skull_8_8").discord_tag,  # Full health
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
    "above_average": f"{Emoji.objects.get(name='above average').discord_tag}",
    "below_average": f"{Emoji.objects.get(name='below average').discord_tag}",
    "average": f"{Emoji.objects.get(name='average').discord_tag}",
    "emboldened": f"{Emoji.objects.get(name='emboldened').discord_tag}",
}


def create_unix_time(t):
    tz = pytz.timezone(str(get_localzone()))
    t = t.astimezone(tz=tz)
    return int(time.mktime(t.timetuple()))


def get_duration_str(seconds: int, colon=True):
    """Get seconds with datetime.timedelta.seconds

    Parameters
    ----------
    colon: bool
        if True returns: 26:08
        if False returns: 1h25m52s
    """
    mins, secs = divmod(seconds, 60)
    if colon:
        return f"{mins}:{str(secs).zfill(2)}"
    hours, mins = divmod(mins, 60)

    return f"{hours}:{mins}:{str(secs).zfill(2)}"


def today_y_m_d():
    now = datetime.datetime.now()
    return now.year, now.month, now.day


def get_fractal_day(y, m, d):
    """Return if logs are fractals.
    By default monday, thursday raids. rest is fractal.
    """
    dt = datetime.datetime(year=y, month=m, day=d)
    wd = dt.weekday()

    # Default raid days
    if wd in [0, 3]:
        return False
    return True


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


def create_rank_str(indiv, group):
    """Find the rank of the indiv in the group.

    Parameters
    ----------
    indiv: [DpsLog, InstanceClear, InstanceClearGroup]
    group: list[[DpsLog, InstanceClear, InstanceClearGroup]]
    """
    if indiv.success:
        rank = group.index(indiv)
    else:
        rank = None

    # Ranks 1, 2 and 3.
    if rank in RANK_EMOTES:
        rank_str = RANK_EMOTES[rank]

        # Strikes as an instance dont have cleartimes.
        if indiv.__class__.__name__ == "InstanceClear":
            if indiv.instance.type == "strike":
                rank_str = RANK_EMOTES["average"]

    # Other ranks
    else:
        rank_str = RANK_EMOTES["average"]
        if indiv.success:
            if indiv.duration.seconds < (np.mean([i.duration.seconds for i in group]) - 5):
                rank_str = RANK_EMOTES["above_average"]
            elif indiv.duration.seconds > (np.mean([i.duration.seconds for i in group]) + 5):
                rank_str = RANK_EMOTES["below_average"]

    if hasattr(indiv, "emboldened"):
        if indiv.emboldened:
            rank_str = RANK_EMOTES["emboldened"]

    return rank_str
