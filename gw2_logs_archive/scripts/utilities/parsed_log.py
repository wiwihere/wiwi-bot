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
)
from scripts.log_helpers import (
    BOSS_HEALTH_PERCENTAGES,
    BOSS_MAX_DURATION,
    get_duration_str,
)
from scripts.log_processing.ei_parser import EliteInsightsParser
from scripts.log_processing.log_uploader import DpsReportUploader
from scripts.model_interactions.encounter import EncounterInteraction

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

    def __init__(self, data: dict, log_path: Optional[Path] = None):
        self.data = data
        self.log_path = log_path

    def to_dpslog_defaults(self, log_path: Optional[Path] = None) -> dict:
        """Return a pure dict of dpslog defaults derived from the detailed parsed log.

        This function must not perform any ORM calls. It should only return
        primitive types and lists so it can be used outside a Django context.
        """
        players = self.get_players()

        defaults = {
            "success": self.data["success"],
            "duration": self.get_duration(),
            "player_count": len(players),
            "boss_name": self.data["fightName"],
            "cm": self.data["isCM"],
            "lcm": self.data["isLegendaryCM"],
            "emboldened": "b68087" in self.data["buffMap"],
            "final_health_percentage": self.get_final_health_percentage(),
            "gw2_build": self.data["gW2Build"],
            "players": players,
            "local_path": log_path,
            "phasetime_str": self.get_phasetime_str(),
        }

        return defaults

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

    @cached_property
    def encounter(self) -> Optional[Encounter]:
        return EncounterInteraction.find_by_detailed_logs(detailed_metadata=self.data)

    def get_starttime(self) -> datetime.datetime:
        return datetime.datetime.strptime(self.data["timeStartStd"], "%Y-%m-%d %H:%M:%S %z").astimezone(
            datetime.timezone.utc
        )

    def get_duration(self) -> datetime.timedelta:
        return datetime.timedelta(seconds=self.data["durationMS"] / 1000)

    def validate(self) -> bool:
        """Check if the parsed log contains valid data."""

        if self.encounter is None:
            logger.error(f"Encounter for log {self.log_path} could not be found. Skipping log.")
            raise ValueError(f"Encounter for log {self.log_path} could not be found.")
            # move_failed_log(log_path, reason="failed")
            # return None

        final_health_percentage = self.get_final_health_percentage()
        if final_health_percentage == 100.0 and self.encounter.name == "Eye of Fate":
            return False, "failed"
        return True, None
