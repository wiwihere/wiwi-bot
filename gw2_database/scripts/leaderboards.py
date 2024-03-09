# %%
import datetime

import discord
import numpy as np
import pytz
from discord import SyncWebhook

if __name__ == "__main__":
    from django_for_jupyter import init_django_from_commands

    init_django_from_commands("gw2_database")

from bot_settings import settings
from django.db.models import Q
from gw2_logs.models import DiscordMessage, Emoji, Encounter, Instance, InstanceClearGroup, InstanceGroup
from scripts.log_helpers import (
    BLANK_EMOTE,
    EMBED_COLOR,
    RANK_EMOTES,
    RANK_EMOTES_INVALID,
    Thread,
    get_avg_duration_str,
    get_duration_str,
    get_rank_duration_str,
    get_rank_emote,
)


# %%
def create_leaderboard(itype: str):
    webhook = SyncWebhook.from_url(settings.WEBHOOK_BOT_CHANNEL_LEADERBOARD)
    thread = Thread(settings.LEADERBOARD_THREADS[itype])

    if settings.INCLUDE_NON_CORE_LOGS:
        min_core_count = 0  # select all logs when including non core
    else:
        min_core_count = settings.CORE_MINIMUM[itype]

    # Instance leaderboards (wings/ strikes/ fractal scales)
    instances = Instance.objects.filter(type=itype).order_by("nr")
    for idx_instance, instance in enumerate(instances):
        discord_message_id = instance.discord_leaderboard_message_id

        # INSTANCE LEADERBOARDS
        # ----------------
        # Find wing clear times
        iclear_success_all = (
            instance.instance_clears.filter(
                success=True,
                emboldened=False,
                core_player_count__gte=min_core_count,
            )
            .filter(
                Q(start_time__gte=datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(days=365))
                & Q(start_time__lte=datetime.datetime.now(tz=pytz.UTC))
            )
            .order_by("duration")
        )

        description = ""

        # Strikes dont have average clear time currently
        if itype != "strike":
            description += f"{instance.emoji.discord_tag}"
            for idx, instance_clear in enumerate(iclear_success_all[:3]):
                description += get_rank_duration_str(instance_clear, iclear_success_all, itype)

            if len(iclear_success_all) > 0:
                # Add average cleartime of instance.
                avg_duration_str = get_avg_duration_str(iclear_success_all)
                description += f"{avg_duration_str}\n\n"

        # ENCOUNTER LEADERBOARDS
        # ----------------------
        # For each encounter in the instance, add a new row to the embed.
        field_value = description
        for encounter in instance.encounters.all().order_by("nr"):
            for cm in [False, True]:
                if cm:
                    emote = encounter.emoji.discord_tag_cm
                    cont = encounter.lb_cm
                else:
                    emote = encounter.emoji.discord_tag
                    cont = encounter.lb

                if not cont:
                    continue  # skip if not

                # Find encounter times
                encounter_success_all = (
                    encounter.dps_logs.filter(
                        success=True,
                        emboldened=False,
                        cm=cm,
                        core_player_count__gte=min_core_count,
                    )
                    .filter(
                        Q(start_time__gte=datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(days=9999))
                        & Q(start_time__lte=datetime.datetime.now(tz=pytz.UTC))
                    )
                    .order_by("duration")
                )

                if len(encounter_success_all) == 0:
                    continue

                # Go through top 3 logs and add this to the message
                field_value += f"{emote}"
                for idx, encounter_log in enumerate(encounter_success_all[:3]):
                    duration_str = get_duration_str(encounter_log.duration.seconds, add_space=True)
                    if encounter_log.core_player_count < settings.CORE_MINIMUM[itype]:
                        rank_emote = RANK_EMOTES_INVALID[idx]
                    else:
                        rank_emote = RANK_EMOTES[idx]
                    field_value += f"""[{rank_emote}]({encounter_log.url})`{duration_str}` """

                # Add average cleartime of encounter.
                avg_duration_str = get_avg_duration_str(encounter_success_all)
                field_value += f"{avg_duration_str}\n"

        embed_title = f"{instance.name}"
        if itype == "strike":  # strike needs emoji because it doenst have instance average
            embed_title = f"{instance.emoji.discord_tag} {instance.name}"

        embed = discord.Embed(
            title=embed_title,
            description=field_value,
            colour=EMBED_COLOR[instance.type],
        )

        if idx_instance == len(instances) - 1:
            embed.timestamp = datetime.datetime.now()
            embed.set_footer(text=f"Minimum core count: {settings.CORE_MINIMUM[itype]}\nLeaderboard last updated")

        # Try to update message. If message cant be found, create a new message instead.
        for attempt in range(2):
            try:
                webhook.edit_message(
                    message_id=discord_message_id,
                    embeds=[embed],
                    thread=thread,
                )
                print(f"Updating {instance.type}s leaderboard: {instance.name}")

            except (discord.errors.NotFound, discord.errors.HTTPException):
                print(f"Creating {instance.type}: {instance.name}")
                mess = webhook.send(
                    wait=True,
                    embeds=[discord.Embed(description=f"{instance.name} leaderboard is in the making")],
                    thread=thread,
                )

                discord_message_id = instance.discord_leaderboard_message_id = mess.id
                instance.save()
            else:  # stop when no exception raised
                break

    # %%
    itype = "raid"

    webhook = SyncWebhook.from_url(settings.WEBHOOK_BOT_CHANNEL_LEADERBOARD)  # FIXME delete after tests
    thread = Thread(settings.LEADERBOARD_THREADS[itype])

    if settings.INCLUDE_NON_CORE_LOGS:
        min_core_count = 0  # select all logs when including non core
    else:
        min_core_count = settings.CORE_MINIMUM[itype]

    instance_group = InstanceGroup.objects.get(name=itype)
    discord_message_id = instance_group.discord_message

    encounters = instance_group.encounters.all()
    instance_names = np.unique(encounters.values_list("instance__name", flat=True))
    instances = Instance.objects.filter(name__in=instance_names).order_by("nr")

    description = ""
    # For each instance add the encounters that are included and their
    # fastes and average killtime
    for instance in instances:
        # Instance emote
        description += f"{instance.emoji.discord_tag}"

        # Loop over the encounters
        counter = 0
        for ec in instance.encounters.filter(use_in_instance_group__name=itype).order_by("nr"):
            # encounter emote
            description += ec.emoji.discord_tag
            counter += 1

        # Add empty spaces to align.
        while counter < 6:
            description += BLANK_EMOTE
            counter += 1

        # Find instance clear fastest and average time
        iclear_success_all = (
            instance.instance_clears.filter(
                success=True,
                emboldened=False,
                core_player_count__gte=min_core_count,
            )
            .filter(
                Q(start_time__gte=datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(days=365))
                & Q(start_time__lte=datetime.datetime.now(tz=pytz.UTC))
            )
            .order_by("duration")
        )

        for idx, instance_clear in enumerate(iclear_success_all[:1]):
            description += get_rank_duration_str(instance_clear, iclear_success_all, itype)

        if len(iclear_success_all) > 0:
            # Add average clear times
            avg_duration_str = get_avg_duration_str(iclear_success_all)
            description += f"{avg_duration_str}\n"

    # List the top 3 of the instance group clear time #
    description += "\n"
    icleargroup_success_all = (
        InstanceClearGroup.objects.filter(
            success=True,
            type=itype,
            core_player_count__gte=min_core_count,
        )
        .filter(
            Q(start_time__gte=datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(days=365))
            & Q(start_time__lte=datetime.datetime.now(tz=pytz.UTC))
        )
        .order_by("duration")
    )

    for idx, icleargroup in enumerate(icleargroup_success_all[:3]):
        description += get_rank_duration_str(icleargroup, icleargroup_success_all, itype)

    if len(icleargroup_success_all) > 0:
        # Add average clear times
        description += get_avg_duration_str(icleargroup_success_all)

    # Create embed # --------------------------------------------------
    embed = discord.Embed(
        title=f"Full {itype.capitalize()} Clear",
        description=description,
        colour=EMBED_COLOR[instance.type],
    )
    embed.set_footer(text=f"Minimum core count: {settings.CORE_MINIMUM[itype]}\nLeaderboard last updated")
    embed.timestamp = datetime.datetime.now()

    # Try to update message. If message cant be found, create a new message instead.
    for attempt in range(2):
        try:
            webhook.edit_message(
                message_id=discord_message_id,
                embeds=[embed],
                thread=thread,
            )
            print(f"Updating {itype}s leaderboard: full clear")

        except (discord.errors.NotFound, discord.errors.HTTPException):
            print(f"Creating {itype}s leaderboard: full clear")
            mess = webhook.send(
                wait=True,
                embeds=[discord.Embed(description=f"{instance.name} leaderboard is in the making")],
                thread=thread,
            )
            discord_message = DiscordMessage.objects.create(message_id=mess.id)
            discord_message_id = instance_group.discord_message = discord_message
            instance_group.save()
        else:  # stop when no exception raised
            break


# %%

if __name__ == "__main__":
    for itype in [
        # "raid",
        # "strike",
        "fractal",
    ]:
        create_leaderboard(itype=itype)
