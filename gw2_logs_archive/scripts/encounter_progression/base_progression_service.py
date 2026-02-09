# %% gw2_logs_archive\scripts\encounter_progression\base_progression_service.py
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import logging
from itertools import chain
from typing import Literal, Tuple

import numpy as np
import pandas as pd
from django.db.models import Q
from gw2_logs.models import (
    DpsLog,
    Encounter,
    InstanceClear,
    InstanceClearGroup,
)
from scripts.log_helpers import (
    BOSS_HEALTH_PERCENTAGES,
    RANK_EMOTES_CUPS_PROGRESSION,
    create_rank_emote_dict_percentiles,
    get_duration_str,
)

# For progression always use percentiles.
RANK_EMOTES_PROGRESSION, RANK_BINS_PERCENTILE_PROGRESSION = create_rank_emote_dict_percentiles(
    custom_emoji_name=True, invalid=False
)

logger = logging.getLogger(__name__)


class ProgressionService:
    def __init__(
        self,
        clear_group_base_name: str,
        clear_name: str,
        encounter: Encounter,
        embed_colour_group: str,
        webhook_thread_id: str,
        webhook_url: str,
    ) -> None:
        self.clear_group_base_name = clear_group_base_name
        self.clear_name = clear_name
        self.encounter = encounter
        self.colour_group = embed_colour_group
        self.webhook_thread_id = webhook_thread_id
        self.webhook_url = webhook_url

        logger.info(f"Starting progression run for {self.encounter.name}: {self.clear_name}")

        self.iclear_group = self.get_iclear_group()
        self.iclear = self.get_iclear()

    def get_iclear_group(self) -> InstanceClearGroup:
        """Load or create the InstanceClearGroup for this progression day."""
        iclear_group, created = InstanceClearGroup.objects.get_or_create(name=self.clear_name, type="strike")
        if created:
            logger.info(f"Created InstanceClearGroup {iclear_group.name}")
        return iclear_group

    def get_iclear(self) -> InstanceClear:
        """Load or create the InstanceClear for this progression day."""
        iclear, created = InstanceClear.objects.get_or_create(
            defaults={
                "instance": self.encounter.instance,
                "instance_clear_group": self.iclear_group,
            },
            name=self.clear_name,
        )
        if created:
            logger.info(f"Created InstanceClear {iclear.name}")

        return iclear

    def get_message_author(self) -> str:
        """Create author name for discord message.
        The author is displayed at the top of the message.
        """
        # The progression_days_count is the total days up to this point for this progression
        progression_days_count = len(
            InstanceClearGroup.objects.filter(
                Q(name__startswith=f"{self.clear_group_base_name}__") & Q(start_time__lte=self.iclear_group.start_time)
            )
        )
        return f"Day #{progression_days_count:02d}"

    def get_all_logs(self) -> list[DpsLog]:
        """Get the total log count for this progression."""
        icg_all = InstanceClearGroup.objects.filter(
            name__startswith=f"{self.clear_group_base_name}__",
            type="strike",
            start_time__lte=self.iclear_group.start_time,
        )
        dps_logs = list(chain.from_iterable(icg.dps_logs_all for icg in icg_all))
        return sorted(dps_logs, key=lambda d: d.final_health_percentage)

    def get_message_footer(self) -> str:
        icg_all = InstanceClearGroup.objects.filter(
            name__startswith=f"{self.clear_group_base_name}__",
            type="strike",
            start_time__lte=self.iclear_group.start_time,
        )
        logs_count = len(self.get_all_logs())

        total_seconds = sum(
            int(icg.instance_clears.first().duration.total_seconds()) for icg in icg_all if icg.instance_clears.first()
        )
        time_str = str(pd.to_timedelta(total_seconds, unit="s"))

        return f"Total logs: {logs_count}\nTotal duration: {time_str}\n"

    def update_instance_clear(self) -> Tuple[InstanceClear, InstanceClearGroup]:
        """Update the iclear_group and iclear"""
        dps_logs_all = self.iclear_group.dps_logs_all
        if dps_logs_all:
            start_time = min([i.start_time for i in dps_logs_all])
            # Set iclear_group start time
            if self.iclear_group.start_time != start_time:
                logger.info(
                    f"Updating start time for {self.iclear_group.name} from {self.iclear_group.start_time} to {start_time}"
                )
                self.iclear_group.start_time = start_time
                self.iclear_group.save()

            # Set iclear start time
            if self.iclear.start_time != start_time:
                logger.info(
                    f"Updating start time for {self.iclear.name} from {self.iclear.start_time} to {start_time}"
                )
                self.iclear.start_time = start_time
                self.iclear.save()

            # Set iclear duration
            last_log = dps_logs_all[-1]
            calculated_duration = last_log.start_time + last_log.duration - self.iclear.start_time
            if self.iclear.duration != calculated_duration:
                logger.info(
                    f"Updating duration for {self.iclear.name} from {self.iclear.duration} to {calculated_duration}"
                )
                self.iclear.duration = calculated_duration
                self.iclear.save()

    def get_rank_emote_for_log(self, dpslog: DpsLog) -> int:
        """Build rank_emote based on the final health left.
        e.g. -> '<:4_masterwork:1218309092477767810>'
        """

        percentile_rank = 100 - dpslog.final_health_percentage
        rank_binned = np.searchsorted(RANK_BINS_PERCENTILE_PROGRESSION, percentile_rank, side="left")

        all_logs = self.get_all_logs()
        rank = all_logs.index(dpslog) + 1

        rank_emote = RANK_EMOTES_PROGRESSION[rank_binned].format(rank, len(all_logs))
        return rank_emote

    def create_logs_rank_health_df(self, minimal_delay_seconds: int) -> pd.DataFrame:
        """Create dataframe with health and rank information for progression logs.
        This dataframe is used to build the discord message line by line

        Parameters
        ----------
        minimal_delay_seconds : int
            Minimal delay in seconds between logs to show the delay in discord message.
        """
        progression_logs = self.iclear_group.dps_logs_all

        logs_rank_health_df = pd.DataFrame(
            [(x.id, x.final_health_percentage, x.cm, x.lcm) for x in progression_logs],
            columns=["id", "health", "cm", "lcm"],
        )
        logs_rank_health_df["log"] = progression_logs

        # Add log counter
        logs_rank_health_df.reset_index(inplace=True)
        logs_rank_health_df["log_idx"] = logs_rank_health_df["index"]
        logs_rank_health_df.rename(columns={"index": "log_nr"}, inplace=True)
        logs_rank_health_df["log_nr"] = logs_rank_health_df["log_nr"].apply(lambda x: f"`{str(x + 1).zfill(2)}`")

        # Add rank based on health
        logs_rank_health_df.sort_values("health", inplace=True)
        logs_rank_health_df.reset_index(inplace=True, drop=True)
        logs_rank_health_df.reset_index(inplace=True, drop=False)
        logs_rank_health_df.rename(columns={"index": "rank"}, inplace=True)
        logs_rank_health_df["rank"] += 1

        # Add rank cups for the best 3 logs
        emote_cups = pd.Series(RANK_EMOTES_CUPS_PROGRESSION.values(), name="rank")
        logs_rank_health_df["cups"] = ""
        logs_rank_health_df.loc[:2, "cups"] = emote_cups[: len(logs_rank_health_df)]
        logs_rank_health_df.loc[:2, "cups"] = logs_rank_health_df.loc[:2, "cups"].apply(
            lambda x: x.format(len(logs_rank_health_df))
        )

        # Revert to chronological order
        logs_rank_health_df.sort_values("log_idx", inplace=True)
        logs_rank_health_df.reset_index(inplace=True, drop=True)

        # Add time_diff between logs. delay_str is only shown if time_diff > minimal_delay_seconds
        start_time = logs_rank_health_df["log"].apply(lambda x: x.start_time)
        end_time = logs_rank_health_df["log"].apply(lambda x: x.start_time + x.duration)
        logs_rank_health_df["time_diff"] = start_time - end_time.shift(1)
        logs_rank_health_df["delay_str"] = logs_rank_health_df["time_diff"].apply(
            lambda x: f"_+{get_duration_str(x.seconds)}_" if x.seconds > minimal_delay_seconds else ""
        )

        return logs_rank_health_df

    def get_difficulty(self, logs_rank_health_df: pd.DataFrame) -> Literal["normal", "cm", "lcm"]:
        difficulty = "cm"
        if not logs_rank_health_df.empty:
            if logs_rank_health_df["lcm"].mode().iloc[0]:
                difficulty = "lcm"
            elif logs_rank_health_df["cm"].mode().iloc[0]:
                difficulty = "cm"
            else:
                difficulty = "normal"
        return difficulty

    def get_boss_title(self, difficulty: Literal["normal", "cm", "lcm"]) -> str:
        if difficulty == "normal":
            boss_title = f"{self.encounter.name}"
        elif difficulty == "cm":
            boss_title = f"{self.encounter.name} CM"
        elif difficulty == "lcm":
            boss_title = f"{self.encounter.name} LegendaryCM"
        return boss_title

    def get_table_header(self) -> str:
        percentages = BOSS_HEALTH_PERCENTAGES[self.encounter.name]
        percentages_str = "|  ".join([f"{hp}% " for hp in percentages])
        return f"`##`{RANK_EMOTES_PROGRESSION[7].format('lets_goo', 'killkillkill')}**★** ` health |  {percentages_str}`+_delay_⠀⠀\n\n"
