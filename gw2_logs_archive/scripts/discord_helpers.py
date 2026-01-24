# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import datetime
import logging
from dataclasses import dataclass
from itertools import chain
from typing import TYPE_CHECKING, Union

import numpy as np
import pandas as pd
from django.conf import settings
from django.db.models import Q, QuerySet
from gw2_logs.models import (
    DpsLog,
    Encounter,
    Instance,
    InstanceClear,
    InstanceClearGroup,
)
from scripts.log_helpers import (
    ITYPE_GROUPS,
    PLAYER_EMOTES,
    WIPE_EMOTES,
    create_discord_time,
    create_or_update_discord_message,
    create_or_update_discord_message_current_week,
    get_duration_str,
    get_rank_emote,
    zfill_y_m_d,
)
from scripts.model_interactions.dps_log import DpsLogInteraction
from scripts.model_interactions.instance_clear import InstanceClearInteraction
from scripts.model_interactions.instance_clear_group import InstanceClearGroupInteraction

logger = logging.getLogger(__name__)


class DiscordMessageBuilder:
    def __init__(
        self,
        icgi: "InstanceClearGroupInteraction",
    ):
        self.icgi = icgi


def _create_message_title(icgi: InstanceClearGroupInteraction) -> str:
    """Header is the date and the total cleartime if all bosses are success"""
    icg = icgi.iclear_group
    title = icg.pretty_time
    if icg.success:
        # Get rank compared to all previous cleared instancecleargroups
        rank_str = icgi.get_rank_emote_icg()
        duration_str = get_duration_str(icg.duration.seconds)
        title += f"⠀⠀⠀⠀{rank_str} **{duration_str}** {rank_str} \n"

    return title


def _create_duration_header_with_player_emotes(all_logs: list[DpsLog]) -> str:
    """Create the embed header with the core, friend and pugs having a different emote, as configured in PLAYER_EMOTES (ducks) for each player.
    Returns this string with the start and endtime as well, like so;
    19:45 - 22:00
    duck duck duck ... etc
    """
    # Calculate the median players in the instancecleargroup
    try:
        core_count = int(np.median([log.core_player_count for log in all_logs]))
        friend_count = int(np.median([log.friend_player_count for log in all_logs]))
        pug_count = int(np.median([log.player_count for log in all_logs])) - core_count - friend_count
    except TypeError:
        logger.error("Couldnt find core_count")
        core_count = 0
        friend_count = 0
        pug_count = 10

    # Create the string with emotes for each player. After 5 players a space is added
    pug_split_str = f"{PLAYER_EMOTES['core'] * core_count}{PLAYER_EMOTES['friend'] * friend_count}{PLAYER_EMOTES['pug'] * pug_count}".split(
        ">"
    )
    if len(pug_split_str) > 5:
        pug_split_str[5] = f" {pug_split_str[5]}"  # empty str here:`⠀`
    pug_str = ">".join(pug_split_str)

    # title description with start - end time and colored ducks for core/pugs
    description = f"""{create_discord_time(all_logs[0].start_time)} - \
{create_discord_time(all_logs[-1].start_time + all_logs[-1].duration)} \
\n{pug_str}\n
"""
    return description


def create_log_delay_str(
    log: DpsLog,
    all_logs: list[DpsLog],
    all_success_logs: list[DpsLog],
    first_boss: bool,
    encounter_wipes: QuerySet[DpsLog],
    encounter_success: QuerySet[DpsLog],
) -> str:
    """Calculate the delay of the log with the previous logs in the cleargroup.

    Example return:
    "1:48" -> fight started 1min48 after other
    """
    delay_str = get_duration_str(0)  # Default no duration between previous and start log.

    if first_boss:
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


def create_log_wipe_str(encounter_wipes: QuerySet[DpsLog]) -> str:
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


def create_log_message_line(
    log: DpsLog,
    instance_logs: QuerySet[DpsLog],
    all_success_logs: list[DpsLog],
    all_logs: list[DpsLog],
    first_boss: bool,
) -> Union[str, bool]:
    r"""Full text line as shown on discord.

    Example:
    '<:ura:1310742374665683056><:r21_of40_slower42_1s:1240799615763222579>[Ura](https://dps.report/3xn6-20251218-201925_ura) (**4:50**)_+1:48_\n'
    """
    # Filter wipes and success
    encounter_wipes = instance_logs.filter(success=False, encounter__nr=log.encounter.nr)
    encounter_success = instance_logs.filter(success=True, encounter__nr=log.encounter.nr)

    rank_str = DpsLogInteraction(dpslog=log).get_rank_emote_log()

    delay_str = create_log_delay_str(
        log=log,
        all_logs=all_logs,
        all_success_logs=all_success_logs,
        first_boss=first_boss,
        encounter_wipes=encounter_wipes,
        encounter_success=encounter_success,
    )
    # Only after a successful log the first_boss is cleared.
    if log.success:
        first_boss = False

    # Wipes also get an url, can be click the emote to go there.
    # Dont show wipes that are under 15 seconds.
    wipe_str = create_log_wipe_str(encounter_wipes=encounter_wipes)

    # Add encounter to field
    log_message_line = ""
    if log.success:
        log_message_line = f"{log.discord_tag.format(rank_str=rank_str)}_+{delay_str}_{wipe_str}\n"
    else:
        # If there are only wipes for an encounter, still add it to the field.
        # This is a bit tricky, thats why we need to check a couple things.
        #   - Cannot add text when there is a success as it will print multiple lines for
        #     the same encounter.
        #   - Also should only add multiple wipes on same boss once.
        if not encounter_success:
            if list(encounter_wipes).index(log) + 1 == len(encounter_wipes):
                log_message_line = f"{log.encounter.emoji.discord_tag(log.difficulty)}{rank_str}{log.encounter.name}{log.cm_str} (wipe)_+{delay_str}_{wipe_str}\n"
    return log_message_line, first_boss


