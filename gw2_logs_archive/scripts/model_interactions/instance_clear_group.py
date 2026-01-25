# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import logging
from dataclasses import dataclass

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
from scripts.discord_interaction.build_embeds import create_discord_embeds
from scripts.discord_interaction.build_message import create_discord_message
from scripts.discord_interaction.send_message import (
    create_or_update_discord_message,
    create_or_update_discord_message_current_week,
)
from scripts.log_helpers import (
    ITYPE_GROUPS,
    get_rank_emote,
    zfill_y_m_d,
)
from scripts.model_interactions.instance_clear import InstanceClearInteraction

logger = logging.getLogger(__name__)


@dataclass
class InstanceClearGroupInteraction:
    iclear_group: InstanceClearGroup
    update_total_duration: bool = True

    def __post_init__(self):
        if self.update_total_duration:
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
            # Select the encounters used to calculate the success and duration.
            # This is only done once on creation
            # creates a string like; "1_1__1_2__1_3__2_1.."
            encounters = Encounter.objects.filter(
                use_for_icg_duration=True,
                instance__instance_group__name=iclear_group.type,
            )
            duration_encounters = "__".join([f"{a.instance.nr}_{a.nr}" for a in encounters])
            iclear_group.duration_encounters = duration_encounters
            iclear_group.save()
            logger.info(f"Created InstanceClearGroup: {iclear_group}")

        # Create individual instance clears
        instances_day = np.unique([log.encounter.instance.name for log in logs_day])
        for instance_name in instances_day:
            logs_instance = logs_day.filter(encounter__instance__name=instance_name)
            ici = InstanceClearInteraction.update_or_create_from_logs(logs=logs_instance, instance_group=iclear_group)

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

    def get_week_clears(self):
        week_start = self.iclear_group.start_time - datetime.timedelta(
            days=self.iclear_group.start_time.weekday()
        )  # days are correct, but not hours and mins.
        week_start = week_start.replace(hour=8, minute=30, second=0, microsecond=0)  # Raid reset time.

        week_clears = InstanceClearGroup.objects.filter(type=self.iclear_group.type).filter(
            Q(start_time__gte=week_start) & Q(start_time__lte=self.iclear_group.start_time)
        )
        return week_clears

    def get_total_clear_duration(self):
        """Get the total duration for raids and fractals
        Duration is saved in the iclear_group.
        """

        # For raids and strikes we need to check multiple clears since they may not be done in one session.
        if self.iclear_group.type in ["raid", "strike"]:
            week_clears = self.get_week_clears()

            week_logs = DpsLog.objects.filter(
                id__in=[j.id for i in week_clears for j in i.dps_logs_all],
                encounter__use_for_icg_duration=True,
                encounter__instance__instance_group__name=self.iclear_group.type,
                use_in_leaderboard=True,
            ).order_by("start_time")
            df_logs_duration = pd.DataFrame(
                week_logs.values_list(
                    "encounter",
                    "encounter__nr",
                    "encounter__instance__nr",
                    "success",
                    "duration",
                    "start_time",
                    "start_time__day",
                ),
                columns=["encounter", "encounter_nr", "instance_nr", "success", "duration", "start_time", "start_day"],
            )

            df_logs_duration["enc_ins_str"] = df_logs_duration.apply(
                lambda x: f"{x.instance_nr}_{x.encounter_nr}", axis=1
            )

            # Drop duplicate successes. Shouldnt happen too much anyway...
            dupe_bool = df_logs_duration[df_logs_duration["success"]].duplicated("encounter")
            df_logs_duration.drop(dupe_bool[dupe_bool].index, inplace=True)

            # Count encounters that are used for leaderboard total with success
            leaderboard_success_count = sum(
                df_logs_duration.loc[df_logs_duration["success"], "enc_ins_str"].apply(
                    lambda x: x in self.iclear_group.duration_encounters
                )
            )
            leaderboard_required_success_count = len(self.iclear_group.duration_encounters.split("__"))

            if leaderboard_success_count == leaderboard_required_success_count:
                if self.iclear_group.success is False:
                    logger.info(f"Finished {self.iclear_group.type}s for this week!")

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
                logger.info("Finished all fractals!")
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

    def get_rank_emote_icg(self) -> str:
        """Look up the rank of the instance clear compared to previous logs.
        Returns the emotestr with information on the rank and how much slower
        it was compared to the fastest clear until that point in time.
        example:
        '<:r20_of45_slower1804_9s:1240399925502545930>'
        """
        icg = self.iclear_group
        icg_type = icg.type

        # This is a str of wings + bosses that is included when looking up rank.
        duration_encounters: str = icg.duration_encounters

        # Find all older icgs and sort them by duration
        group = list(
            InstanceClearGroup.objects.filter(
                success=True,
                duration_encounters=duration_encounters,
                type=icg_type,
            )
            .filter(start_time__lte=icg.start_time)
            .exclude(name__icontains="cm__")
            .order_by("duration")
        )

        # Create the rank emote str
        rank_str = get_rank_emote(
            indiv=icg,
            group_list=group,
            core_minimum=settings.CORE_MINIMUM[icg_type],
        )
        return rank_str

    def sync_discord_message_id(self):
        """Update the iclear_group discord message id to be the same if raids and strikes
        are sent to the same channel.
        """
        # FIXME errors when strikes are done first on a raid-day.
        if (ITYPE_GROUPS["raid"] == ITYPE_GROUPS["strike"]) and (self.iclear_group.type in ["raid", "strike"]):
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
                logger.debug(f"Updated discord_message_id for {self.iclear_group}")
                self.iclear_group.save()

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

            titles, descriptions = create_discord_message(icgi)
            icg_embeds = create_discord_embeds(titles, descriptions)
            embeds.update(icg_embeds)
        embeds_messages_list = list(embeds.values())

        # Create/update the message
        create_or_update_discord_message(
            group=self.iclear_group,
            webhook_url=settings.WEBHOOKS[self.iclear_group.type],
            embeds_messages_list=embeds_messages_list,
        )

        # Create/update message in the fast channel.
        if settings.WEBHOOKS_CURRENT_WEEK[self.iclear_group.type] is not None:
            create_or_update_discord_message_current_week(
                iclear_group=self.iclear_group,
                webhook_url=settings.WEBHOOKS_CURRENT_WEEK[self.iclear_group.type],
                embeds_messages_list=embeds_messages_list,
            )


# %%
if __name__ == "__main__":
    y, m, d = 2025, 9, 8
    itype_group = "raid"

    self = icgi = InstanceClearGroupInteraction.create_from_date(y=y, m=m, d=d, itype_group=itype_group)

    group = self.iclear_group
    webhook_url = settings.WEBHOOKS_CURRENT_WEEK[self.iclear_group.type]
