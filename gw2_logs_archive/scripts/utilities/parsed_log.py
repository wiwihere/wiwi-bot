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
from bot_settings import settings
from gw2_logs.models import (
    Encounter,
)
from scripts.model_interactions.encounter import EncounterInteraction

logger = logging.getLogger(__name__)


class _HealthData:
    """Search the time in seconds from start when a certain health percentage was reached.

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
    """

    def __init__(self, health_data: list[list[float]]):
        health_data_np = np.array(health_data)

        if health_data:
            health_data_np
        self.times = health_data_np[:, 0]  # ms
        self.health = health_data_np[:, 1]  # %

    @classmethod
    def from_detailed_logs(cls, json_detailed: dict) -> "_HealthData":
        """Create HealthData from detailed logs json."""
        health_data = json_detailed["targets"][0]["healthPercents"]

        return cls(health_data=health_data)

    def get_time_at_healthpercentage(self, target_hp: float) -> Optional[float]:
        """Get the time in seconds when the boss reached a certain health percentage.
        If the target_hp is above the starting health or below the final health, return None.
        """
        if target_hp > self.health[0] or target_hp < self.health[-1]:
            return None

        idx = np.searchsorted(-self.health, -target_hp)

        time_ms = self.times[idx]
        time_s = round(float(time_ms) / 1000, 2)
        return time_s


class DetailedParsedLog:
    """Class to hold information on a parsed log, either from EI parser or dps.report

    These functions return this object;
        EliteInsightsParser().load_parsed_json
        DpsReportUploader().request_detailed_info
    """

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
            "health_timers": self.get_health_timers(),
        }

        return defaults

    def get_final_health_percentage(self) -> float:
        """Get final health percentage from detailed logs."""
        return round(100 - self.data["targets"][0]["healthPercentBurned"], 2)

    def get_health_timers(self) -> dict[int, Optional[float]]:
        """For progression logging when a milestone (from log_helpers.BOSS_HEALTH_PERCENTAGES) has been reached
        we send this in the discord message. The time at which the boss reached certain health percentages (5% intervals) is
        calculated here.

        This results in a dict like:
            {
                100: np.float64(0.0),
                95: np.float64(66.84),
                90: np.float64(70.14),
                ...
                5: np.float64(266.44),
            }
        """
        try:
            hd = _HealthData.from_detailed_logs(json_detailed=self.data)

            health_time_dict = {}
            for health_percentage in range(100, 0, -5):
                health_time_dict[health_percentage] = hd.get_time_at_healthpercentage(target_hp=health_percentage)
            return health_time_dict
        except:
            logger.error(f"Failed to get health timers for log {self.log_path}")
            return None

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


# %%
if __name__ == "__main__":
    # Local testing
    import gzip
    import json

    from django.conf import settings

    parsed_path = settings.PROJECT_DIR.joinpath(r"data\parsed_logs\20260205\20260205-215553_xera_273s_kill.json.gz")
    with gzip.open(parsed_path, "r") as fin:
        json_bytes = fin.read()

    json_str = json_bytes.decode("utf-8")
    data = json.loads(json_str)

    self = DetailedParsedLog(data=data)
    self.get_health_timers()

# %%
