# %%

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import logging
import shutil
from ast import parse
from dataclasses import dataclass
from functools import cached_property
from os import times
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from django.conf import settings
from django.db.models import Q
from gw2_logs.models import (
    DpsLog,
    Encounter,
    Player,
)
from scripts.log_helpers import (
    get_duration_str,
    get_rank_emote,
)
from scripts.log_processing.ei_parser import EliteInsightsParser

logger = logging.getLogger(__name__)

BOSS_MAX_DURATION = {"Temple of Febe": 10 * 60}  # s
BOSS_HEALTH_PERCENTAGES = {
    "Temple of Febe": [80, 50, 10],
}


def move_failed_upload(log_path: Path) -> None:
    """Some logs are just broken. Lets remove them from the equation"""  # noqa
    out_path = settings.DPS_LOGS_DIR.parent.joinpath("failed_logs", *log_path.parts[-3:])
    out_path.parent.mkdir(exist_ok=True, parents=True)
    logger.warning(f"Moved failing log from {log_path} to")
    logger.warning(out_path)
    shutil.move(src=log_path, dst=out_path)


class HealthData:
    """Get the time (in seconds) when a certain health percentage was reached.

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
    def from_detailed_logs(cls, encounter_name: str, json_detailed: dict) -> Optional["HealthData"]:
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

        if self.health[idx] == target_hp:
            return self.times[idx]

        t0, t1 = self.times[idx - 1], self.times[idx]
        hp0, hp1 = self.health[idx - 1], self.health[idx]

        # Linear interpolation
        return t0 + (t1 - t0) * ((hp0 - target_hp) / (hp0 - hp1))

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


class ParsedLog:
    """Class to hold information on a parsed log, either from EI parser or dps.report"""

    def __init__(self, json_detailed: Optional[dict]):
        self.json_detailed = json_detailed

    @cached_property
    def name(self) -> str:
        return self.json_detailed["name"].replace("CM", "").replace("LCM", "").strip()

    def get_final_health_percentage(self) -> float:
        """Get final health percentage from detailed logs."""
        return round(100 - self.json_detailed["targets"][0]["healthPercentBurned"], 2)

    def get_phasetime_str(self) -> str:
        """For Cerus CM the time breakbar phases are reached is calculated from detailed logs."""
        if self.name not in BOSS_HEALTH_PERCENTAGES.keys():
            return None

        logger.info(
            f"Calculating phase times at health percentages {BOSS_HEALTH_PERCENTAGES[self.name]} for {self.name}"
        )
        hd = HealthData.from_detailed_logs(encounter_name=self.name, json_detailed=self.json_detailed)

        phasetime_lst = [hd.get_time_at_healthpercentage(target_hp=hp) for hp in BOSS_HEALTH_PERCENTAGES[self.name]]
        return " | ".join(phasetime_lst)

    def get_players(self) -> list[str]:
        return [player["account"] for player in self.json_detailed["players"]]

    def get_encounter(self) -> Optional[Encounter]:
        try:
            encounter = Encounter.objects.get(
                ei_encounter_id=self.json_detailed["eiEncounterID"]
            )  # FIXME on new encounters this is 0 somehow.
            if self.json_detailed["eiEncounterID"] == 0:
                logger.warning(f"{self.name} has eiEncounterID 0, which now returned {encounter}")
        except Encounter.DoesNotExist:
            logger.error(f"{self.name} with id {self.json_detailed['eiEncounterID']} doesnt exist")
            return None
        return encounter

    def get_starttime(self) -> datetime.datetime:
        return datetime.datetime.strptime(self.json_detailed["timeStartStd"], "%Y-%m-%d %H:%M:%S %z").astimezone(
            datetime.timezone.utc
        )

    def get_duration(self) -> datetime.timedelta:
        return datetime.timedelta(seconds=self.json_detailed["durationMS"] / 1000)


def create_from_detailed_logs(log_path: Path, json_detailed: dict) -> Optional[DpsLog]:
    """
    Create or update a DpsLog instance from detailed log data.

    Parameters
    ----------
    log_path : Path
        Path to the log file.
    json_detailed : dict
        Detailed JSON data from the log (EliteInsightsParser.load_json_gz(parsed_path=parsed_path))

    Returns
    -------
    Optional[DpsLog]
        The created or updated DpsLog instance, or None if creation failed.
    """
    logger.info(f"Processing detailed log: {log_path}")

    parsed_log = ParsedLog(json_detailed=json_detailed)

    encounter = parsed_log.get_encounter()
    if encounter is None:
        logger.error(f"Encounter for log {log_path} could not be found. Skipping log.")
        move_failed_upload(log_path)
        return False

    final_health_percentage = parsed_log.get_final_health_percentage()
    if final_health_percentage == 100.0 and encounter.name == "Eye of Fate":
        move_failed_upload(log_path)
        return False

    start_time = parsed_log.get_starttime()

    # Check if log was uploaded before by someone else. Start time can be couple seconds off,
    # so we need to filter a timerange.
    dpslog = DpsLog.objects.filter(
        start_time__range=(
            start_time - datetime.timedelta(seconds=5),
            start_time + datetime.timedelta(seconds=5),
        ),
        encounter__name=encounter.name,
    )

    if len(dpslog) > 1:
        # Problem when multiple people upload the same log at exactly the same time
        # unsure if this can/will occur.
        logger.error("Multiple dpslogs found for %s, check the admin.", encounter.name)

    if len(dpslog) >= 1:
        dpslog = dpslog.first()
    else:
        players = [player["account"] for player in json_detailed["players"]]
        dpslog, created = DpsLog.objects.update_or_create(
            defaults={
                "duration": parsed_log.get_duration(),
                "player_count": len(players),
                "encounter": encounter,
                "boss_name": json_detailed["fightName"],
                "cm": json_detailed["isCM"],
                "lcm": json_detailed["isLegendaryCM"],
                "emboldened": "b68087" in json_detailed["buffMap"],
                "success": json_detailed["success"],
                "final_health_percentage": final_health_percentage,
                "gw2_build": json_detailed["gW2Build"],
                "players": players,
                "core_player_count": len(Player.objects.filter(gw2_id__in=players, role="core")),
                "friend_player_count": len(Player.objects.filter(gw2_id__in=players, role="friend")),
                "local_path": log_path,
                "phasetime_str": parsed_log.get_phasetime_str(),
            },
            start_time=start_time,
        )
    return dpslog


@dataclass
class DpsLogInteraction:
    """Create a dpslog from detailed logs in EI parser or the
    shorter json from dps.report.
    """

    dpslog: DpsLog = None

    @classmethod
    def from_local_ei_parser(cls, log_path: Path, parsed_path: Path) -> Optional["DpsLogInteraction"]:
        try:
            dpslog = DpsLog.objects.get(local_path=log_path)
        except DpsLog.DoesNotExist:
            dpslog = None

        if dpslog is None:
            if parsed_path is None:
                logger.warning(f"{log_path} was not parsed")
                return False

            json_detailed = EliteInsightsParser.load_json_gz(parsed_path=parsed_path)
            dpslog = create_from_detailed_logs(cls, log_path=log_path, json_detailed=json_detailed)

            if dpslog is False:
                return False

        return cls(dpslog=dpslog)

    @staticmethod
    def update_or_create_from_dps_report_metadata(
        self,
        metadata: dict,
        encounter: Optional[Encounter],
    ) -> DpsLog:
        """Create or update a dpslog from dps.report metadata json."""
        # Arcdps error 'File had invalid agents. Please update arcdps' would return some
        # empty jsons. This makes sure the log is still processed
        if metadata["players"] != []:
            players = [i["display_name"] for i in metadata["players"].values()]
        else:
            players = []

        dpslog, created = DpsLog.objects.update_or_create(
            defaults={
                "encounter": encounter,
                "success": metadata["encounter"]["success"],
                "duration": datetime.timedelta(seconds=metadata["encounter"]["duration"]),
                "url": metadata["permalink"],
                "player_count": metadata["encounter"]["numberOfPlayers"],
                "boss_name": metadata["encounter"]["boss"],
                "cm": metadata["encounter"]["isCm"],
                "gw2_build": metadata["encounter"]["gw2Build"],
                "players": players,
                "core_player_count": len(Player.objects.filter(gw2_id__in=players, role="core")),
                "friend_player_count": len(Player.objects.filter(gw2_id__in=players, role="friend")),
                "report_id": metadata["id"],
                "local_path": self.log_source,
                "json_dump": metadata,
            },
            # metadata["encounterTime"] format is 1702926477
            start_time=datetime.datetime.fromtimestamp(metadata["encounterTime"], tz=datetime.timezone.utc),
        )
        return dpslog

    def get_rank_emote_log(self) -> str:
        """Look up the rank of the log compared to previous logs.
        Returns the emotestr with information on the rank and how much slower
        it was compared to the fastest clear until that point in time.
        example:
        '<:r20_of45_slower1804_9s:1240399925502545930>'
        """
        encounter_success_all = None
        if self.dpslog.success:
            encounter_success_all = list(
                self.dpslog.encounter.dps_logs.filter(success=True, cm=self.dpslog.cm, emboldened=False)
                .filter(
                    Q(start_time__gte=self.dpslog.start_time - datetime.timedelta(days=9999))
                    & Q(start_time__lte=self.dpslog.start_time)
                )
                .order_by("duration")
            )
        rank_str = get_rank_emote(
            indiv=self.dpslog,
            group_list=encounter_success_all,
            core_minimum=settings.CORE_MINIMUM[self.dpslog.encounter.instance.instance_group.name],
            custom_emoji_name=False,
        )
        return rank_str

    def build_health_str(self) -> str:
        """Build health string with leading zeros for discord message. Used in Cerus CM."""
        health_str = ".".join(
            [str(int(i)).zfill(2) for i in str(round(self.dpslog.final_health_percentage, 2)).split(".")]
        )  # makes 02.20%
        if health_str == "100.00":
            health_str = "100.0"
        return health_str
