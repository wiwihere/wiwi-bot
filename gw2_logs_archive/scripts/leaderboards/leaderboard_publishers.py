# %%

"""Publish leaderboards to Discord."""

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging
from typing import Literal

from django.conf import settings
from gw2_logs.models import (
    Instance,
    InstanceGroup,
)
from scripts.discord_interaction.send_message import Thread, create_or_update_discord_message
from scripts.leaderboards.create_embeds import create_fullclear_leaderboard_embed, create_instance_leaderboard_embed
from scripts.log_helpers import (
    WEBHOOKS,
)
from scripts.model_interactions.instance import InstanceInteraction
from scripts.model_interactions.instance_group import InstanceGroupInteraction

logger = logging.getLogger(__name__)


def publish_instance_leaderboard_messages(instance_type: Literal["raid", "strike", "fractal"]) -> None:
    """
    Create and publish leaderboards on discord for all instances of a given type.

    Parameters
    ----------
    instance_type: {'raid', 'strike', 'fractal'}
        Type of instances to publish leaderboards for
    """
    instances = Instance.objects.filter(instance_group__name=instance_type).order_by("nr")

    for instance in instances:
        instance_interaction = InstanceInteraction(instance)
        embed = create_instance_leaderboard_embed(instance_interaction=instance_interaction)

        create_or_update_discord_message(
            group=instance,
            webhook_url=WEBHOOKS["leaderboard"],
            embeds_messages_list=[embed],
            thread=Thread(settings.LEADERBOARD_THREADS[instance_type]),
        )


def publish_fullclear_message(instance_type: Literal["raid", "strike", "fractal"]):
    """
    Publish full clear leaderboard for given type to Discord.

    Creates single message showing all instances combined with rankings.

    Parameters
    ----------
    instance_type : {'raid', 'strike', 'fractal'}
        Type of instance group to publish
    """
    instance_group = InstanceGroup.objects.get(name=instance_type)
    instance_group_interaction = InstanceGroupInteraction(instance_group)

    embed = create_fullclear_leaderboard_embed(instance_group_interaction=instance_group_interaction)

    create_or_update_discord_message(
        group=instance_group,
        webhook_url=WEBHOOKS["leaderboard"],
        embeds_messages_list=[embed],
        thread=Thread(settings.LEADERBOARD_THREADS[instance_group_interaction.instance_type]),
    )
