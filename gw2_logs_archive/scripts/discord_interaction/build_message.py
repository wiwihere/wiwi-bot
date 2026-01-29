# %%
"""Use the main function create_discord_message(icgi) to build the message.
Then make embeds out of the with build_embeds.py
"""

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import logging
from itertools import chain
from typing import TYPE_CHECKING, Tuple

import numpy as np
from django.db.models import QuerySet
from gw2_logs.models import (
    DpsLog,
    InstanceClear,
)
from scripts.discord_interaction.message_helpers import create_duration_header_with_player_emotes
from scripts.log_helpers import (
    WIPE_EMOTES,
    get_duration_str,
)
from scripts.model_interactions.dps_log import DpsLogInteraction
from scripts.model_interactions.instance_clear import InstanceClearInteraction

if TYPE_CHECKING:
    # Avoids circular imports
    from scripts.model_interactions.instance_clear_group import InstanceClearGroupInteraction

logger = logging.getLogger(__name__)


class FirstBossTracker:
    """Tracks whether the first successful log has been encountered."""

    def __init__(self):
        self.is_first = True

    def consume(self, success: bool):
        """Flip to false after first success."""
        if self.is_first and success:
            logger.info("First boss cleared")
            self.is_first = False


def _create_message_title(icgi: "InstanceClearGroupInteraction") -> str:
    """Header is the date and the total cleartime if all bosses are success"""
    icg = icgi.iclear_group
    title = icg.pretty_time
    if icg.success:
        # Get rank compared to all previous cleared instancecleargroups
        rank_str = icgi.get_rank_emote_icg()
        duration_str = get_duration_str(icg.duration.seconds)
        title += f"⠀⠀⠀⠀{rank_str} **{duration_str}** {rank_str} \n"

    return title


def _create_log_delay_str(
    log: DpsLog,
    all_logs: list[DpsLog],
    all_success_logs: list[DpsLog],
    first_boss_tracker: FirstBossTracker,
    encounter_wipes: QuerySet[DpsLog],
    encounter_success: QuerySet[DpsLog],
) -> str:
    """Calculate the delay of the log with the previous logs in the cleargroup.

    Example return:
    "1:48" -> fight started 1min48 after other
    """
    delay_str = get_duration_str(0)  # Default no duration between previous and start log.

    if first_boss_tracker.is_first:
        # If there was a wipe on the first boss we calculate diff between start of
        # wipe run and start of kill run
        if len(encounter_wipes) > 0:
            diff_time = log.start_time - all_logs[0].start_time
            if not encounter_success:
                diff_time = log.start_time + log.duration - all_logs[0].start_time

            delay_str = get_duration_str(diff_time.seconds)

    else:
        # Calculate duration between start of kill run with previous kill run
        if log.success:
            all_success_logs_idx = all_success_logs.index(log)
            diff_time = log.start_time - (
                all_success_logs[all_success_logs_idx - 1].start_time
                + all_success_logs[all_success_logs_idx - 1].duration
            )
            delay_str = get_duration_str(diff_time.seconds)

        # If we dont have a success, we still need to calculate difference with previous log.
        elif len(encounter_wipes) > 0:
            diff_time = (
                log.start_time
                + log.duration
                - (
                    all_logs[all_logs.index(log) - len(encounter_wipes)].start_time
                    + all_logs[all_logs.index(log) - len(encounter_wipes)].duration
                )
            )

            delay_str = get_duration_str(diff_time.seconds)

    return delay_str


def _create_log_wipe_str(encounter_wipes: QuerySet[DpsLog]) -> str:
    """Create the wipe str. This will add one wipe skull per wipe on an encounter.
    Clicking the skull will open a browser at the dps.report log.

    Example return with wipes at 54% and 14%:
    "[<:wipe_at_54:skullemoiji>](https://dps.report/wipe1) [<:wipe_at_14:skullemoiji>](https://dps.report/wipe2)"
    """
    wipe_str = ""
    for wipe in encounter_wipes:
        if wipe.duration.seconds > 15:
            wipe_emote = WIPE_EMOTES[np.ceil(wipe.final_health_percentage / 12.5)].format(
                f"wipe_at_{int(wipe.final_health_percentage)}"
            )
            # Add link to dps.report log if available
            if wipe.url == "":
                wipe_str += f" {wipe_emote}"
            else:
                wipe_str += f" [{wipe_emote}]({wipe.url})"
    return wipe_str


