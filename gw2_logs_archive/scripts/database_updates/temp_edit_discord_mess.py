# %%
import datetime
import logging
import os
import time
from dataclasses import dataclass
from itertools import chain
from typing import Union

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
# %%
# Add name to discord messages
for obj in DiscordMessage.objects.all():
    if obj.name is None:
        if obj.instance.first():
            group = obj.instance.first()
            obj.name = f"leaderboard_{group.instance_group.name}{group.nr}"
            obj.save()
        elif obj.instance_group.first():
            group = obj.instance_group.first()
            obj.name = f"leaderboard_{group.name}_all"
            obj.save()
        elif obj.instance_clear_group.first():
            obj.name = obj.instance_clear_group.first().name
            obj.save()
        else:
            logger.warning(f"Probably delete {obj.id}: {obj.name}")
            continue

        logger.info(f"{obj.id}: {obj.name}")

# %% Migrate discord_message_id_old
for obj in InstanceClearGroup.objects.all():
    dm = None
    if obj.discord_message_id_old is not None:
        try:
            dm = DiscordMessage.objects.get(name=obj.name)

        except DiscordMessage.DoesNotExist:
            logger.warning(f"Making dm {obj.id}: {obj.name}")

            dm = DiscordMessage.objects.create(message_id=obj.discord_message_id_old, name=obj.name)
            dm.increase_counter()

        if dm.message_id == obj.discord_message_id_old:
            obj.discord_message_id_old = None
            obj.save()
            logger.info(f"{obj.id}: {obj.name}")


# %% Migrate discord_message_id_old
for obj in InstanceClearGroup.objects.all():
    dm = None
    if obj.discord_message is None:
        try:
            dm = DiscordMessage.objects.get(name=obj.name)
            obj.discord_message = dm
            obj.save()
            logger.info(f"{obj.id}: {obj.name}")

        except DiscordMessage.DoesNotExist:
            name = obj.name.replace("strikes", "raids")
            dm = DiscordMessage.objects.get(name=name)
            obj.discord_message = dm
            obj.save()
            logger.warning(f"Ehh {obj.id}: {obj.name}")