def create_instance_header(
    iclear: InstanceClear,
    all_success_logs: list[DpsLog],
    all_logs: list[DpsLog],
    first_boss: bool,
) -> Union[str, str, bool]:
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
    instance_logs = iclear.dps_logs.order_by("start_time")
    for log in instance_logs:
        log_message_line, first_boss = create_log_message_line(
            log=log,
            instance_logs=instance_logs,
            all_success_logs=all_success_logs,
            all_logs=all_logs,
            first_boss=first_boss,
        )
        description_instance += log_message_line

    return title_instance, description_instance, first_boss


def create_discord_message(icgi):
    """Create a discord message from the available logs that are linked
    to the instance clear.
    """
    icg = icgi.iclear_group

    # Find all logs
    all_logs = list(chain(*[i.dps_logs.order_by("start_time") for i in icgi.icg_iclears_all]))
    all_success_logs = list(
        chain(*[i.dps_logs.filter(success=True).order_by("start_time") for i in icgi.icg_iclears_all])
    )

    descriptions = {}
    titles = {}

    title_main = _create_message_title(icgi=icgi)
    description_main = _create_duration_header_with_player_emotes(all_logs=all_logs)

    titles[icg.type] = {"main": title_main}
    descriptions[icg.type] = {"main": description_main}

    # Loop over the instance clears (Spirit Vale, Salvation Pass, Soto Strikes, etc)
    first_boss = True  # Tracks if a log is the first boss of all logs.
    for iclear in icgi.icg_iclears_all:
        title_instance, description_instance, first_boss = create_instance_header(
            iclear=iclear,
            all_success_logs=all_success_logs,
            all_logs=all_logs,
            first_boss=first_boss,
        )
        # Add the field text to the embed. Raids and strikes have a
        # larger chance that the field_value is larger than 1024 charcters.
        # This is sadly currently the limit on embed.field.value.
        # Descriptions can be 4096 characters, so instead of a field we just edit the description.
        titles[iclear.instance.instance_group.name][iclear.name] = title_instance
        descriptions[iclear.instance.instance_group.name][iclear.name] = description_instance

    return titles, descriptions


