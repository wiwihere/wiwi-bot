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


def build_instance_cleartime_row(instance_interaction: InstanceInteraction) -> str:
    # Strikes dont have average clear time
    if instance_interaction.instance_type == "strike":
        return ""

    iclear_success_all = instance_interaction.get_all_succesful_clears()

    description = f"{instance_interaction.instance.emoji.discord_tag()}"

    # Add the top 3 logs
    for idx, instance_clear in enumerate(iclear_success_all[:3]):
        rank_duration_str = get_rank_duration_str(
            instance_clear,
            iclear_success_all,
            itype=instance_interaction.instance_type,
            pretty_time=True,
        )
        description += rank_duration_str

    if len(iclear_success_all) > 0:
        # Add average cleartime of instance.
        avg_duration_str = get_avg_duration_str(iclear_success_all)
        description += f"{avg_duration_str}\n\n"
    return description


def build_instance_title(instance: Instance) -> str:
    """Title is just the name of the instance. For strikes the emoji is added"""
    instance_title = f"{instance.name}"

    # strike needs emoji because it doenst have instance average
    if instance.instance_group.name == "strike":
        instance_title = f"{instance.emoji.discord_tag()} {instance.name}"
    return instance_title


def _build_encounter_line(emote: str, encounter_success_all: QuerySet, instance_type: str) -> str:
    # Go through top 3 logs and add this to the message
    line_str = f"{emote}"

    for idx, encounter_log in enumerate(encounter_success_all[:3]):
        rank_duration_str = get_rank_duration_str(
            indiv=encounter_log,
            group=encounter_success_all,
            itype=instance_type,
            pretty_time=True,
            url=encounter_log.url,
        )
        line_str += rank_duration_str

    # Add average cleartime of encounter.
    avg_duration_str = get_avg_duration_str(encounter_success_all)
    line_str += f"{avg_duration_str}\n"
    return line_str


def _create_leaderboard_encounter_lines(
    encounter_interaction: EncounterInteraction,
    instance_interaction: InstanceInteraction,
) -> str:
    """Build lines for single encounter. Different difficulties are shown on a new line.
    Skips if the encounter in the database has a False value on lb, lb_cm or lb_lcm.
    """

    encounter_line = ""
    for difficulty in ["normal", "cm", "lcm"]:
        cm, lcm, lb_attr = DIFFICULTY_CONFIG[difficulty]
        should_show_on_leaderboard = getattr(encounter_interaction.encounter, lb_attr)

        if not should_show_on_leaderboard:
            continue  # skip if encounter is not selected to be on leaderboard

        # Find encounter times
        encounter_success_all = encounter_interaction.get_all_succesful_clears(
            cm=cm, lcm=lcm, min_core_count=instance_interaction.min_core_count
        )

        if len(encounter_success_all) == 0:
            continue

        emote: str = encounter_interaction.encounter.emoji.discord_tag(difficulty)
        encounter_line += _build_encounter_line(
            emote=emote, encounter_success_all=encounter_success_all, instance_type=instance_interaction.instance_type
        )
    return encounter_line


def build_leaderboard_instance_embed(
    instance_interaction: InstanceInteraction,
) -> discord.Embed:
    """
    Build a Discord embed for a single instance (e.g. Spirit Vale) leaderboard.

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
    description = build_instance_cleartime_row(instance_interaction=instance_interaction)

    # For each encounter in the instance, add a new row to the embed.
    for encounter in instance_interaction.instance.encounters.all().order_by("nr"):
        encounter_interaction = EncounterInteraction(encounter)
        description += _create_leaderboard_encounter_lines(
            encounter_interaction=encounter_interaction,
            instance_interaction=instance_interaction,
        )

    title = build_instance_title(instance=instance_interaction.instance)
    return discord.Embed(
        title=title,
        description=description,
        colour=EMBED_COLOR[instance_interaction.instance_type],
    )


def publish_all_instance_leaderboards(instance_type: Literal["raid", "strike", "fractal"]) -> None:
    """
    Create and publish leaderboards on discord for all instances of a given type.

    Parameters
    ----------
    instance_type: Literal["raids", "strike", "fractal"]
    """
    instances = Instance.objects.filter(instance_group__name=instance_type).order_by("nr")

    for instance in instances:
        instance_interaction = InstanceInteraction(instance)
        embed = build_leaderboard_instance_embed(instance_interaction=instance_interaction)

        create_or_update_discord_message(
            group=instance,
            webhook_url=WEBHOOKS["leaderboard"],
            embeds_messages_list=[embed],
            thread=Thread(settings.LEADERBOARD_THREADS[instance_type]),
        )


def get_encounter_emojis(encounters: QuerySet[Encounter]) -> str:
    description = ""
    for encounter in encounters:
        description += encounter.emoji.discord_tag()

    # Add empty spaces to align all rows
    description += BLANK_EMOTE * max(0, 6 - len(encounters))
    return description


def _create_leaderboard_encounters_line(instance_interaction: InstanceInteraction) -> str:
    # Get all encounters for this instance that are used for total duration
    encounters = instance_interaction.get_all_encounters_for_leaderboard()

    # Dont add instance if no encounters selected
    if len(encounters) == 0:
        return ""

    # Find instance clear fastest and average time
    iclear_success_all = instance_interaction.get_all_succesful_clears()

    # Instance emote
    line_str = f"{instance_interaction.instance.emoji.discord_tag()}"  # Instance emote (e.g. wing1)
    line_str += get_encounter_emojis(encounters=encounters)  # (e.g. vg, gorseval, sabetha)

    if len(iclear_success_all) > 0:
        # Add first rank time to message. The popup of the medal will give the date
        line_str += get_rank_duration_str(
            iclear_success_all.first(), iclear_success_all, itype=instance_interaction.instance_type, pretty_time=True
        )

        # Add average clear times
        line_str += get_avg_duration_str(iclear_success_all)
    line_str += "\n"
    return line_str


def create_leaderboard_fullclear_line(instance_group_interaction: InstanceGroupInteraction) -> str:
    """Line with top3 clear durations for a fullclear."""
    line_str = ""
    icleargroup_success_all = instance_group_interaction.get_all_successful_group_clears()

    for idx, icleargroup in enumerate(icleargroup_success_all[:3]):
        line_str += get_rank_duration_str(
            icleargroup, icleargroup_success_all, itype=instance_group_interaction.instance_type, pretty_time=True
        )

    if len(icleargroup_success_all) > 0:
        # Add average clear times
        line_str += get_avg_duration_str(icleargroup_success_all)
    return line_str


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
