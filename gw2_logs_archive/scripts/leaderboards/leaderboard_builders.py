# %%

"""Build formatted strings for leaderboard content."""

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging

from django.db.models import QuerySet
from gw2_logs.models import (
    Encounter,
    Instance,
)
from scripts.log_helpers import (
    BLANK_EMOTE,
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


def build_instance_title(instance: Instance) -> str:
    """Build title for instance leaderboard.
    For strikes, includes emoji prefix since they don't show instance averages.
    """
    instance_title = f"{instance.name}"

    # strike needs emoji because it doenst have instance average
    if instance.instance_group.name == "strike":
        instance_title = f"{instance.emoji.discord_tag()} {instance.name}"
    return instance_title


def build_instance_cleartime_row(instance_interaction: InstanceInteraction) -> str:
    """Build instance clear time row with top 3 and average."""
    # Strikes dont have average clear time
    if instance_interaction.instance_type == "strike":
        return ""

    iclear_success_all = instance_interaction.get_all_succesful_clears()

    description = f"{instance_interaction.instance.emoji.discord_tag()}"

    # Add the top 3 logs
    for instance_clear in iclear_success_all[:3]:
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


def _build_encounter_line(emote: str, encounter_success_all: QuerySet[Encounter], instance_type: str) -> str:
    """Build single encounter line with top 3 and average."""
    # Go through top 3 logs and add this to the message
    line_str = f"{emote}"

    for encounter_log in encounter_success_all[:3]:
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


def build_encounter_lines(
    encounter_interaction: EncounterInteraction,
    instance_interaction: InstanceInteraction,
) -> str:
    """Build all difficulty lines for a single encounter.
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


def _build_encounter_emojis(encounters: QuerySet[Encounter]) -> str:
    """Build emoji string with alignment padding."""
    description = ""
    for encounter in encounters:
        description += encounter.emoji.discord_tag()

    # Add empty spaces to align all rows
    description += BLANK_EMOTE * max(0, 6 - len(encounters))
    return description


def build_instance_summary_line(instance_interaction: InstanceInteraction) -> str:
    """Build summary line showing instance and encounter emojis with the fastest and average time."""
    encounters = instance_interaction.get_all_encounters_for_leaderboard()

    # Dont add instance if no encounters selected
    if len(encounters) == 0:
        return ""

    # Find instance clear fastest and average time
    iclear_success_all = instance_interaction.get_all_succesful_clears()

    # Instance emote
    line_str = f"{instance_interaction.instance.emoji.discord_tag()}"  # Instance emote (e.g. wing1)
    line_str += _build_encounter_emojis(encounters=encounters)  # (e.g. vg, gorseval, sabetha)

    if len(iclear_success_all) > 0:
        # Add first rank time to message. The popup of the medal will give the date
        line_str += get_rank_duration_str(
            iclear_success_all.first(), iclear_success_all, itype=instance_interaction.instance_type, pretty_time=True
        )

        # Add average clear times
        line_str += get_avg_duration_str(iclear_success_all)
    line_str += "\n"
    return line_str


def build_fullclear_ranking_line(instance_group_interaction: InstanceGroupInteraction) -> str:
    """Build top 3 rankings line for full clear."""
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
