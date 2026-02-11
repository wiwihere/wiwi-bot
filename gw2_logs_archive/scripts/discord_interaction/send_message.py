# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import logging
from dataclasses import dataclass
from functools import cached_property
from typing import Optional, Tuple, Union

import discord
from discord import SyncWebhook
from discord.utils import MISSING
from gw2_logs.models import (
    DiscordMessage,
    Instance,
    InstanceClearGroup,
    InstanceGroup,
)

logger = logging.getLogger(__name__)


@dataclass
class Thread:
    """Discordpy seems to be rather picky about threads.
    Initializing with id on the discord.Thread doesnt work.
    When sending a message it however just needs a class with an id
    to work. So this represents that discord.Thread class.
    """

    id: int


class Webhook:
    def __init__(self, webhook_url: str):
        self.url = webhook_url

    @cached_property
    def webhook(self) -> SyncWebhook:
        return SyncWebhook.from_url(self.url)

    def _validate_thread(
        self,
        thread: Optional[discord.Thread] = None,
    ) -> Union[Thread, discord.utils._MissingSentinel]:
        """Replace missing thread with the correct MISSING value."""
        if thread is None:
            thread = MISSING
        return thread

    def edit_message(
        self,
        discord_message: DiscordMessage,
        embeds_messages_list: list[discord.Embed],
        thread: Optional[Thread] = None,
    ) -> None:
        """Edit message. If this fails, a new message must be created."""
        thread = self._validate_thread(thread)

        if discord_message is None:
            raise ValueError("DiscordMessage not found")
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
        discord_message_name: str,
        thread: Optional[Thread] = None,
    ) -> DiscordMessage:
        """Create new message on discord and create an instance in django database

        Parameters
        ----------
        embeds_messages_list: list[discord.Embed]
            List of embeds to send
        name: str
            Name of the discord message in the django database
        thread: Optional[Thread]
            Thread to send the message in
        """
        thread = self._validate_thread(thread)

        # Send message
        mess = self.webhook.send(wait=True, embeds=embeds_messages_list, thread=thread)

        # Get or create in django database
        discord_message, created = DiscordMessage.objects.get_or_create(name=discord_message_name)
        discord_message.increase_counter()

        if discord_message.message_id != mess.id:
            discord_message.message_id = mess.id
            discord_message.save()

        logger.info(f"Sent new discord message: {discord_message.name}")
        return discord_message

    def delete_message(self, discord_message: DiscordMessage) -> None:
        """Delete message from discord. Set .message_id and .weekdate to None"""
        message = f"Removing message on discord {discord_message.message_id}"
        if discord_message.weekdate:
            message += f" from date {discord_message.weekdate}"
        logger.info(message)

        # Delete message
        try:
            self.webhook.delete_message(discord_message.message_id)
        except discord.NotFound:
            logger.warning(
                f"Message {discord_message.message_id} not found on discord. It might have been already deleted."
            )

        # Update django database
        discord_message.message_id = None
        discord_message.weekdate = None
        discord_message.save()


def create_or_update_discord_message(
    group: Union[Instance, InstanceGroup, InstanceClearGroup],
    webhook_url: str,
    embeds_messages_list: list[discord.Embed],
    thread: Optional[Thread] = None,
) -> None:
    """
    Send message to discord using a group.

    Parameters
    ----------
    group : Union[Instance, InstanceGroup, InstanceClearGroup, str]
        The group object or string identifier for navigation
    webhook_url : str
        Webhook URL from log_helper.WEBHOOK[itype]
    embeds_messages_list : list[discord.Embed]
        List of embeds to send
    thread : Optional[Thread]
        Thread to send message in (from settings.LEADERBOARD_THREADS[itype])
    """

    discord_message = group.discord_message

    if isinstance(group, Instance):
        discord_message_name = f"leaderboard_{group.instance_group.name}{group.nr}"
    elif isinstance(group, InstanceGroup):
        discord_message_name = f"leaderboard_{group.name}_all"
    elif isinstance(group, InstanceClearGroup):
        discord_message_name = group.name

    discord_message, created = send_discord_message(
        discord_message=discord_message,
        discord_message_name=discord_message_name,
        webhook_url=webhook_url,
        embeds_messages_list=embeds_messages_list,
        thread=thread,
    )

    if created:
        group.discord_message = discord_message
        group.save()


def send_discord_message(
    discord_message: DiscordMessage,
    discord_message_name: str,  # discord_message.name
    webhook_url: str,
    embeds_messages_list: list[discord.Embed],
    thread: Optional[Thread] = None,
) -> Tuple[DiscordMessage, bool]:
    """
    Send message to discord using a discord message

    Parameters
    ----------
    group : Union[Instance, InstanceGroup, InstanceClearGroup, str]
        The group object or string identifier for navigation
    webhook_url : str
        Webhook URL from log_helper.WEBHOOK[itype]
    embeds_messages_list : list[discord.Embed]
        List of embeds to send
    thread : Optional[Thread]
        Thread to send message in (from settings.LEADERBOARD_THREADS[itype])
    """
    webhook = Webhook(webhook_url)

    try:
        # Try to update message. If message cant be found, create a new message instead.
        webhook.edit_message(
            discord_message=discord_message,
            embeds_messages_list=embeds_messages_list,
            thread=thread,
        )
        created = False

    except (ValueError, discord.errors.NotFound, discord.errors.HTTPException):
        discord_message = webhook.send_message(
            embeds_messages_list=embeds_messages_list,
            discord_message_name=discord_message_name,
            thread=thread,
        )
        created = True
    return discord_message, created


def create_or_update_discord_message_current_week(
    iclear_group: InstanceClearGroup,
    webhook_url: str,  # html url to api webhook
    embeds_messages_list: list[discord.Embed],
    thread: Optional[Thread] = None,
):
    """Send message to discord. This will update or create the message in the current
    week channel. This channel only holds logs for the current week.

    Parameters
    ----------
    iclear_group: InstanceClearGroup
    webhook_url: log_helper.WEBHOOK[itype]
    embeds_messages_list: [Embed, Embed]
    thread: Optional[Thread]
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
                discord_message_name=message_name,
                thread=thread,
            )

            if discord_message.weekdate is None:
                discord_message.weekdate = weekdate
                discord_message.save()

    else:
        logger.info("current_week message not updated")
