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
    InstanceClearGroup,
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

logger = logging.getLogger(__name__)
# TODO remove ITYPE_GROUPS
if __name__ == "__main__":
    itype = "raid"
    min_core_count = 0  # select all logs when including non core


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
    DIFFICULTY_CONFIG = {
        "normal": (False, False, "lb"),
        "cm": (True, False, "lb_cm"),
        "lcm": (True, True, "lb_lcm"),
    }

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


# %%
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

    # %%


def build_full_message():
    # Create message for total clear time.
    instance_group = InstanceGroup.objects.get(name=instance_type)
    instances = Instance.objects.filter(instance_group=instance_group).order_by("nr")

    description = ""
    # For each instance add the encounters that are included and their
    # fastest and average killtime
    for instance in instances:
        # Get all encounters for this instance that are used for total duration
        encounters = Encounter.objects.filter(
            use_for_icg_duration=True,
            instance=instance,
        ).order_by("nr")

        # Dont add instance if no encounters selected
        if len(encounters) == 0:
            continue

        # Find instance clear fastest and average time
        iclear_success_all = instance.instance_clears.filter(
            success=True,
            emboldened=False,
            core_player_count__gte=min_core_count,
        ).order_by("duration")
        # .filter(
        #     Q(start_time__gte=datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(days=365))
        #     & Q(start_time__lte=datetime.datetime.now(tz=pytz.UTC))
        # )

        # Instance emote
        description += f"{instance.emoji.discord_tag()}"

        # Loop over the encounters
        counter = 0
        for ec in encounters:
            # encounter emote
            description += ec.emoji.discord_tag()
            counter += 1

        # Add empty spaces to align.
        while counter < 6:
            description += BLANK_EMOTE
            counter += 1

        if len(iclear_success_all) > 0:
            # Add first rank time to message. The popup of the medal will give the date
            rank_duration_str = get_rank_duration_str(
                iclear_success_all.first(), iclear_success_all, itype, pretty_time=True
            )
            description += rank_duration_str

            # Add average clear times
            avg_duration_str = get_avg_duration_str(iclear_success_all)
            description += avg_duration_str
        description += "\n"

    # List the top 3 of the instance group clear time #
    # Filter on duration_encounters to only include runs where all the same wings
    # were selected  for leaderboard. e.g. with wing 8 the clear times went up,
    # so we reset the leaderboard here.
    description += "\n"
    duration_encounters = (
        InstanceClearGroup.objects.filter(type=itype).order_by("start_time").last().duration_encounters
    )
    icleargroup_success_all = (
        InstanceClearGroup.objects.filter(
            success=True,
            duration_encounters=duration_encounters,
            type=itype,
            core_player_count__gte=min_core_count,
        )
        .exclude(name__icontains="cm__")
        .order_by("duration")
    )
    # .filter(
    #         Q(start_time__gte=datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(days=365))
    #         & Q(start_time__lte=datetime.datetime.now(tz=pytz.UTC)),
    #     )

    for idx, icleargroup in enumerate(icleargroup_success_all[:3]):
        rank_duration_str = get_rank_duration_str(icleargroup, icleargroup_success_all, itype, pretty_time=True)
        description += rank_duration_str  # FIXME

    if len(icleargroup_success_all) > 0:
        # Add average clear times
        description += get_avg_duration_str(icleargroup_success_all)

    # Create embed # --------------------------------------------------
    embed = discord.Embed(
        title=f"Full {itype.capitalize()} Clear",
        description=description,
        colour=EMBED_COLOR[instance_group.name],
    )
    embed.set_footer(text=f"Minimum core count: {settings.CORE_MINIMUM[itype]}\nLeaderboard last updated")
    embed.timestamp = datetime.datetime.now()

    # create_or_update_discord_message(
    #     group=instance_group,
    #     webhook_url=WEBHOOKS["leaderboard"],
    #     embeds_messages_list=[embed],
    #     thread=Thread(settings.LEADERBOARD_THREADS[itype]),
    # )


# %%
if __name__ == "__main__":
    for instance_type in [
        "raid",
        # "strike",
        # "fractal",
    ]:
        pass
        # create_leaderboard(itype=itype)
