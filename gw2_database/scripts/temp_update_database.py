# %%
import datetime
from dataclasses import dataclass
from itertools import chain

import discord
import numpy as np
import pandas as pd
from discord import SyncWebhook
from django.db.models import Q

if __name__ == "__main__":
    from django_for_jupyter import init_django_from_commands

    init_django_from_commands("gw2_database")
from bot_settings import settings
from gw2_logs.models import (
    DiscordMessage,
    DpsLog,
    Emoji,
    Encounter,
    Instance,
    InstanceClear,
    InstanceClearGroup,
    InstanceClearGroupInteraction,
    Player,
)

# %%

icgs = InstanceClearGroup.objects.filter(name__contains="raids")

for icg in icgs:
    if icg.discord_message_id_old is not None:
        print(icg.name)
        disc_mess, _ = DiscordMessage.objects.update_or_create(message_id=icg.discord_message_id_old)
        icg.discord_message = disc_mess
        icg.save()

        # Create strike counterpart
        InstanceClearGroupInteraction.create_from_date(
            y=icg.start_time.year, m=icg.start_time.month, d=icg.start_time.day, itype_group="strike"
        )
