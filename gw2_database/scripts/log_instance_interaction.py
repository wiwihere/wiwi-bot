import datetime
from dataclasses import dataclass
from itertools import chain

import discord
import numpy as np
from discord import SyncWebhook
from django.db.models import Q

if __name__ == "__main__":
    from django_for_jupyter import init_django_from_commands

    init_django_from_commands("gw2_database")
from bot_settings import settings
from gw2_logs.models import DpsLog, Emoji, Encounter, Instance, InstanceClear, InstanceClearGroup, Player
from scripts.log_helpers import (
    EMBED_COLOR,
    ITYPE_GROUPS,
    WIPE_EMOTES,
    create_discord_time,
    get_duration_str,
    get_rank_emote,
    zfill_y_m_d,
)


@dataclass
class InstanceClearInteraction:
    """Single instance clear; raidwing or fractal scale or strikes grouped per expansion."""

    iclear: InstanceClear

    @classmethod
    def from_logs(cls, logs: list[DpsLog], instance_group=None):
        """Log should be filtered on instance"""
        iname = f"{logs[0].encounter.instance.name_lower}__{logs[0].start_time.strftime('%Y%m%d')}"

        # Check if all logs are from the same wing.
        same_wing = all(log.encounter.instance == logs[0].encounter.instance for log in logs)
        if not same_wing:
            raise ValueError("Not all logs of same wing.")

        # Create or update instance
        iclear, created = InstanceClear.objects.update_or_create(
            defaults={
                "instance": logs[0].encounter.instance,
                "instance_clear_group": instance_group,
            },
            name=iname,
        )
        if created:
            print(f"Created {iclear}")

        # All logs that are not yet part of the instance clear will be added.
        for log in set(logs).difference(set(iclear.dps_logs.all())):
            log.instance_clear = iclear
            log.save()

        # Update start_time
        iclear.start_time = iclear.dps_logs.all().order_by("start_time").first().start_time

        # Calculate duration
        last_log = iclear.dps_logs.all().order_by("start_time").last()
        iclear.duration = last_log.start_time + last_log.duration - iclear.start_time

        if len(iclear.dps_logs.all()) > 0:
            iclear.core_player_count = int(np.median([log.core_player_count for log in iclear.dps_logs.all()]))

        # Check if all encounters have been finished.
        encounter_count = max([i.nr for i in iclear.instance.encounters.all()])

        iclear.success = False
        if len(iclear.dps_logs.filter(success=True)) == encounter_count:
            iclear.success = True

        iclear.emboldened = False
        if len(iclear.dps_logs.filter(success=True, emboldened=True)) > 0:
            iclear.emboldened = True

        iclear.save()
        return cls(iclear)

    @classmethod
    def from_name(cls, name):
        return cls(InstanceClear.objects.get(name=name))