if __name__ == "__main__":
    # Test refactor on the go. Dont touch the code below.
    y, m, d = 2025, 12, 18
    itype_group = "raid"

    icgi = InstanceClearGroupInteraction.create_from_date(y=y, m=m, d=d, itype_group=itype_group)
    titles, descriptions = create_discord_message(icgi)
    logger.info(titles)
    logger.info(descriptions)

    assert titles == {
        "raid": {
            "main": "Thu 18 Dec 2025⠀⠀⠀⠀<:r20_of45_slower1804_9s:1240399925502545930> **3:12:00** <:r20_of45_slower1804_9s:1240399925502545930> \n",
            "spirit_vale__20251218": "**__<:spirit_vale:1185639755464060959><:r46_of82_slower108_8s:1240799615763222579>Spirit Vale (17:49)__**\n",
            "salvation_pass__20251218": "**__<:salvation_pass:1185642016776913046><:r23_of84_slower55_9s:1240399925502545930>Salvation Pass (14:55)__**\n",
            "bastion_of_the_penitent__20251218": "**__<:bastion_of_the_penitent:1185642020484698132><:r73_of99_slower319_4s:1240799615763222579>Bastion of the Penitent (23:26)__**\n",
            "mount_balrior__20251218": "**__<:mount_balrior:1311064236486688839><:r14_of39_slower175_0s:1240399925502545930>Mount Balrior (22:17)__**\n",
        }
    }

    assert descriptions == {
        "raid": {
            "main": "<t:1766083791:t> - <t:1766089156:t> \n<a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414> <a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:pug:1206367130509905931>\n\n",
            "spirit_vale__20251218": "<:vale_guardian:1206250717401063605><:r55_of82_slower22_6s:1240799615763222579>[Vale Guardian](https://dps.report/Zb2m-20251218-185224_vg) (**2:31**)_+0:00_\n<:gorseval_the_multifarious:1206250719074721813><:r29_of83_slower10_7s:1240399925502545930>[Gorseval the Multifarious](https://dps.report/aIEy-20251218-190208_gors) (**2:10**)_+7:33_\n<:sabetha_the_saboteur:1206250720483872828><:r68_of83_slower49_0s:1240798628596027483>[Sabetha the Saboteur](https://dps.report/texU-20251218-190742_sab) (**3:42**)_+1:51_\n",
            "salvation_pass__20251218": "<:slothasor:1206250721880576081><:r8_of84_slower9_5s:1240399924198379621>[Slothasor](https://dps.report/yGvz-20251218-191257_sloth) (**2:10**)_+2:58_\n<:bandit_trio:1206250723550175283><:r26_of84_slower4_6s:1240399925502545930>[Bandit Trio](https://dps.report/3csn-20251218-192149_trio) (**6:31**)_+0:22_\n<:matthias_gabrel:1206250724879503410><:r72_of84_slower66_0s:1240798628596027483>[Matthias Gabrel](https://dps.report/D9Wl-20251218-192539_matt) (**3:10**)_+2:40_\n",
            "bastion_of_the_penitent__20251218": "<:cairn:1206251996680556544><:r6_of99_slower3_6s:1240399924198379621>[Cairn CM](https://dps.report/e3La-20251218-193053_cairn) (**1:18**)_+3:44_\n<:mursaat_overseer:1206252000229199932><:r3_of99_slower3_7s:1338196304924250273>[Mursaat Overseer CM](https://dps.report/cUNu-20251218-193357_mo) (**1:37**)_+1:35_\n<:samarog:1206256460120457277><:r4_of99_slower41_2s:1240399924198379621>[Samarog CM](https://dps.report/Lgpi-20251218-194020_sam) (**5:08**)_+1:19_\n<:deimos:1206256463031304253><:r5_of99_slower19_9s:1240399924198379621>[Deimos CM](https://dps.report/7jym-20251218-195252_dei) (**5:23**)_+7:03_ [<:wipe_at_14:1199739670641258526>](https://dps.report/2Q8K-20251218-194648_dei)\n",
            "mount_balrior__20251218": "<:greer:1310742326548762664><:r21_of42_slower45_4s:1240799615763222579>[Greer, the Blightbringer](https://dps.report/IPHG-20251218-200502_greer) (**7:59**)_+4:13_\n<:decima:1310742355644776458><:r17_of40_slower39_0s:1240399925502545930>[Decima, the Stormsinger](https://dps.report/tOQg-20251218-201241_deci) (**4:57**)_+2:41_\n<:ura:1310742374665683056><:r21_of40_slower42_1s:1240799615763222579>[Ura](https://dps.report/3xn6-20251218-201925_ura) (**4:50**)_+1:48_\n",
        }
    }


# %%


def create_discord_embeds(titles, descriptions) -> dict:
    """Create discord embed from description."""
    embeds = {}
    has_title = False
    for instance_type in titles:
        use_fields = True  # max 1024 per field
        field_characters = np.array([len(i) for i in descriptions[instance_type].values()])
        # Check field length. If more than 1024 it cannot go to a field and should instead
        # go to description
        if np.any(field_characters > 1024):
            logger.info("Cannot use fields because one has more than 1024 chars")
            use_fields = False

            # field characters actually change here because the titles are included in
            # the description.
            field_characters += np.array([len(i) for i in titles[instance_type].values()])

        # If we go over 4096 characters, a new embed should be created.
        # Just find per field which embed they should be in:

        embed_ids = np.floor(np.cumsum(field_characters) / 4096).astype(int)

        # Loop over every unique embed for this instance.
        for embed_id in np.unique(embed_ids):
            title = ""
            description = ""
            # The first embed gets a title and title  description.
            if int(embed_id) == 0:
                title = titles[instance_type]["main"]
                description = descriptions[instance_type]["main"]
                if ("raid" in titles) and ("strike" in titles):
                    if not has_title:
                        has_title = True
                    else:
                        title = ""
                        description = ""

            if not use_fields:
                # Loop the encounters
                for embed_id_instance, encounter_key in zip(embed_ids, descriptions[instance_type].keys()):
                    if encounter_key == "main":  # Main is already in title.
                        continue
                    if embed_id_instance != embed_id:  # Should go to different embed.
                        logger.debug(f"{len(description)} something is up with embeds")

                        continue

                    description += titles[instance_type][encounter_key]
                    description += descriptions[instance_type][encounter_key] + "\n"

            embeds[f"{instance_type}_{embed_id}"] = discord.Embed(
                title=title,
                description=description,
                colour=EMBED_COLOR[instance_type],
            )

            if use_fields:
                for embed_id_instance, encounter_key in zip(embed_ids, descriptions[instance_type].keys()):
                    if encounter_key == "main":  # Main is already in title.
                        continue
                    if embed_id_instance != embed_id:  # Should go to different embed.
                        continue
                    field_name = titles[instance_type][encounter_key]
                    field_value = descriptions[instance_type][encounter_key]
                    embeds[f"{instance_type}_{embed_id}"].add_field(name=field_name, value=field_value, inline=False)

    return embeds
