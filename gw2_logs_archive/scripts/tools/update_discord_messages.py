# %%
"""Tool to update discord messages for a given date"""

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime

from gw2_logs.models import InstanceClearGroup
from scripts.log_helpers import today_y_m_d
from scripts.model_interactions.instance_clear_group import InstanceClearGroupInteraction


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
    # y, m, d = 2025, 3, 6
    # y, m, d = 2025, 2, 24
    # y, m, d = 2025, 2, 27
    y, m, d = today_y_m_d()
    itype_group = "raid"

    # update_discord_message_single(y=y, m=m, d=d)
    update_discord_messages_from_date(y=y, m=m, d=d)

# %%
