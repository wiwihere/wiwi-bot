# %%
"""Tool to update discord messages for a given date"""

import datetime

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)

from gw2_logs.models import (
    InstanceClearGroup,
)
from scripts.log_instance_interaction import InstanceClearGroupInteraction


def update_discord_message_single(y, m, d, itype_group="raid"):
    """Update single discord message. Doesnt upload any logs"""
    self = icgi = InstanceClearGroupInteraction.create_from_date(y=y, m=m, d=d, itype_group=itype_group)
    # self = icgi = InstanceClearGroupInteraction.from_name("dummy")
    icgi.send_discord_message()


def update_discord_messages_from_date(y, m, d):
    """Update discord messages from a certain date onwards"""
    icgs = InstanceClearGroup.objects.filter(
        start_time__gte=datetime.datetime(year=y, month=m, day=d, tzinfo=datetime.timezone.utc)
    ).order_by("start_time")

    for icg in icgs:
        icgi = InstanceClearGroupInteraction.from_name(name=icg.name)
        icgi.send_discord_message()


def update_discord_messages_all():
    """Update discord messages for all instances"""
    for icg in InstanceClearGroup.objects.all().order_by("start_time"):
        icgi = InstanceClearGroupInteraction.from_name(name=icg.name)
        icgi.send_discord_message()


# %%
if __name__ == "__main__":
    y, m, d = 2025, 2, 6
    itype_group = "raid"

    # update_discord_messages_from_date(y=y, m=m, d=d)
