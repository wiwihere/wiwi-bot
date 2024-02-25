# %%

# %%
import datetime

import discord
import numpy as np
import pytz
from discord import SyncWebhook
from django.db.models import Q

if __name__ == "__main__":
    from django_for_jupyter import init_django_from_commands

    init_django_from_commands("gw2_database")

from bot_settings import settings
from gw2_logs.models import Instance
from scripts.log_helpers import EMBED_COLOR, RANK_EMOTES, RANK_EMOTES_INVALID, Thread, get_duration_str


# %%
def create_leaderboard(itype: str):
    webhook = SyncWebhook.from_url(settings.WEBHOOK_BOT_CHANNEL_LEADERBOARD)

    if settings.INCLUDE_NON_CORE_LOGS:
        min_core_count = 0  # select all logs when including non core
    else:
        min_core_count = settings.CORE_MINIMUM[itype]

    instances = Instance.objects.filter(type=itype).order_by("nr")
    for idx_instance, instance in enumerate(instances):
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
                duration_str = get_duration_str(instance_clear.duration.seconds, add_space=True)

                if instance_clear.core_player_count < settings.CORE_MINIMUM[itype]:
                    rank_emote = RANK_EMOTES_INVALID[idx]
                else:
                    rank_emote = RANK_EMOTES[idx]
                description += f"{rank_emote}`{duration_str}` "

            if len(iclear_success_all) > 0:
                # Add average clear times
                avg_time = int(
                    getattr(np, settings.MEAN_OR_MEDIAN)(
                        [e[0].seconds for e in iclear_success_all.values_list("duration")]
                    )
                )
                avg_duration_str = get_duration_str(avg_time, add_space=True)
                description += f"{RANK_EMOTES[settings.MEAN_OR_MEDIAN]}`{avg_duration_str}`\n\n"

        # ENCOUNTER LEADERBOARDS
        # ----------------------
        # For each encounter in the instance, add a new row to the embed.
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

                avg_time = int(
                    getattr(np, settings.MEAN_OR_MEDIAN)(
                        [e[0].seconds for e in encounter_success_all.values_list("duration")]
                    )
                )
                avg_duration_str = get_duration_str(avg_time, add_space=True)

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
                field_value += f"{RANK_EMOTES[settings.MEAN_OR_MEDIAN]}`{avg_duration_str}`\n"

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


if __name__ == "__main__":
    for itype in [
        # "raid",
        # "strike",
        "fractal",
    ]:
        create_leaderboard(itype=itype)

# %%
