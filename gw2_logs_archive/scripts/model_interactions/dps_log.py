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

from django.conf import settings
from django.db.models import Q
from gw2_logs.models import (
    DpsLog,
    Encounter,
    Player,
)
from scripts.log_helpers import (
    get_rank_emote,
)
from scripts.utilities.parsed_log import ParsedLog

logger = logging.getLogger(__name__)


def move_failed_upload(log_path: Path) -> None:
    """Some logs are just broken. Lets remove them from the equation"""  # noqa
    out_path = settings.DPS_LOGS_DIR.parent.joinpath("failed_logs", *log_path.parts[-3:])
    out_path.parent.mkdir(exist_ok=True, parents=True)
    logger.warning(f"Moved failing log from {log_path} to")
    logger.warning(out_path)
    shutil.move(src=log_path, dst=out_path)


def create_dpslog_from_detailed_logs(log_path: Path, parsed_log: ParsedLog) -> Optional[DpsLog]:
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

    dpslog = DpsLogInteraction.find_dpslog_by_start_time(start_time=start_time, encounter=encounter)

    if dpslog:
        logger.info(f"Log already found in database, returning existing log {dpslog}")
    else:
        logger.info(f"Creating new log entry for {log_path}")
        players = [player["account"] for player in parsed_log.json_detailed["players"]]
        dpslog, created = DpsLog.objects.update_or_create(
            defaults={
                "duration": parsed_log.get_duration(),
                "player_count": len(players),
                "encounter": encounter,
                "boss_name": parsed_log.json_detailed["fightName"],
                "cm": parsed_log.json_detailed["isCM"],
                "lcm": parsed_log.json_detailed["isLegendaryCM"],
                "emboldened": "b68087" in parsed_log.json_detailed["buffMap"],
                "success": parsed_log.json_detailed["success"],
                "final_health_percentage": final_health_percentage,
                "gw2_build": parsed_log.json_detailed["gW2Build"],
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
        dpslog = cls.find_dpslog_by_name(log_path=log_path)
        if dpslog is None:
            if parsed_path is None:
                logger.warning(f"{log_path} was not parsed")
                return False

            parsed_log = ParsedLog.from_ei_parsed_path(parsed_path=parsed_path)
            dpslog = create_dpslog_from_detailed_logs(log_path=log_path, parsed_log=parsed_log)

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

    @staticmethod
    def find_dpslog_by_start_time(start_time: datetime.datetime, encounter: Encounter) -> Optional[DpsLog]:
        """Find a log in the database with a similar start time and encounter name as the current log.
        This handles the case where a log was processed by someone else and we cannot search based on the name.
        """
        dpslogs = DpsLog.objects.filter(
            start_time__range=(
                start_time - datetime.timedelta(seconds=5),
                start_time + datetime.timedelta(seconds=5),
            ),
            encounter__name=encounter.name,
        )
        if len(dpslogs) > 1:
            # Problem when multiple people upload the same log at exactly the same time
            # unsure if this can/will occur.
            raise Exception("Multiple dpslogs found for %s, check the admin." % encounter.name)
        elif len(dpslogs) == 0:
            return None
        else:
            return dpslogs.first()

    @staticmethod
    def find_dpslog_by_name(log_path: Path) -> Optional[DpsLog]:
        """Find a dpslog in the database with the same log_path name."""
        try:
            dpslog = DpsLog.objects.get(local_path__endswith=log_path.name)
        except DpsLog.DoesNotExist:
            dpslog = None
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
