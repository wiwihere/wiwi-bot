# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import logging
from typing import Literal

import discord
from django.conf import settings
from django.db.models import Q, QuerySet
from gw2_logs.models import (
    Encounter,
    Instance,
    InstanceGroup,
)
from scripts.discord_interaction.send_message import Thread, create_or_update_discord_message
from scripts.log_helpers import (
    BLANK_EMOTE,
    EMBED_COLOR,
    WEBHOOKS,
    get_avg_duration_str,
    get_rank_duration_str,
)
from scripts.model_interactions.encounter import EncounterInteraction
from scripts.model_interactions.instance import InstanceInteraction
from scripts.model_interactions.instance_group import InstanceGroupInteraction

logger = logging.getLogger(__name__)

DIFFICULTY_CONFIG = {
    "normal": (False, False, "lb"),
    "cm": (True, False, "lb_cm"),
    "lcm": (True, True, "lb_lcm"),
}


def build_fullwingcleartime_message(instance_group_interaction: InstanceGroupInteraction) -> discord.Embed:
    """Build a message that contains one row per instance.
    Each line shows the icons of all bosses included in that instance.
    """
    # Initialize objects
    instances = Instance.objects.filter(instance_group=instance_group_interaction.instance_group).order_by("nr")

    description = ""

    # For each instance add the encounters that are included and their
    # fastest and average killtime
    for instance in instances:
        instance_interaction = InstanceInteraction(instance)
        description += _create_leaderboard_encounters_line(instance_interaction=instance_interaction)

    # List the top 3 of the instance group clear time #

    description += "\n"
    description += create_leaderboard_fullclear_line(instance_group_interaction=instance_group_interaction)
    # Create embed # --------------------------------------------------
    embed = discord.Embed(
        title=f"Full {instance_group_interaction.instance_type.capitalize()} Clear",
        description=description,
        colour=EMBED_COLOR[instance_group_interaction.instance_group.name],
    )
    embed.set_footer(
        text=f"Minimum core count: {instance_group_interaction.instance_group.min_core_count}\nLeaderboard last updated"
    )
    embed.timestamp = datetime.datetime.now()
    return embed


def publish_fullwingcleartime_message(instance_type: Literal["raid", "strike", "fractal"]):
    instance_group = InstanceGroup.objects.get(name=instance_type)
    instance_group_interaction = InstanceGroupInteraction(instance_group)

    embed = build_fullwingcleartime_message(instance_group_interaction=instance_group_interaction)

    create_or_update_discord_message(
        group=instance_group,
        webhook_url=WEBHOOKS["leaderboard"],
        embeds_messages_list=[embed],
        thread=Thread(settings.LEADERBOARD_THREADS[instance_group_interaction.instance_type]),
    )


def run_leaderboard(instance_type: Literal["raid", "strike", "fractal"]):
    """
    Run complete leaderboard generation for an instance type.

    Creates and publishes:
    1. Individual instance leaderboards (one per wing/strike/fractal)
    2. Full clear leaderboard (all instances combined)

    Parameters
    ----------
    instance_type: Literal["raid", "strike", "fractal"]
        Type of instances to process
    """
    publish_all_instance_leaderboards(instance_type=instance_type)
    publish_fullwingcleartime_message(instance_type=instance_type)


# %%
if __name__ == "__main__":
    # For testing
    for instance_type in [
        "raid",
        # "strike",
        # "fractal",
    ]:
        pass
        # run_leaderboard(instance_type=instance_type)
    publish_fullwingcleartime_message(instance_type)
