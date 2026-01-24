# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import logging
from typing import Optional, Union

import discord
from discord import SyncWebhook
from discord.utils import MISSING
from django.conf import settings
from gw2_logs.models import (
    DiscordMessage,
    Instance,
    InstanceClearGroup,
    InstanceGroup,
)

logger = logging.getLogger(__name__)


def create_or_update_discord_message(
    group: Union[Instance, InstanceGroup, InstanceClearGroup],
    hook,
    embeds_messages_list: list,
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
            embeds=embeds_messages_list,
            thread=thread,
        )

        discord_message.increase_counter()
        logger.info(f"Updating discord message: {discord_message.name}")

    except (AttributeError, discord.errors.NotFound, discord.errors.HTTPException):
        mess = webhook.send(wait=True, embeds=embeds_messages_list, thread=thread)

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
    embeds_messages_list: list,
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
                embeds=embeds_messages_list,
                thread=thread,
            )

            discord_message.increase_counter()
            logger.info(f"Updating discord message: {discord_message.name}")

        except (AttributeError, discord.errors.NotFound, discord.errors.HTTPException):
            mess = webhook.send(wait=True, embeds=embeds_messages_list, thread=thread)

            discord_message.message_id = mess.id
            discord_message.increase_counter()
            discord_message.save()

            logger.info(f"New discord message created: {discord_message.name}")
