# %%

"""Create Discord embed objects for leaderboards."""

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging

import discord
from django.utils import timezone
from gw2_logs.models import (
    Instance,
)
from scripts.leaderboards.leaderboard_builders import (
    build_encounter_lines,
    build_fullclear_ranking_line,
    build_instance_cleartime_row,
    build_instance_summary_line,
    build_instance_title,
    build_navigation_menu,
)
from scripts.log_helpers import (
    EMBED_COLOR,
)
from scripts.model_interactions.encounter import EncounterInteraction
from scripts.model_interactions.instance import InstanceInteraction
from scripts.model_interactions.instance_group import InstanceGroupInteraction

logger = logging.getLogger(__name__)


def create_instance_leaderboard_embed(
    instance_interaction: InstanceInteraction,
) -> discord.Embed:
    """
    Create Discord embed for single instance (e.g. Spirit Vale) leaderboard.

    Contains instance clear times and encounter times for all difficulties when the encounters are
    marked in the database to post to the leaderboard. This is handled through the lb, lb_cm and
    lb_lcm options.

    Parameters
    ----------
    instance_interaction: InstanceInteraction
        The instance to build the leaderboard for

    Returns
    -------
    discord.Embed
        Discord embed ready to send
    """
    title = build_instance_title(instance=instance_interaction.instance)

    description = build_instance_cleartime_row(instance_interaction=instance_interaction)

    # For each encounter in the instance, add a new row to the embed.
    for encounter in instance_interaction.instance.encounters.all().order_by("nr"):
        encounter_interaction = EncounterInteraction(encounter)
        description += build_encounter_lines(
            encounter_interaction=encounter_interaction,
            instance_interaction=instance_interaction,
        )

    return discord.Embed(
        title=title,
        description=description,
        colour=EMBED_COLOR[instance_interaction.instance_type],
    )


def create_fullclear_leaderboard_embed(instance_group_interaction: InstanceGroupInteraction) -> discord.Embed:
    """
    Create Discord embed for full clear leaderboard.

    Shows all instances with their encounters and top rankings.

    Parameters
    ----------
    instance_group_interaction : InstanceGroupInteraction
        Instance group to create leaderboard for

    Returns
    -------
    discord.Embed
        Full clear leaderboard embed with footer and timestamp
    """
    # Initialize objects
    instances = Instance.objects.filter(instance_group=instance_group_interaction.instance_group).order_by("nr")

    description = ""

    # For each instance add the encounters that are included and their
    # fastest and average killtime
    for instance in instances:
        instance_interaction = InstanceInteraction(instance)
        description += build_instance_summary_line(instance_interaction=instance_interaction)

    # List the top 3 of the instance group clear time #

    description += "\n"
    description += build_fullclear_ranking_line(instance_group_interaction=instance_group_interaction)
    # Create embed # --------------------------------------------------
    embed = discord.Embed(
        title=f"Full {instance_group_interaction.instance_type.capitalize()} Clear",
        description=description,
        colour=EMBED_COLOR[instance_group_interaction.instance_group.name],
    )
    embed.set_footer(
        text=f"Minimum core count: {instance_group_interaction.instance_group.min_core_count}\nLeaderboard last updated"
    )
    embed.timestamp = timezone.now()
    return embed


def create_navigation_embed(instance_type: str, leaderboard_thread_url: str) -> discord.Embed:
    """
    Create navigation embed for instance type leaderboards.

    Parameters
    ----------
    instance_type : str
        Type of instances ('raid', 'strike', 'fractal')
    leaderboard_thread_url: str
        Full url to the leaderboard thread

    Returns
    -------
    discord.Embed
        Navigation embed with links to all leaderboards
    """

    navigation_menu = build_navigation_menu(instance_type, leaderboard_thread_url=leaderboard_thread_url)

    # Title mapping
    titles = {
        "raid": "📊 Raid Leaderboards",
        "strike": "⚔️ Strike Leaderboards",
        "fractal": "🔮 Fractal Leaderboards",
    }

    embed = discord.Embed(
        title=titles.get(instance_type, f"{instance_type.capitalize()} Leaderboards"),
        description=navigation_menu,
        colour=EMBED_COLOR[instance_type],
    )

    return embed
