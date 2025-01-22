# %%
import datetime
from dataclasses import dataclass
from itertools import chain

import discord
import numpy as np
import pandas as pd
from django.db.models import Q

if __name__ == "__main__":
    from django_for_jupyter import init_django_from_commands

    init_django_from_commands("gw2_database")
from bot_settings import settings
from gw2_logs.models import (
    DpsLog,
    Emoji,
    Encounter,
    Instance,
    InstanceClear,
    InstanceClearGroup,
)
from scripts.log_helpers import (
    EMBED_COLOR,
    ITYPE_GROUPS,
    PLAYER_EMOTES,
    WEBHOOKS,
    WIPE_EMOTES,
    create_discord_time,
    create_or_update_discord_message,
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
            iclear.friend_player_count = int(np.median([log.friend_player_count for log in iclear.dps_logs.all()]))

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
    def create_from_date(cls, y, m, d, itype_group):
        """Create an instance clear group from a specific date."""
        # All logs in a day
        logs_day = DpsLog.objects.filter(
            start_time__year=y,
            start_time__month=m,
            start_time__day=d,
            encounter__instance__instance_group__name=itype_group,
        ).exclude(encounter__instance__instance_group__name="golem")

        if len(logs_day) == 0:
            return None

        name = f"{itype_group}s__{zfill_y_m_d(y, m, d)}"

        iclear_group, created = InstanceClearGroup.objects.update_or_create(name=name, type=itype_group)
        if created:
            print(f"Created InstanceClearGroup: {iclear_group}")

        # Create individual instance clears
        instances_day = np.unique([log.encounter.instance.name for log in logs_day])
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
    def icg_iclears_all(self):
        return self.iclear_group.instance_clears.all().order_by("start_time")

    def get_total_clear_duration(self):
        """Get the total duration for raids and fractals
        Duration is saved in the iclear_group.
        """

        # For raids and strikes we need to check multiple clears since they may not be done in one session.
        if self.iclear_group.type in ["raid", "strike"]:
            week_start = self.iclear_group.start_time - datetime.timedelta(
                days=self.iclear_group.start_time.weekday()
            )  # days are correct, but not hours and mins.
            week_start = week_start.replace(hour=8, minute=30, second=0, microsecond=0)  # Raid reset time.

            week_clears = InstanceClearGroup.objects.filter(type=self.iclear_group.type).filter(
                Q(start_time__gte=week_start) & Q(start_time__lte=self.iclear_group.start_time)
            )

            week_logs = DpsLog.objects.filter(
                id__in=[j.id for i in week_clears for j in i.dps_logs_all],
                encounter__leaderboard_instance_group__name=self.iclear_group.type,
            ).order_by("start_time")
            df_logs_duration = pd.DataFrame(
                week_logs.values_list("encounter", "success", "duration", "start_time", "start_time__day"),
                columns=["encounter", "success", "duration", "start_time", "start_day"],
            )

            # Drop duplicate successes. Shouldnt happen too much anyway...
            dupe_bool = df_logs_duration[df_logs_duration["success"]].duplicated("encounter")
            df_logs_duration.drop(dupe_bool[dupe_bool].index, inplace=True)

            if len(df_logs_duration[df_logs_duration["success"]]) == len(
                Encounter.objects.filter(leaderboard_instance_group__name=self.iclear_group.type)
            ):
                # if self.iclear_group.success is False:
                print(f"Finished {self.iclear_group.type}s for this week!")
                # Duration is the difference between first and last log for each day.
                # If there is only one log (e.g. strikes), that duration should be added.
                time_diff = datetime.timedelta(0)
                day_grouped_logs = df_logs_duration.groupby("start_day")
                for idx, day_group in day_grouped_logs:
                    maxidx = day_group["start_time"].idxmax()
                    time_diff += (
                        day_group.loc[maxidx, "start_time"]
                        + day_group.loc[maxidx, "duration"]
                        - day_group["start_time"].min()
                    )

                if any(day_grouped_logs["start_time"].count() == 1):
                    time_one_log = (
                        day_grouped_logs["duration"].first()[day_grouped_logs["start_time"].count() == 1]
                    ).sum()
                else:
                    time_one_log = pd.Timedelta(seconds=0)

                self.iclear_group.success = True
                self.iclear_group.duration = time_diff + time_one_log
                self.iclear_group.core_player_count = int(
                    np.median(
                        [
                            j.core_player_count
                            for i in week_clears
                            for j in i.instance_clears.all().order_by("start_time")
                        ]
                    )
                )
                self.iclear_group.friend_player_count = int(
                    np.median(
                        [
                            j.friend_player_count
                            for i in week_clears
                            for j in i.instance_clears.all().order_by("start_time")
                        ]
                    )
                )
                self.iclear_group.save()
            else:
                self.iclear_group.success = False
                self.iclear_group.duration = None
                self.iclear_group.core_player_count = None
                self.iclear_group.friend_player_count = None
                self.iclear_group.save()

        if self.iclear_group.type == "fractal":
            # If success instances equals total number of instances
            if sum(self.icg_iclears_all.values_list("success", flat=True)) == len(
                Instance.objects.filter(instance_group__name=self.iclear_group.type)
            ):
                print("Finished all fractals!")
                self.iclear_group.success = True
                self.iclear_group.duration = sum(
                    self.icg_iclears_all.values_list("duration", flat=True),
                    datetime.timedelta(),
                )
                self.iclear_group.core_player_count = int(
                    np.median([i.core_player_count for i in self.icg_iclears_all])
                )
                self.iclear_group.friend_player_count = int(
                    np.median([i.friend_player_count for i in self.icg_iclears_all])
                )
                self.iclear_group.save()

    def create_message(self):
        """Create a discord message from the available logs that are linked
        to the instance clear.
        """
        icg = self.iclear_group

        self.all_logs = list(chain(*[i.dps_logs.order_by("start_time") for i in self.icg_iclears_all]))
        # Find all iclears. Can be both strike and raid.
        all_success_logs = list(
            chain(*[i.dps_logs.filter(success=True).order_by("start_time") for i in self.icg_iclears_all])
        )

        descriptions = {}
        titles = {}

        # Put raid, strike, fractal in separate embeds.
        # for instance_type in instance_types:

        try:
            core_count = int(np.median([log.core_player_count for log in self.all_logs]))
            friend_count = int(np.median([log.friend_player_count for log in self.all_logs]))
            pug_count = int(np.median([log.player_count for log in self.all_logs])) - core_count - friend_count
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
        description = f"""{create_discord_time(self.all_logs[0].start_time)} - \
{create_discord_time(self.all_logs[-1].start_time + self.all_logs[-1].duration)} \
\n{pug_str}\n
"""
        # Add total instance group time if all bosses finished.
        # Loop through all instance clears in the same discord message.
        title = self.iclear_group.pretty_time
        if icg.success:
            # Get rank compared to all cleared instancecleargroups
            group = list(
                InstanceClearGroup.objects.filter(success=True, type=icg.type)
                .filter(
                    Q(start_time__gte=icg.start_time - datetime.timedelta(days=9999))
                    & Q(start_time__lte=icg.start_time)
                )
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
        for iclear in self.icg_iclears_all:
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

                    # If we dont have a success, we still need to calculate difference with previous log.
                    elif len(encounter_wipes) > 0:
                        diff_time = (
                            log.start_time
                            + log.duration
                            - (
                                self.all_logs[self.all_logs.index(log) - len(encounter_wipes)].start_time
                                + self.all_logs[self.all_logs.index(log) - len(encounter_wipes)].duration
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

        self.titles = titles
        self.descriptions = descriptions

        return titles, descriptions

    def send_discord_message(self):
        """Build the message from embeds and send to discord.
        This will create embeds when there are multiple types linked to the same discord
        message. So raids and strikes will be combined in one message.
        """

        # Find the clear groups. e.g. [raids__20240222, strikes__20240222]
        grp_lst = [self.iclear_group]
        if self.iclear_group.discord_message is not None:
            grp_lst += self.iclear_group.discord_message.instance_clear_group.all()
        grp_lst = sorted(set(grp_lst), key=lambda x: x.start_time)

        # combine embeds
        embeds = {}
        for icg in grp_lst:
            icgi = InstanceClearGroupInteraction.from_name(icg.name)

            titles, descriptions = icgi.create_message()
            icg_embeds = create_embeds(titles, descriptions)
            embeds.update(icg_embeds)
        embeds_mes = list(embeds.values())

        # Create/update the message
        create_or_update_discord_message(
            group=self.iclear_group,
            hook=WEBHOOKS[self.iclear_group.type],
            embeds_mes=embeds_mes,
        )


def create_embeds(titles, descriptions):
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
                    embeds[f"{instance_type}_{embed_id}"].add_field(name=field_name, value=field_value, inline=False)

    return embeds


# %%

if __name__ == "__main__":
    y, m, d = 2024, 6, 13
    itype_group = "raid"

    self = icgi = InstanceClearGroupInteraction.create_from_date(y=y, m=m, d=d, itype_group=itype_group)
    if icgi is not None:
        # Set the same discord message id when strikes and raids are combined.
        if (ITYPE_GROUPS["raid"] == ITYPE_GROUPS["strike"]) and (icgi.iclear_group.type in ["raid", "strike"]):
            if self.iclear_group.discord_message is None:
                group_names = [
                    "__".join([f"{j}s", self.iclear_group.name.split("__")[1]]) for j in ITYPE_GROUPS["raid"]
                ]
                self.iclear_group.discord_message_id = (
                    InstanceClearGroup.objects.filter(name__in=group_names)
                    .exclude(discord_message=None)
                    .values_list("discord_message", flat=True)
                    .first()
                )
                self.iclear_group.save()

        # Find the clear groups. e.g. [raids__20240222, strikes__20240222]
        grp_lst = [icgi.iclear_group]
        if icgi.iclear_group.discord_message is not None:
            grp_lst += icgi.iclear_group.discord_message.instance_clear_group.all()
        grp_lst = sorted(set(grp_lst), key=lambda x: x.start_time)

        # combine embeds
        embeds = {}
        for icg in grp_lst:
            icgi = InstanceClearGroupInteraction.from_name(icg.name)
            print(icg.name)
            titles, descriptions = icgi.create_message()
            icg_embeds = create_embeds(titles, descriptions)
            embeds.update(icg_embeds)
        embeds_mes = list(embeds.values())

        create_or_update_discord_message(
            group=icgi.iclear_group,
            hook=WEBHOOKS[icgi.iclear_group.type],
            embeds_mes=embeds_mes,
        )


# # %%
# from log_helpers import RANK_EMOTES, RANK_EMOTES_CUSTOM, RANK_EMOTES_CUSTOM_INVALID, RANK_EMOTES_INVALID

# # from gw2_logs.models import DpsLog
# log = DpsLog.objects.get(url='https://dps.report/s5ZG-20240216-192127_skor')

# encounter_success_all = list(
#     log.encounter.dps_logs.filter(success=True, cm=log.cm, emboldened=False)
#     .filter(Q(start_time__gte=log.start_time - datetime.timedelta(days=9999)) & Q(start_time__lte=log.start_time))
#     .order_by("duration")
# )

# indiv = log
# group = encounter_success_all
# core_minimum = settings.CORE_MINIMUM[log.encounter.instance.instance_group.name]
# custom_emoji_name = False

# MEDAL_TYPE = "percentiles"
# if True:
#     emboldened = False
#     if hasattr(indiv, "emboldened"):
#         emboldened = indiv.emboldened

#     if indiv.success and not emboldened:
#         rank = group.index(indiv)
#     else:
#         rank = None

#     # When amount of players is below the minimum it will still show rank but with a different emote.
#     if indiv.core_player_count < core_minimum:
#         if custom_emoji_name:
#             emote_dict = RANK_EMOTES_CUSTOM_INVALID
#         else:
#             emote_dict = RANK_EMOTES_INVALID
#     else:
#         if custom_emoji_name:
#             emote_dict = RANK_EMOTES_CUSTOM
#         else:
#             emote_dict = RANK_EMOTES

#     rank = 5
#     # Ranks 1, 2 and 3.
#     # if rank in emote_dict:
#     #     rank_str = emote_dict[rank]

#     # Other ranks
#     if emboldened:
#         rank_str = emote_dict["emboldened"]
#     else:
#         if MEDAL_TYPE == "avg":
#             rank_str = emote_dict["average"]
#             if indiv.success:
#                 if indiv.duration.seconds < (
#                     getattr(np, settings.MEAN_OR_MEDIAN)([i.duration.seconds for i in group]) - 5
#                 ):
#                     rank_str = emote_dict["above_average"]
#                 elif indiv.duration.seconds > (
#                     getattr(np, settings.MEAN_OR_MEDIAN)([i.duration.seconds for i in group]) + 5
#                 ):
#                     rank_str = emote_dict["below_average"]
#         if MEDAL_TYPE == "percentiles":
#             inverse_rank = group[::-1].index(indiv)
#             percentile_rank = (inverse_rank+1)/ len(group) * 100
#             rank_binned = np.searchsorted(settings.RANK_BINS_PERCENTILE, percentile_rank, side="left")
#             rank_str = RANK_EMOTES_CUSTOM[rank_binned].format(int(percentile_rank))


# print(rank_str)

# # %%
# from scipy.stats import percentileofscore

# # Calculate percentile of duration
# # Rank '0' is better than 100% of logs. We need to invert the groups to say this log is
# # better than 100% of logs.

# inverse_rank = group[::-1].index(indiv)
# percentile_rank = inverse_rank / len(group) * 100
# rank_binned = np.searchsorted(settings.RANK_BINS_PERCENTILE, percentile_rank, side="left")
# RANK_EMOTES_CUSTOM[rank_binned]

# %%
