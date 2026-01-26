# %%

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import logging
import shutil
from dataclasses import dataclass
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


def move_failed_upload(log_path):
    """Some logs are just broken. Lets remove them from the equation"""  # noqa
    out_path = settings.DPS_LOGS_DIR.parent.joinpath("failed_logs", Path(log_path).name)
    out_path.parent.mkdir(exist_ok=True)
    logger.warning(f"Moved failing log from {log_path} to")
    logger.warning(out_path)
    shutil.move(src=log_path, dst=out_path)


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

            json_detailed = EliteInsightsParser.load_json_gz(js_path=parsed_path)
            dpslog = cls.from_detailed_logs(cls, log_path=log_path, json_detailed=json_detailed)

            if dpslog is False:
                return False

        return cls(dpslog=dpslog)

    @staticmethod
    def from_detailed_logs(cls, log_path: Path, json_detailed: dict) -> Optional[DpsLog]:
        logger.info(f"Processing detailed log: {log_path}")
        r2 = json_detailed

        players = [player["account"] for player in r2["players"]]
        final_health_percentage = round(100 - r2["targets"][0]["healthPercentBurned"], 2)

        try:
            encounter = Encounter.objects.get(ei_encounter_id=r2["eiEncounterID"])
        except Encounter.DoesNotExist:
            logger.error(f"{r2['fightName']} with id {r2['eiEncounterID']} doesnt exist")
            move_failed_upload(log_path)
            return False

        if final_health_percentage == 100.0 and encounter.name == "Eye of Fate":
            move_failed_upload(log_path)
            return False

        if encounter.name == "Temple of Febe":
            phasetime_str = cls._get_phasetime_str(json_detailed=json_detailed)
        else:
            phasetime_str = None

        start_time = datetime.datetime.strptime(r2["timeStartStd"], "%Y-%m-%d %H:%M:%S %z").astimezone(
            datetime.timezone.utc
        )

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
            dpslog, created = DpsLog.objects.update_or_create(
                defaults={
                    # "url": r["permalink"],
                    "duration": datetime.timedelta(seconds=r2["durationMS"] / 1000),
                    # "end_time"=,
                    "player_count": len(players),
                    "encounter": encounter,
                    "boss_name": r2["fightName"],
                    "cm": r2["isCM"],
                    "lcm": r2["isLegendaryCM"],
                    "emboldened": "b68087" in r2["buffMap"],
                    "success": r2["success"],
                    "final_health_percentage": final_health_percentage,
                    "gw2_build": r2["gW2Build"],
                    "players": players,
                    "core_player_count": len(Player.objects.filter(gw2_id__in=players, role="core")),
                    "friend_player_count": len(Player.objects.filter(gw2_id__in=players, role="friend")),
                    # "report_id": r["id"],
                    "local_path": log_path,
                    # "json_dump": r,
                    "phasetime_str": phasetime_str,
                },
                start_time=datetime.datetime.strptime(r2["timeStartStd"], "%Y-%m-%d %H:%M:%S %z").astimezone(
                    datetime.timezone.utc
                ),
            )
        return dpslog

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

    @staticmethod
    def _get_phasetime_str(json_detailed: dict) -> str:
        """For Cerus LCM the time breakbar phases are reached is calculated from detailed logs."""
        # Get information on phase timings
        data = json_detailed["phases"]

        filtered_data = [d for d in data if "Cerus Breakbar" in d["name"]]
        df = pd.DataFrame(filtered_data)
        if not df.empty:
            df["time"] = df["end"].apply(lambda x: datetime.timedelta(minutes=10) - datetime.timedelta(milliseconds=x))

            phasetime_lst = [
                get_duration_str(i.astype("timedelta64[s]").astype(np.int32)) for i in df["time"].to_numpy()
            ]
        else:
            phasetime_lst = []

        while len(phasetime_lst) < 3:
            phasetime_lst.append(" -- ")

        phasetime_str = " | ".join(phasetime_lst)

        return phasetime_str

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
