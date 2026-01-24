# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import logging
from functools import cached_property
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


class Webhook:
    def __init__(self, webhook_url: str):
        self.url = webhook_url

    @cached_property
    def webhook(self) -> SyncWebhook:
        return SyncWebhook.from_url(self.url)

    def _validate_thread(
        self,
        thread: Optional[discord.Thread] = None,
    ) -> Union[discord.Thread, discord.utils._MissingSentinel]:
        """Replace missing thread with the correct MISSING value."""
        if thread is None:
            thread = MISSING
        return thread

    def edit_message(
        self,
        discord_message: DiscordMessage,
        embeds_messages_list: list[discord.Embed],
        thread: Optional[discord.Thread] = None,
    ) -> None:
        """Edit message. If this fails, a new message must be created."""
        thread = self._validate_thread(thread)

        if not discord_message.message_id:
            raise ValueError("DiscordMessage cant edit message without message_id")

        # Edit message
        self.webhook.edit_message(
            message_id=discord_message.message_id,
            embeds=embeds_messages_list,
            thread=thread,
        )

        # Update in django database
        discord_message.increase_counter()
        logger.info(f"Updating discord message: {discord_message.name}")

    def send_message(
        self,
        embeds_messages_list: list[discord.Embed],
        name: str,
        thread: Optional[discord.Thread] = None,
    ) -> DiscordMessage:
        """Create new message on discord and create an instance in django database"""
        thread = self._validate_thread(thread)

        # Send message
        mess = self.webhook.send(wait=True, embeds=embeds_messages_list, thread=thread)

        # Get or create in django database
        discord_message, created = DiscordMessage.objects.get_or_create(name=name)
        discord_message.message_id = mess.id
        discord_message.increase_counter()
        discord_message.save()

        logger.info(f"Sent new discord message: {discord_message.name}")
        return discord_message

    def delete_message(self, discord_message: DiscordMessage) -> None:
        """Delete message from discord. Set .message_id and .weekdate to None"""
        if discord_message.weekdate:
            message = f"Removing discord message {discord_message.message_id} from date {discord_message.weekdate}"
        else:
            message = f"Removing discord message {discord_message.message_id}"
        logger.info(message)

        # Delete message
        self.webhook.delete_message(discord_message.message_id)

        # Update django database
        discord_message.message_id = None
        discord_message.weekdate = None
        discord_message.save()


def create_or_update_discord_message(
    group: Union[Instance, InstanceGroup, InstanceClearGroup],
    webhook_url: str,
    embeds_messages_list: list[discord.Embed],
    thread: Optional[discord.Thread] = None,
) -> None:
    """Send message to discord

    group: Union[Instance, InstanceGroup, InstanceClearGroup]
    webhook_url: log_helper.WEBHOOK[itype]
    embeds_messages_list: list[discord.Embed]
    thread: Thread(settings.LEADERBOARD_THREADS[itype])
    """

    webhook = Webhook(webhook_url)

    # Try to update message. If message cant be found, create a new message instead.
    try:
        discord_message = group.discord_message

        webhook.edit_message(
            discord_message=discord_message,
            embeds_messages_list=embeds_messages_list,
            thread=thread,
        )

    except (ValueError, discord.errors.NotFound, discord.errors.HTTPException):
        if isinstance(group, Instance):
            message_name = f"leaderboard_{group.instance_group.name}{group.nr}"
        elif isinstance(group, InstanceGroup):
            message_name = f"leaderboard_{group.name}_all"
        elif isinstance(group, InstanceClearGroup):
            message_name = group.name

        discord_message = webhook.send_message(
            embeds_messages_list=embeds_messages_list,
            name=message_name,
            thread=thread,
        )

        group.discord_message = discord_message
        group.save()


def create_or_update_discord_message_current_week(
    iclear_group: InstanceClearGroup,
    webhook_url: str,  # html url to api webhook
    embeds_messages_list: list[discord.Embed],
    thread: Optional[discord.Thread] = None,
):
    """Send message to discord. This will update or create the message in the current
    week channel. This channel only holds logs for the current week.

    Parameters
    ----------
    iclear_group: InstanceClearGroup
    webhook_url: log_helper.WEBHOOK[itype]
    embeds_messages_list: [Embed, Embed]
    thread: Optional[discord.Thread]
    """

    weekdate = int(f"{iclear_group.start_time.strftime('%Y%V')}")  # e.g. 202510 -> year2025, week10
    weekdate_current = int(f"{datetime.date.today().strftime('%Y%V')}")

    # Only update current week.
    if weekdate == weekdate_current:
        webhook = Webhook(webhook_url)

        # Remove old messages from previous weeks from the channel
        dms = DiscordMessage.objects.filter(weekdate__lt=weekdate_current)
        for dm in dms:
            if dm.message_id is not None:
                webhook.delete_message(discord_message=dm)

        # Update the message weekdate
        day_str = iclear_group.start_time.strftime("%a")
        message_name = f"current_week_message_{day_str}"
        discord_message, created = DiscordMessage.objects.get_or_create(name=message_name)

        # Try to update message. If message cant be found, create a new message instead.
        try:
            webhook.edit_message(
                discord_message=discord_message,
                embeds_messages_list=embeds_messages_list,
                thread=thread,
            )

        except (ValueError, discord.errors.NotFound, discord.errors.HTTPException):
            discord_message = webhook.send_message(
                embeds_messages_list=embeds_messages_list,
                name=message_name,
                thread=thread,
            )

            if discord_message.weekdate is None:
                discord_message.weekdate = weekdate
                discord_message.save()

    else:
        logger.info("current_week message not updated")
