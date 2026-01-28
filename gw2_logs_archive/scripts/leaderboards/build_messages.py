"""Build formatted strings for leaderboard content."""

DIFFICULTY_CONFIG = {
    "normal": (False, False, "lb"),
    "cm": (True, False, "lb_cm"),
    "lcm": (True, True, "lb_lcm"),
}


def build_instance_cleartime_row(instance_interaction: InstanceInteraction) -> str:
    """Build instance clear time row with top 3 and average."""
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


def build_instance_title(instance) -> str:
    """Build title for instance leaderboard."""


def build_encounter_line(emote, encounter_clears, instance_type) -> str:
    """Build single encounter line with top 3 and average."""


def build_encounter_lines(encounter_interaction, instance_interaction) -> str:
    """Build all difficulty lines for a single encounter."""


def build_encounter_emojis(encounters) -> str:
    """Build emoji string with alignment padding."""


def build_instance_summary_line(instance_interaction) -> str:
    """Build summary line showing instance and encounter emojis with times."""


def build_fullclear_ranking_line(instance_group_interaction) -> str:
    """Build top 3 rankings line for full clear."""
