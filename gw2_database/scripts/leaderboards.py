# %%

# %%
import datetime
import sys
from dataclasses import dataclass

import discord
import numpy as np
import pytz
from discord import SyncWebhook
from django.db.models import Q

if __name__ == "__main__":
    # -- temp TESTING --
    sys.path.append("../../nbs")
    from django_for_jupyter import init_django_from_commands

    init_django_from_commands("gw2_database")
    # -- temp TESTING --

from gw2_logs.models import DpsLog, Emoji, Encounter, Instance, InstanceClear, InstanceClearGroup, Player
from log_helpers import EMBED_COLOR, RANK_EMOTES, RANK_EMOTES_INVALID, get_duration_str

from bot_settings import settings


@dataclass
class Thread:
    """Discordpy seems to be rather picky about threads.
    When sending a message it just needs a class with an id
    to work. So here we are.
    """

    id: int


webhook = SyncWebhook.from_url(settings.WEBHOOK_BOT_CHANNEL_LEADERBOARD)

# %%


for itype in [
    "raid",
    "strike",
    "fractal",
]:
    if settings.INCLUDE_NON_CORE_LOGS:
        min_core_count = 0
    else:
        min_core_count = settings.CORE_MINIMUM[itype]

    instances = Instance.objects.filter(type=itype).order_by("nr")
    for idx_instance, instance in enumerate(instances):
        # for instance in [Instance.objects.filter(type=itype).order_by("nr")[5]]:
        # instance = Instance.objects.filter(name="Spirit Vale").first()
        discord_message_id = instance.discord_leaderboard_message_id
        thread = Thread(settings.LEADERBOARD_THREADS[instance.type])

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
                duration_str = get_duration_str(instance_clear.duration.seconds)

                if instance_clear.core_player_count < settings.CORE_MINIMUM[itype]:
                    rank_emote = RANK_EMOTES_INVALID[idx]
                else:
                    rank_emote = RANK_EMOTES[idx]
                description += f"{rank_emote}`{duration_str}` "

            if len(iclear_success_all) > 0:
                # Add average clear times
                avg_time = int(np.mean([e[0].seconds for e in iclear_success_all.values_list("duration")]))
                avg_duration_str = get_duration_str(avg_time)
                description += f"{RANK_EMOTES['average']}`{avg_duration_str}`\n\n"

        # ENCOUNTER LEADERBOARDS
        # ----------------------
        # For each encounter in the instance, add a new field to the embed.
        field_value = description
        for encounter in instance.encounters.all().order_by("nr"):
            for cm in [False, True]:
                emote = encounter.emoji.discord_tag
                cont = encounter.lb
                if cm:
                    emote = encounter.emoji.discord_tag_cm
                    cont = encounter.lb_cm

                if not cont:
                    continue  # skip if not

                nam = encounter.shortname
                if nam is None:
                    nam = encounter.name[:4]
                field_name = f"{emote} {nam}"

                # Find encounter times
                encounter_success_all = (
                    encounter.dps_logs.filter(
                        success=True,
                        emboldened=False,
                        cm=cm,
                        core_player_count__gte=min_core_count,
                    )
                    .filter(
                        Q(start_time__gte=datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(days=365))
                        & Q(start_time__lte=datetime.datetime.now(tz=pytz.UTC))
                    )
                    .order_by("duration")
                )

                if len(encounter_success_all) == 0:
                    continue

                avg_time = int(np.mean([e[0].seconds for e in encounter_success_all.values_list("duration")]))
                avg_duration_str = get_duration_str(avg_time)

                # Go through top 3 logs and add this to the message
                field_value += f"{emote}"
                for idx, encounter_log in enumerate(encounter_success_all[:3]):
                    duration_str = get_duration_str(encounter_log.duration.seconds)
                    if encounter_log.core_player_count < settings.CORE_MINIMUM[itype]:
                        rank_emote = RANK_EMOTES_INVALID[idx]
                    else:
                        rank_emote = RANK_EMOTES[idx]
                    field_value += f"""[{rank_emote}]({encounter_log.url})`{duration_str}` """

                # Add average cleartime of encounter.
                field_value += f"{RANK_EMOTES['average']}`{avg_duration_str}`\n"

        embed_title = f"{instance.name}"
        if itype == "strike":
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
                print(f"Updating {instance.type}: {instance.name}")

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
