# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import logging
from dataclasses import dataclass
from itertools import chain

import numpy as np
import pandas as pd
from django.conf import settings
from django.db.models import Q
from gw2_logs.models import (
    DpsLog,
    Encounter,
    Instance,
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

logger = logging.getLogger(__name__)


def create_discord_message(icgi):
    """Create a discord message from the available logs that are linked
    to the instance clear.
    """
    icg = icgi.iclear_group

    icgi.all_logs = list(chain(*[i.dps_logs.order_by("start_time") for i in icgi.icg_iclears_all]))
    # Find all iclears. Can be both strike and raid.
    all_success_logs = list(
        chain(*[i.dps_logs.filter(success=True).order_by("start_time") for i in icgi.icg_iclears_all])
    )

    descriptions = {}
    titles = {}

    # Put raid, strike, fractal in separate embeds.
    # for instance_type in instance_types:

    try:
        core_count = int(np.median([log.core_player_count for log in icgi.all_logs]))
        friend_count = int(np.median([log.friend_player_count for log in icgi.all_logs]))
        pug_count = int(np.median([log.player_count for log in icgi.all_logs])) - core_count - friend_count
    except TypeError:
        core_count = 0
        friend_count = 0
        pug_count = 10

    # Nina's space, add space after 5 ducks for better readability.
    pug_split_str = f"{PLAYER_EMOTES['core'] * core_count}{PLAYER_EMOTES['friend'] * friend_count}{PLAYER_EMOTES['pug'] * pug_count}".split(
        ">"
    )
    if len(pug_split_str) > 5:
        pug_split_str[5] = f" {pug_split_str[5]}"  # empty str here:`⠀`
    pug_str = ">".join(pug_split_str)

    # title description with start - end time and colored ducks for core/pugs
    description = f"""{create_discord_time(icgi.all_logs[0].start_time)} - \
{create_discord_time(icgi.all_logs[-1].start_time + icgi.all_logs[-1].duration)} \
\n{pug_str}\n
"""
    # Add total instance group time if all bosses finished.
    # Loop through all instance clears in the same discord message.
    title = icgi.iclear_group.pretty_time
    if icg.success:
        # Get rank compared to all cleared instancecleargroups
        duration_encounters = (
            InstanceClearGroup.objects.filter(type=icg.type).order_by("start_time").last().duration_encounters
        )

        group = list(
            InstanceClearGroup.objects.filter(
                success=True,
                duration_encounters=duration_encounters,
                type=icg.type,
            )
            .exclude(name__icontains="cm__")
            .order_by("duration")
        )

        rank_str = get_rank_emote(
            indiv=icg,
            group=group,
            core_minimum=settings.CORE_MINIMUM[icg.type],
        )

        duration_str = get_duration_str(icg.duration.seconds)
        title += f"⠀⠀⠀⠀{rank_str} **{duration_str}** {rank_str} \n"

    titles[icg.type] = {"main": title}
    descriptions[icg.type] = {"main": description}

    # Loop over the instance clears
    first_boss = True  # Tracks if a log is the first boss of all logs.
    for iclear in icgi.icg_iclears_all:
        titles[iclear.instance.instance_group.name][iclear.name] = ""  # field title
        descriptions[iclear.instance.instance_group.name][iclear.name] = ""  # field description

        # Find rank of full instance on leaderboard
        iclear_success_all = None
        if iclear.success:
            iclear_success_all = list(
                iclear.instance.instance_clears.filter(success=True, emboldened=False)
                .filter(
                    Q(start_time__gte=iclear.start_time - datetime.timedelta(days=9999))
                    & Q(start_time__lte=iclear.start_time)
                )
                .order_by("duration")
            )
        rank_str = get_rank_emote(
            indiv=iclear,
            group=iclear_success_all,
            core_minimum=settings.CORE_MINIMUM[iclear.instance.instance_group.name],
        )

        # Cleartime wing
        duration_str = get_duration_str(iclear.duration.seconds)

        titles[iclear.instance.instance_group.name][iclear.name] = (
            f"**__{iclear.instance.emoji.discord_tag()}{rank_str}{iclear.name.split('__')[0].replace('_', ' ').title()} \
({duration_str})__**\n"
        )
        field_value = ""

        instance_logs = iclear.dps_logs.order_by("start_time")

        # Loop all logs in an instance (raid wing).
        # If there are wipes also take those
        # Print each log on separate line. Also calculate diff between logs (downtime)
        for idx, log in enumerate(instance_logs):
            encounter_wipes = instance_logs.filter(success=False, encounter__nr=log.encounter.nr)
            encounter_success = instance_logs.filter(success=True, encounter__nr=log.encounter.nr)

            duration_str = get_duration_str(0)  # Default no duration between previous and start log.

            if first_boss:
                # If there was a wipe on the first boss we calculate diff between start of
                # wipe run and start of kill run
                if len(encounter_wipes) > 0:
                    diff_time = log.start_time - icgi.all_logs[0].start_time
                    if not encounter_success:
                        diff_time = log.start_time + log.duration - icgi.all_logs[0].start_time

                    duration_str = get_duration_str(diff_time.seconds)
            else:
                # Calculate duration between start of kill run with previous kill run
                if log.success:
                    all_success_logs_idx = all_success_logs.index(log)
                    diff_time = log.start_time - (
                        all_success_logs[all_success_logs_idx - 1].start_time
                        + all_success_logs[all_success_logs_idx - 1].duration
                    )
                    duration_str = get_duration_str(diff_time.seconds)

                # If we dont have a success, we still need to calculate difference with previous log.
                elif len(encounter_wipes) > 0:
                    diff_time = (
                        log.start_time
                        + log.duration
                        - (
                            icgi.all_logs[icgi.all_logs.index(log) - len(encounter_wipes)].start_time
                            + icgi.all_logs[icgi.all_logs.index(log) - len(encounter_wipes)].duration
                        )
                    )

                    duration_str = get_duration_str(diff_time.seconds)

            if log.success:
                first_boss = False  # Only after a successful log the first_boss is cleared.

            # Find rank of boss on leaderboard filter for logs of last year.
            encounter_success_all = None
            if log.success:
                encounter_success_all = list(
                    log.encounter.dps_logs.filter(success=True, cm=log.cm, emboldened=False)
                    .filter(
                        Q(start_time__gte=log.start_time - datetime.timedelta(days=9999))
                        & Q(start_time__lte=log.start_time)
                    )
                    .order_by("duration")
                )
            rank_str = get_rank_emote(
                indiv=log,
                group=encounter_success_all,
                core_minimum=settings.CORE_MINIMUM[log.encounter.instance.instance_group.name],
                custom_emoji_name=False,
            )

            # Wipes also get an url, can be click the emote to go there. Doesnt work on phone.
            # Dont show wipes that are under 15 seconds.
            wipe_str = ""
            for wipe in encounter_wipes:
                if wipe.duration.seconds > 15:
                    wipe_emote = WIPE_EMOTES[np.ceil(wipe.final_health_percentage / 12.5)].format(
                        f"wipe_at_{int(wipe.final_health_percentage)}"
                    )
                    if wipe.url == "":
                        wipe_str += f" {wipe_emote}"
                    else:
                        wipe_str += f" [{wipe_emote}]({wipe.url})"

            # Add encounter to field
            if log.success:
                field_value += f"{log.discord_tag.format(rank_str=rank_str)}_+{duration_str}_{wipe_str}\n"
            else:
                # If there are only wipes for an encounter, still add it to the field.
                # This is a bit tricky, thats why we need to check a couple things.
                #   - Cannot add text when there is a success as it will print multiple lines for
                #     the same encounter.
                #   - Also should only add multiple wipes on same boss once.
                if not encounter_success:
                    if list(encounter_wipes).index(log) + 1 == len(encounter_wipes):
                        field_value += f"{log.encounter.emoji.discord_tag(log.difficulty)}{rank_str}{log.encounter.name}{log.cm_str} (wipe)_+{duration_str}_{wipe_str}\n"

        # Add the field text to the embed. Raids and strikes have a
        # larger chance that the field_value is larger than 1024 charcters.
        # This is sadly currently the limit on embed.field.value.
        # Descriptions can be 4096 characters, so instead of a field we just edit the description.
        descriptions[iclear.instance.instance_group.name][iclear.name] = field_value

    return titles, descriptions


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
