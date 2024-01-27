# %%
"""Helper functions and variables"""
import datetime
import time

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


def get_duration_str(seconds: int):
    """Get seconds with datetime.timedelta.seconds"""
    mins, secs = divmod(seconds, 60)
    return f"{mins}:{str(secs).zfill(2)}"


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
