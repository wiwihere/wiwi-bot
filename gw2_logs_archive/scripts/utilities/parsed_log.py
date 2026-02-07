# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import logging
from functools import cached_property
from pathlib import Path
from typing import Optional

import numpy as np
from gw2_logs.models import (
    Encounter,
    Player,
)
from scripts.log_helpers import (
    BOSS_HEALTH_PERCENTAGES,
    BOSS_MAX_DURATION,
    get_duration_str,
)
from scripts.log_processing.ei_parser import EliteInsightsParser
from scripts.log_processing.log_uploader import DpsReportUploader

logger = logging.getLogger(__name__)


class _HealthData:
    """Search the time in seconds when a certain health percentage was reached.
    Return the remaining time on the clock.

    Parameters
    ----------
    health_data : list[list[float]]
        List of [time (ms), health percentage] pairs. This looks like this;
        [
        [0, 100],
        [3018, 99.99],
        [3918, 99.98],
        [4519, 99.97],
        ]
    encounter_name : str
        Options are; 'cerus'
    """

    def __init__(self, health_data: list[list[float]], encounter_name: str):
        health_data_np = np.array(health_data)
        self.times = health_data_np[:, 0]  # ms
        self.health = health_data_np[:, 1]  # %

        self.encounter_name = encounter_name

    @property
    def max_duration_seconds(self) -> int:
        return BOSS_MAX_DURATION[self.encounter_name]

    @classmethod
    def from_detailed_logs(cls, encounter_name: str, json_detailed: dict) -> Optional["_HealthData"]:
        """Create HealthData from detailed logs json."""
        health_data = json_detailed["targets"][0]["healthPercents"]

        return cls(health_data=health_data, encounter_name=encounter_name)

    def _get_time_from_healthpercentage(
        self,
        target_hp: float,
    ) -> float | None:
        if target_hp > self.health[0] or target_hp < self.health[-1]:
            return None

        idx = np.searchsorted(-self.health, -target_hp)

        return self.times[idx]

    def get_time_at_healthpercentage(self, target_hp: float) -> str:
        time_ms = self._get_time_from_healthpercentage(target_hp=target_hp)
        if time_ms is None:
            return " -- "
        else:
            time_s = time_ms / 1000
            time_s_int = time_s.astype("timedelta64[s]").astype(np.int32)

            if time_s_int <= 0:
                return " -- "
            return get_duration_str(self.max_duration_seconds - time_s_int)


class DetailedParsedLog:
    """Class to hold information on a parsed log, either from EI parser or dps.report"""

    def __init__(self, data: dict):
        self.data = data

    @classmethod
    def from_ei_parsed_path(cls, parsed_path: Path) -> "DetailedParsedLog":
        """Create DetailedParsedLog from parsed path."""
        return EliteInsightsParser.load_parsed_json(parsed_path=parsed_path)

    @classmethod
    def from_dps_report_url(cls, url: str) -> "DetailedParsedLog":
        """Create DetailedParsedLog from dps.report url by requesting detailed info from the API."""
        data = DpsReportUploader().request_detailed_info(url=url)
        return cls(data=data)

    @cached_property
    def name(self) -> str:
        return self.data["name"].replace("CM", "").replace("LCM", "").strip()

    def get_final_health_percentage(self) -> float:
        """Get final health percentage from detailed logs."""
        return round(100 - self.data["targets"][0]["healthPercentBurned"], 2)

    def get_phasetime_str(self) -> str:
        """For progression logging when a milestone (from BOSS_HEALTH_PERCENTAGES) has been reached
        is calculated from detailed logs. The remaining time until enrage is shown at the specified health percentages.

        For example, for Cerus the times at 80%, 50% and 10% health are calculated.
        This results in a string like:
        '8:12 | 5:34 | 1:07'
        """
        if self.name not in BOSS_HEALTH_PERCENTAGES.keys():
            return None

        logger.info(
            f"Calculating phase times at health percentages {BOSS_HEALTH_PERCENTAGES[self.name]} for {self.name}"
        )
        hd = _HealthData.from_detailed_logs(encounter_name=self.name, json_detailed=self.data)

        phasetime_lst = [hd.get_time_at_healthpercentage(target_hp=hp) for hp in BOSS_HEALTH_PERCENTAGES[self.name]]
        return " | ".join(phasetime_lst)

    def get_players(self) -> list[str]:
        return [player["account"] for player in self.data["players"]]

    def get_encounter(self) -> Optional[Encounter]:
        try:
            encounter = Encounter.objects.get(
                ei_encounter_id=self.data["eiEncounterID"]
            )  # FIXME on new encounters this is 0 somehow.
            if self.data["eiEncounterID"] == 0:
                logger.warning(f"{self.name} has eiEncounterID 0, which now returned {encounter}")
        except Encounter.DoesNotExist:
            logger.error(f"{self.name} with id {self.data['eiEncounterID']} doesnt exist")
            return None
        return encounter

    def get_starttime(self) -> datetime.datetime:
        return datetime.datetime.strptime(self.data["timeStartStd"], "%Y-%m-%d %H:%M:%S %z").astimezone(
            datetime.timezone.utc
        )

    def get_duration(self) -> datetime.timedelta:
        return datetime.timedelta(seconds=self.data["durationMS"] / 1000)

    def to_dpslog_defaults(self, log_path: Path) -> dict:
        """Build defaults dict for DpsLog from an Elite Insights parsed log."""
        players = [player["account"] for player in self.data["players"]]

        defaults = {
            "duration": self.get_duration(),
            "player_count": len(players),
            # encounter resolution belongs to the service; factory doesn't touch DB for Encounter
            "boss_name": self.data.get("fightName"),
            "cm": self.data.get("isCM"),
            "lcm": self.data.get("isLegendaryCM"),
            "emboldened": "b68087" in self.data.get("buffMap", {}),
            "success": self.data.get("success"),
            "final_health_percentage": self.get_final_health_percentage(),
            "gw2_build": self.data.get("gW2Build"),
            "players": players,
            "core_player_count": len(Player.objects.filter(gw2_id__in=players, role="core")),
            "friend_player_count": len(Player.objects.filter(gw2_id__in=players, role="friend")),
            "local_path": log_path,
            "phasetime_str": self.get_phasetime_str(),
        }

        return defaults