def _create_log_message_line(
    log: DpsLog,
    instance_logs: list[DpsLog],
    all_success_logs: list[DpsLog],
    all_logs: list[DpsLog],
    first_boss_tracker: FirstBossTracker,
) -> str:
    r"""Full text line as shown on discord.
    first_boss flips to False on the first successful log and never back.
    Each encounter is only processed once. At the start of this function we therefore return
    an empty line if its not the last log for the encounter.

    Example:
    '<:ura:1310742374665683056><:r21_of40_slower42_1s:1240799615763222579>[Ura](https://dps.report/dummy_ura) (**4:50**)_+1:48_\n'
    """

    # Filter wipes and success
    encounter_wipes = [l for l in instance_logs if not l.success and l.encounter.nr == log.encounter.nr]
    encounter_success = [l for l in instance_logs if l.success and l.encounter.nr == log.encounter.nr]

    if not log.success:
        if encounter_success:
            # There is a success log, but its not this one.
            # Create the message_line when the success logs is passed to this function
            log_message_line = ""
            return log_message_line

        if not (list(encounter_wipes).index(log) + 1 == len(encounter_wipes)):
            # There are only wipes. But we only create a message_line when the last
            # failed log is passed to this function
            log_message_line = ""
            return log_message_line

    rank_str = DpsLogInteraction(dpslog=log).get_rank_emote_log()

    delay_str = _create_log_delay_str(
        log=log,
        all_logs=all_logs,
        all_success_logs=all_success_logs,
        first_boss_tracker=first_boss_tracker,
        encounter_wipes=encounter_wipes,
        encounter_success=encounter_success,
    )
    # Only after a successful log the first_boss is cleared.
    if log.success:
        first_boss_tracker.consume(success=log.success)

    # Wipes also get an url, can be click the emote to go there.
    # Dont show wipes that are under 15 seconds.
    wipe_str = _create_log_wipe_str(encounter_wipes=encounter_wipes)

    # Add encounter to field
    if log.success:
        log_message_line = f"{log.discord_tag.format(rank_str=rank_str)}_+{delay_str}_{wipe_str}\n"
    else:
        if not encounter_success:
            # If there are only wipes for an encounter, we still want to see it in the line.
            # This is a bit tricky, thats why we need to check a couple things.
            #   - Cannot add text when there is a success as it will print multiple lines for
            #     the same encounter.
            #   - Also should only add multiple wipes on same boss once.
            if list(encounter_wipes).index(log) + 1 == len(encounter_wipes):
                # Build line without URL to dps.report.
                log_message_line = f"{log.encounter.emoji.discord_tag(log.difficulty)}{rank_str}{log.encounter.name}{log.cm_str} (wipe)_+{delay_str}_{wipe_str}\n"
    return log_message_line


def _create_instance_header(
    iclear: InstanceClear,
    all_success_logs: list[DpsLog],
    all_logs: list[DpsLog],
    first_boss_tracker: FirstBossTracker,
) -> Tuple[str, str]:
    r"""Create the header of an instance. For raid wings this would result in something like this;

    title_instance:
    '**__<:spirit_vale:1185639755464060959><:r46_of82_slower108_8s:1240799615763222579>Spirit Vale (17:49)__**\n'

    description_instance:
    '<:vale_guardian:emoji_id><:r55_of82_slower22_6s:emoji_id>[Vale Guardian](https://dps.report/.._vg) (**2:31**)_+0:00_\n
    <:gorseval_the_multifarious:emoji_id><:r29_of83_slower10_7s:emoji_id>[Gorseval the Multifarious](https://dps.report/.._gors) (**2:10**)_+7:33_\n
    <:sabetha_the_saboteur:emoji_id><:r68_of83_slower49_0s:emoji_id>[Sabetha the Saboteur](https://dps.report/.._sab) (**3:42**)_+1:51_\n'
    """
    # --------------------------------
    # Create the title of the instance
    # --------------------------------
    # Find rank and cleartime of wing
    rank_str = InstanceClearInteraction(iclear=iclear).get_rank_emote_ic()
    duration_str = get_duration_str(iclear.duration.seconds)

    title_instance = (
        f"**__{iclear.instance.emoji.discord_tag()}{rank_str}{iclear.instance.name} ({duration_str})__**\n"
    )

    # --------------------------------------
    # Create the description of the instance
    # --------------------------------------
    # Loop all logs in an instance (raid wing), each encounter will be its own line in discord
    # If there are wipes these are added to the line as separete emoji's
    # Also calculate diff between logs (downtime)
    description_instance = ""
    instance_logs = list(iclear.dps_logs.order_by("start_time"))
    for log in instance_logs:
        log_message_line = _create_log_message_line(
            log=log,
            instance_logs=instance_logs,
            all_success_logs=all_success_logs,
            all_logs=all_logs,
            first_boss_tracker=first_boss_tracker,
        )
        if log_message_line != "":
            logger.debug(f"Adding logline:  {iclear} - {log}")

        description_instance += log_message_line

    return title_instance, description_instance


def create_discord_message(icgi: "InstanceClearGroupInteraction") -> Tuple[str, str]:
    """Create a discord message from the available logs that are linked
    to the instance clear.
    """
    icg = icgi.iclear_group

    # Find all logs
    all_logs = list(chain(*[i.dps_logs.order_by("start_time") for i in icgi.icg_iclears_all]))
    all_success_logs = list(
        chain(*[i.dps_logs.filter(success=True).order_by("start_time") for i in icgi.icg_iclears_all])
    )

    logger.debug("")  # empty line for readability
    logger.debug(
        f"Creating discord message for {icg.name} - {len(all_logs)} logs, {len(all_success_logs)} success logs, {len(icgi.icg_iclears_all)} wings"
    )

    titles = {}
    descriptions = {}

    title_main = _create_message_title(icgi=icgi)
    description_main = create_duration_header_with_player_emotes(all_logs=all_logs)

    titles[icg.type] = {"main": title_main}
    descriptions[icg.type] = {"main": description_main}

    # Loop over the instance clears (Spirit Vale, Salvation Pass, Soto Strikes, etc)
    first_boss_tracker = FirstBossTracker()  # Tracks if a log is the first boss of all logs.
    for iclear in icgi.icg_iclears_all:
        logger.debug(f"Creating header: {iclear}")
        title_instance, description_instance = _create_instance_header(
            iclear=iclear,
            all_success_logs=all_success_logs,
            all_logs=all_logs,
            first_boss_tracker=first_boss_tracker,
        )
        # Add the field text to the embed. Raids and strikes have a
        # larger chance that the field_value is larger than 1024 charcters.
        # This is sadly currently the limit on embed.field.value.
        # Descriptions can be 4096 characters, so instead of a field we just edit the description.
        titles[iclear.instance.instance_group.name][iclear.name] = title_instance
        descriptions[iclear.instance.instance_group.name][iclear.name] = description_instance

    return titles, descriptions
