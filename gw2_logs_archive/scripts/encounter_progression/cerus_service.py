# %% gw2_logs_archive\scripts\encounter_progression\cerus_service.py
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import logging
from typing import Literal

import numpy as np
import pandas as pd
from gw2_logs.models import (
    DpsLog,
    Encounter,
)
from scripts.encounter_progression.base_progression_service import ProgressionService
from scripts.log_helpers import (
    RANK_EMOTES_CUPS_PROGRESSION,
    create_rank_emote_dict_percentiles,
    get_duration_str,
    today_y_m_d,
    zfill_y_m_d,
)

logger = logging.getLogger(__name__)

# For progression always use percentiles.
RANK_EMOTES_PROGRESSION, RANK_BINS_PERCENTILE_PROGRESSION = create_rank_emote_dict_percentiles(
    custom_emoji_name=False, invalid=False
)

# %%


class CerusProgressionService(ProgressionService):
    def __init__(
        self,
        clear_group_base_name: str,
        y: int,
        m: int,
        d: int,
    ):
        self.clear_group_base_name = clear_group_base_name
        self.clear_name = f"{self.clear_group_base_name}__{zfill_y_m_d(y, m, d)}"  # e.g. cerus_cm__20240406
        self.encounter = Encounter.objects.get(name="Temple of Febe")

        super().__init__(
            clear_group_base_name=self.clear_group_base_name,
            clear_name=self.clear_name,
            encounter=self.encounter,
        )

    @staticmethod
    def get_rank_emote_for_log(dpslog: DpsLog) -> int:
        """Build rank_emote based on the final health left.
        e.g. -> '<:4_masterwork:1218309092477767810>'
        """
        percentile_rank = 100 - dpslog.final_health_percentage
        rank_binned = np.searchsorted(RANK_BINS_PERCENTILE_PROGRESSION, percentile_rank, side="left")
        rank_emote = RANK_EMOTES_PROGRESSION[rank_binned].format(int(percentile_rank))
        return rank_emote

    def create_health_df(self, minimal_delay_seconds: int) -> pd.DataFrame:
        """Create dataframe with health and rank information for cm logs.
        This dataframe is used to build the discord message line by line

        Parameters
        ----------
        cm_logs : QuerySet[DpsLog]
            Queryset of cm DpsLogs
        minimal_timediff_seconds : int
            Minimal time difference in seconds between logs to show delay in discord message.
        """
        cm_logs = self.iclear_group.dps_logs_all

        health_df = pd.DataFrame(
            [(x.id, x.final_health_percentage, x.lcm) for x in cm_logs], columns=["id", "health", "lcm"]
        )
        health_df["log"] = cm_logs

        # Add log counter
        health_df.reset_index(inplace=True)
        health_df["log_idx"] = health_df["index"]
        health_df.rename(columns={"index": "log_nr"}, inplace=True)
        health_df["log_nr"] = health_df["log_nr"].apply(lambda x: f"`{str(x + 1).zfill(2)}`")

        # Add rank based on health
        health_df.sort_values("health", inplace=True)
        health_df.reset_index(inplace=True, drop=True)
        health_df.reset_index(inplace=True, drop=False)
        health_df.rename(columns={"index": "rank"}, inplace=True)
        health_df["rank"] += 1

        # Add rank cups for the best 3 logs
        emote_cups = pd.Series(RANK_EMOTES_CUPS_PROGRESSION.values(), name="rank")
        health_df["cups"] = ""
        health_df.loc[:2, "cups"] = emote_cups[: len(health_df)]
        health_df.loc[:2, "cups"] = health_df.loc[:2, "cups"].apply(lambda x: x.format(len(health_df)))

        # Revert to chronological order
        health_df.sort_values("log_idx", inplace=True)
        health_df.reset_index(inplace=True, drop=True)

        # Add time_diff between logs. delay_str is only shown if time_diff > minimal_delay_seconds
        start_time = health_df["log"].apply(lambda x: x.start_time)
        end_time = health_df["log"].apply(lambda x: x.start_time + x.duration)
        health_df["time_diff"] = start_time - end_time.shift(1)
        health_df["delay_str"] = health_df["time_diff"].apply(
            lambda x: f"_+{get_duration_str(x.seconds)}_" if x.seconds > minimal_delay_seconds else ""
        )

        return health_df

    def get_difficulty(self, health_df: pd.DataFrame) -> Literal["cm", "lcm"]:
        difficulty = "cm"
        if len(health_df) > 0:
            if health_df["lcm"].mode().iloc[0]:
                difficulty = "lcm"
        return difficulty

    def get_boss_title(self, difficulty: Literal["cm", "lcm"]) -> str:
        if difficulty == "cm":
            boss_title = f"{self.encounter.name} CM"
        elif difficulty == "lcm":
            boss_title = f"{self.encounter.name} Legendary CM"
        return boss_title

    def get_table_header(self) -> str:
        return f"`##`{RANK_EMOTES_PROGRESSION[7]}**★** ` health |  80% |  50% |  10% `+_delay_⠀⠀\n\n"


if __name__ == "__main__":
    y, m, d = today_y_m_d()
    y, m, d = 2024, 3, 16
    cps = CerusProgressionService(clear_group_base_name="cerus_cm", y=y, m=m, d=d)
