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

import requests
from gw2_logs.models import DpsLog, Emoji, Encounter, Instance, InstanceClear, InstanceClearGroup, Player

from bot_settings import settings


@dataclass
class Thread:
    """Discordpy seems to be rather picky about threads.
    When sending a message it just needs a class with an id
    to work. So here we are.
    """

    id: int


url = settings.WEBHOOK_BOT_CHANNEL_LEADERBOARD
webhook = SyncWebhook.from_url(settings.WEBHOOK_BOT_CHANNEL_LEADERBOARD)


# %%
EMBED_COLOR = {
    "raid": 7930903,
    "strike": 6603422,
    "fractal": 5512822,
}

RANK_STR = {
    0: ":first_place:",
    1: ":second_place:",
    2: ":third_place:",
    "average": f"{Emoji.objects.get(name='average').discord_tag}",
}


def get_duration_str(seconds: int):
    """Get seconds with datetime.timedelta.seconds"""
    mins, secs = divmod(seconds, 60)
    if len(str(mins)) == 1:
        mins = f" {mins}"
    return f"{mins}:{str(secs).zfill(2)}"


# for itype in [
#     "strike",
# ]:
for itype in [
    "raid",
    "strike",
    "fractal",
]:
    instances = Instance.objects.filter(type=itype).order_by("nr")
    for idx_instance, instance in enumerate(instances):
        # for instance in [Instance.objects.filter(type=itype).order_by("nr")[5]]:
        # instance = Instance.objects.filter(name="Spirit Vale").first()
        discord_message_id = instance.discord_leaderboard_message_id

        # Create a message if it doesnt exist yet
        if discord_message_id is None:
            mess = webhook.send(
                wait=True,
                embeds=[discord.Embed(description=f"{instance.name} leaderboard is in the making")],
                thread=Thread(settings.LEADERBOARD_THREADS[instance.type]),
            )

            discord_message_id = instance.discord_leaderboard_message_id = mess.id
            instance.save()

        # INSTANCE LEADERBOARDS
        # ----------------
        # Find wing clear times
        iclear_success_all = (
            instance.instance_clears.filter(success=True, emboldened=False)
            .filter(
                Q(start_time__gte=datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(days=365))
                & Q(start_time__lte=datetime.datetime.now(tz=pytz.UTC))
            )
            .order_by("duration")
        )

        description = ""
        if itype != "strike":
            description += f"{instance.emoji.discord_tag}"
            for idx, instance_clear in enumerate(iclear_success_all[:3]):
                duration_str = get_duration_str(instance_clear.duration.seconds)
                description += f"{RANK_STR[idx]}`{duration_str}` "

            # Add average clear times
            avg_time = int(np.mean([e[0].seconds for e in iclear_success_all.values_list("duration")]))
            avg_duration_str = get_duration_str(avg_time)
            description += f"{RANK_STR['average']}`{avg_duration_str}`\n\n"

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
                    encounter.dps_logs.filter(success=True, emboldened=False, cm=cm)
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
                    field_value += f"""[{RANK_STR[idx]}]({encounter_log.url})`{duration_str}` """

                # Add average cleartime of encounter.
                field_value += f"{RANK_STR['average']}`{avg_duration_str}`\n"

        # embed.add_field(name="", value=field_value, inline=False)

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
            embed.set_footer(text="Leaderboard last updated")

        webhook.edit_message(
            message_id=discord_message_id,
            embeds=[embed],
            thread=Thread(settings.LEADERBOARD_THREADS[instance.type]),
        )
        # break
        # # DELETE MESSAGES
        # webhook.delete_message(discord_message_id,
        #     thread=Thread(settings.LEADERBOARD_THREADS[instance.type]),
        # )
        # instance.discord_leaderboard_message_id = None
        # instance.save()

        # break

# %%
