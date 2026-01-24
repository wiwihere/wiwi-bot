# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import logging

import discord
from django.conf import settings
from gw2_logs.models import (
    Encounter,
    Instance,
    InstanceClearGroup,
    InstanceGroup,
)
from scripts.discord_interaction.send_message import create_or_update_discord_message
from scripts.log_helpers import (
    BLANK_EMOTE,
    EMBED_COLOR,
    WEBHOOKS,
    Thread,
    get_avg_duration_str,
    get_rank_duration_str,
)

logger = logging.getLogger(__name__)
# TODO remove ITYPE_GROUPS
if __name__ == "__main__":
    itype = "raid"
    min_core_count = 0  # select all logs when including non core


# %%
def create_leaderboard(itype: str):
    """"""
    # %%
    if settings.INCLUDE_NON_CORE_LOGS:
        min_core_count = 0  # select all logs when including non core
    else:
        min_core_count = settings.CORE_MINIMUM[itype]

    # Instance leaderboards (wings/ strikes/ fractal scales)
    instances = Instance.objects.filter(instance_group__name=itype).order_by("nr")
    for instance in instances:
        # INSTANCE LEADERBOARDS
        # ----------------
        # Find wing clear times
        iclear_success_all = (
            instance.instance_clears.filter(
                success=True,
                emboldened=False,
                core_player_count__gte=min_core_count,
            )
            # .filter(
            #     Q(start_time__gte=datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(days=365))
            #     & Q(start_time__lte=datetime.datetime.now(tz=pytz.UTC))
            # )
            .order_by("duration")
        )

        description = ""

        # Strikes dont have average clear time currently # FIXME
        if itype != "strike":
            description += f"{instance.emoji.discord_tag()}"
            for idx, instance_clear in enumerate(iclear_success_all[:3]):
                rank_duration_str = get_rank_duration_str(instance_clear, iclear_success_all, itype, pretty_time=True)
                description += rank_duration_str

            if len(iclear_success_all) > 0:
                # Add average cleartime of instance.
                avg_duration_str = get_avg_duration_str(iclear_success_all)
                description += f"{avg_duration_str}\n\n"

        # ENCOUNTER LEADERBOARDS
        # ----------------------
        # For each encounter in the instance, add a new row to the embed.
        field_value = description
        for encounter in instance.encounters.all().order_by("nr"):
            for difficulty in ["normal", "cm", "lcm"]:
                if difficulty == "normal":
                    cm = False
                    lcm = False
                    cont = encounter.lb
                if difficulty == "cm":
                    cm = True
                    lcm = False
                    cont = encounter.lb_cm
                if difficulty == "lcm":
                    cm = True
                    lcm = True
                    cont = encounter.lb_lcm

                emote = encounter.emoji.discord_tag(difficulty)

                if not cont:
                    continue  # skip if encounter is not selected to be on leaderboard

                # Find encounter times
                encounter_success_all = (
                    encounter.dps_logs.filter(
                        success=True,
                        emboldened=False,
                        cm=cm,
                        lcm=lcm,
                        core_player_count__gte=min_core_count,
                    )
                    # .filter(
                    #     Q(start_time__gte=datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(days=9999))
                    #     & Q(start_time__lte=datetime.datetime.now(tz=pytz.UTC))
                    # )
                    .order_by("duration")
                )

                if len(encounter_success_all) == 0:
                    continue

                # Go through top 3 logs and add this to the message
                field_value += f"{emote}"

                # FIXME
                # for idx, encounter_log in enumerate(encounter_success_all[:3]):
                #     duration_str = get_duration_str(encounter_log.duration.seconds, add_space=True)
                #     if encounter_log.core_player_count < settings.CORE_MINIMUM[itype]:
                #         rank_emote = RANK_EMOTES_INVALID[idx]
                #     else:
                #         rank_emote = RANK_EMOTES[idx]
                #     field_value += f"""[{rank_emote}]({encounter_log.url})`{duration_str}` """

                for idx, encounter_log in enumerate(encounter_success_all[:3]):
                    rank_duration_str = get_rank_duration_str(
                        encounter_log, encounter_success_all, itype, pretty_time=True, url=encounter_log.url
                    )
                    field_value += rank_duration_str

                # Add average cleartime of encounter.
                avg_duration_str = get_avg_duration_str(encounter_success_all)
                field_value += f"{avg_duration_str}\n"

        embed_title = f"{instance.name}"
        # TODO strike should have average too
        if itype == "strike":  # strike needs emoji because it doenst have instance average
            embed_title = f"{instance.emoji.discord_tag()} {instance.name}"

        embed = discord.Embed(
            title=embed_title,
            description=field_value,
            colour=EMBED_COLOR[instance.instance_group.name],
        )

        create_or_update_discord_message(
            group=instance,
            hook=WEBHOOKS["leaderboard"],
            embeds_messages_list=[embed],
            thread=Thread(settings.LEADERBOARD_THREADS[itype]),
        )

    # %%
    # Create message for total clear time.
    instance_group = InstanceGroup.objects.get(name=itype)
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

    create_or_update_discord_message(
        group=instance_group,
        hook=WEBHOOKS["leaderboard"],
        embeds_messages_list=[embed],
        thread=Thread(settings.LEADERBOARD_THREADS[itype]),
    )


# %%
if __name__ == "__main__":
    for itype in [
        "raid",
        # "strike",
        # "fractal",
    ]:
        pass
        # create_leaderboard(itype=itype)