@dataclass
class InstanceClearGroupInteraction:
    iclear_group: InstanceClearGroup

    def __post_init__(self):
        self.get_total_clear_duration()

    @classmethod
    def create_from_date(cls, y, m, d, fractal=False):
        """Create an instance clear group from a specific date."""
        # All logs in a day
        logs_day = DpsLog.objects.filter(
            start_time__year=y,
            start_time__month=m,
            start_time__day=d,
        )

        # Get itypes (raid or fractal)
        itypes = list(set(ITYPE_GROUPS[i] for i in logs_day.values_list("encounter__instance__type", flat=True)))

        if len(itypes) == 0:
            raise Exception("No itypes?")  # No logs

        if len(itypes) == 1:
            itype = itypes[0]
        elif len(itypes) > 1:
            itype = input(f"Multiple instance types for given period. Choose: {itypes}")

        # TODO grouping raids and strikes doesnt really work nicely.
        if itype == "fractal":
            logs_day = logs_day.filter(encounter__instance__type="fractal")
        else:
            logs_day = logs_day.exclude(encounter__instance__type="fractal")

        name = f"{itype}s__{zfill_y_m_d(y,m,d)}"

        instances_day = np.unique([log.encounter.instance.name for log in logs_day])

        iclear_group, created = InstanceClearGroup.objects.update_or_create(name=name, type=itype)
        if created:
            print(f"Created InstanceClearGroup: {iclear_group}")

        # Create individual instance clears
        for instance_name in instances_day:
            logs_instance = logs_day.filter(encounter__instance__name=instance_name)
            ici = InstanceClearInteraction.from_logs(logs=logs_instance, instance_group=iclear_group)

        # Set start time of clear
        if iclear_group.instance_clears.all():
            start_time = min([i.start_time for i in iclear_group.instance_clears.all()])
            if iclear_group.start_time != start_time:
                iclear_group.start_time = start_time
                iclear_group.save()

        return cls(iclear_group)

    @classmethod
    def from_name(cls, name):
        return cls(InstanceClearGroup.objects.get(name=name))

    @property
    def clears_by_date(self):
        return self.iclear_group.instance_clears.all().order_by("start_time")

    def get_total_clear_duration(self):
        """Get the total duration for raids and fractals
        Duration is saved in the iclear_group.
        """
        if self.iclear_group.type == "raid":
            # For raids we need to check multiple clears since they may not be done in one session.
            week_start = self.iclear_group.start_time - datetime.timedelta(
                days=self.iclear_group.start_time.weekday()
            )  # days are correct, but not hours and mins.
            week_start = week_start.replace(hour=8, minute=30, second=0, microsecond=0)  # Raid reset time.

            week_clears = InstanceClearGroup.objects.filter(type="raid").filter(
                Q(start_time__gte=week_start) & Q(start_time__lte=self.iclear_group.start_time)
            )
            successes = list(
                chain(*[j.instance_clears.filter(instance__type="raid", success=True) for j in week_clears])
            )

            if len(successes) == len(Instance.objects.filter(type=self.iclear_group.type)):
                print("Finished a whole instance group!")
                self.iclear_group.success = True
                self.iclear_group.duration = sum([ic.duration for ic in successes], datetime.timedelta())
                self.iclear_group.core_player_count = int(
                    np.median([i.core_player_count for i in self.clears_by_date])
                )

                self.iclear_group.save()

        if self.iclear_group.type == "fractal":
            # If success instances equals total number of instances
            if sum(self.clears_by_date.values_list("success", flat=True)) == len(
                Instance.objects.filter(type=self.iclear_group.type)
            ):
                print("Finished all fracals!")
                self.iclear_group.success = True
                self.iclear_group.duration = sum(
                    self.clears_by_date.values_list("duration", flat=True),
                    datetime.timedelta(),
                )
                self.iclear_group.core_player_count = int(
                    np.median([i.core_player_count for i in self.clears_by_date])
                )
                self.iclear_group.save()

    def create_message(self):
        """Create a discord message from the available logs that are linked
        to the instance clear.
        """
        self.all_logs = list(chain(*[i.dps_logs.order_by("start_time") for i in self.clears_by_date]))

        instance_types = np.unique([i.instance.type for i in self.clears_by_date])

        descriptions = {}
        titles = {}

        # Put raid, strike, fractal in separate embeds.
        for instance_type in instance_types:
            core_emote = Emoji.objects.get(name="core").discord_tag
            pug_emote = Emoji.objects.get(name="pug").discord_tag
            try:
                core_count = int(np.median([log.core_player_count for log in self.all_logs]))
                pug_count = int(np.median([log.player_count for log in self.all_logs])) - core_count
            except TypeError:
                core_count = 0
                pug_count = 0

            # Nina's space, add space after 5 ducks for better readability.
            pug_split_str = f"{core_emote*core_count}{pug_emote*pug_count}".split(">")
            pug_split_str[5] = f" {pug_split_str[5]}"  # empty str here:`⠀`
            pug_str = ">".join(pug_split_str)

            # title description with start - end time and colored ducks for core/pugs
            description = f"""{create_discord_time(self.all_logs[0].start_time)} - \
{create_discord_time(self.all_logs[-1].start_time+self.all_logs[-1].duration)} \
\n{pug_str}\n
"""

            title = self.iclear_group.pretty_time
            # Add total instance group time if all bosses finished.

            if self.iclear_group.success:
                # Get rank compared to all cleared instancecleargroups
                group = list(
                    InstanceClearGroup.objects.filter(success=True, type=self.iclear_group.type)
                    .filter(
                        Q(start_time__gte=self.iclear_group.start_time - datetime.timedelta(days=9999))
                        & Q(start_time__lte=self.iclear_group.start_time)
                    )
                    .order_by("duration")
                )
                rank_str = get_rank_emote(
                    indiv=self.iclear_group,
                    group=group,
                    core_minimum=settings.CORE_MINIMUM[self.iclear_group.type],
                )

                duration_str = get_duration_str(self.iclear_group.duration.seconds)
                title += f"⠀⠀⠀⠀{rank_str} **{duration_str}** {rank_str} \n"

            titles[instance_type] = {}
            titles[instance_type]["main"] = title
            descriptions[instance_type] = {}
            descriptions[instance_type]["main"] = description

        # Loop over the instance clears
        first_boss = True  # Tracks if a log is the first boss of all logs.
        for iclear in self.clears_by_date:
            titles[iclear.instance.type][iclear.name] = ""  # field title
            descriptions[iclear.instance.type][iclear.name] = ""  # field description

            # Find rank of full instance on leaderboard
            iclear_success_all = None
            if iclear.success:
                iclear_success_all = list(
                    iclear.instance.instance_clears.filter(success=True)
                    .filter(
                        Q(start_time__gte=iclear.start_time - datetime.timedelta(days=9999))
                        & Q(start_time__lte=iclear.start_time)
                    )
                    .order_by("duration")
                )
            rank_str = get_rank_emote(
                indiv=iclear,
                group=iclear_success_all,
                core_minimum=settings.CORE_MINIMUM[iclear.instance.type],
            )

            # Cleartime wing
            duration_str = get_duration_str(iclear.duration.seconds)

            titles[iclear.instance.type][
                iclear.name
            ] = f"**__{iclear.instance.emoji.discord_tag}{rank_str}{iclear.name.split('__')[0].replace('_', ' ').title()} \
({duration_str})__**\n"
            field_value = ""

            instance_logs = iclear.dps_logs.order_by("start_time")
            all_success_logs = list(
                chain(*[i.dps_logs.filter(success=True).order_by("start_time") for i in self.clears_by_date])
            )

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
                        diff_time = log.start_time - self.all_logs[0].start_time
                        if not encounter_success:
                            diff_time = log.start_time + log.duration - self.all_logs[0].start_time

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
                if log.success:
                    first_boss = False  # Only after a successful log the first_boss is cleared.

                # Find rank of boss on leaderboard filter for logs of last year.
                encounter_success_all = None
                if log.success:
                    encounter_success_all = list(
                        log.encounter.dps_logs.filter(success=True, cm=log.cm)
                        .filter(
                            Q(start_time__gte=log.start_time - datetime.timedelta(days=9999))
                            & Q(start_time__lte=log.start_time)
                        )
                        .order_by("duration")
                    )
                rank_str = get_rank_emote(
                    indiv=log,
                    group=encounter_success_all,
                    core_minimum=settings.CORE_MINIMUM[log.encounter.instance.type],
                )

                # Wipes also get an url, can be click the emote to go there. Doesnt work on phone.
                # Dont show wipes that are under 15 seconds.
                wipe_str = ""
                for wipe in encounter_wipes:
                    if wipe.duration.seconds > 15:
                        wipe_emote = WIPE_EMOTES[np.ceil(wipe.final_health_percentage / 12.5)]
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
                            cm_str = ""
                            if log.cm:
                                cm_str = " CM"
                            field_value += f"{log.emoji_tag}{rank_str}{log.encounter.name}{cm_str} (wipe)_+{duration_str}_{wipe_str}\n"

            # Add the field text to the embed. Raids and strikes have a
            # larger chance that the field_value is larger than 1024 charcters.
            # This is sadly currently the limit on embed.field.value.
            # Descriptions can be 4096 characters, so instead of a field we just edit the description.
            descriptions[iclear.instance.type][iclear.name] = field_value

        self.titles = titles
        self.descriptions = descriptions

        return titles, descriptions

    def create_embeds(self, titles, descriptions):
        """Create discord embed from description."""
        embeds = {}
        has_title = False
        for instance_type in titles:
            use_fields = True  # max 1024 per field
            field_characters = np.array([len(i) for i in descriptions[instance_type].values()])
            # Check field length. If more than 1024 it cannot go to a field and should instead
            # go to description
            if np.any(field_characters > 1024):
                print("Cannot use fields because one has more than 1024 chars")
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
                            print(len(description))

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
                        embeds[f"{instance_type}_{embed_id}"].add_field(
                            name=field_name, value=field_value, inline=False
                        )

        return embeds

    def create_or_update_discord_message(self, embeds):
        """Send message to discord created by .create_message to discord"""

        # Combine raid and strike embeds in the same group.
        embeds_split = {}
        embeds_split["fractal"] = [embeds[i] for i in embeds if "fractal_" in i]
        embeds_split["raid"] = [embeds[i] for i in embeds if "fractal_" not in i]

        webhooks = {}
        webhooks["fractal"] = SyncWebhook.from_url(settings.WEBHOOK_BOT_CHANNEL_FRACTAL)
        webhooks["raid"] = SyncWebhook.from_url(settings.WEBHOOK_BOT_CHANNEL_RAID)

        # Update message if it exists
        for embeds_instance, webhook in zip(embeds_split.values(), webhooks.values()):
            if embeds_instance == []:
                continue

            # Try to update message. If message cant be found, create a new message instead.
            try:
                webhook.edit_message(
                    message_id=self.iclear_group.discord_message_id,
                    embeds=embeds_instance,
                )
                print("Updating discord message")

            except (discord.errors.NotFound, discord.errors.HTTPException):
                mess = webhook.send(wait=True, embeds=embeds_instance)
                self.iclear_group.discord_message_id = mess.id
                self.iclear_group.save()
                print("New discord message created")