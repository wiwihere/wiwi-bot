# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import logging
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.db.models import Q
from gw2_logs.models import DpsLog, Encounter, Player
from scripts.log_helpers import get_rank_emote
from scripts.model_interactions.dpslog_repository import DpsLogRepository
from scripts.utilities.failed_log_mover import move_failed_log
from scripts.utilities.parsed_log import ParsedLog

logger = logging.getLogger(__name__)


class DpsLogService:
    """Service consolidating creation/update logic for `DpsLog` records.

    This is intentionally conservative: it extracts the mapping logic from
    existing helpers so callers can be migrated gradually.
    """

    def __init__(self, repository: DpsLogRepository = DpsLogRepository()):
        # Keep repository private; expose domain methods on the service.
        self._repo = repository

    # Repository facade methods (explicit return types improve clarity)
    def find_by_name(self, log_path: Path) -> Optional[DpsLog]:
        return self._repo.find_by_name(log_path)

    def find_by_start_time(self, start_time, encounter: Encounter) -> Optional[DpsLog]:
        return self._repo.find_by_start_time(start_time=start_time, encounter=encounter)

    def get_by_url(self, url: str) -> Optional[DpsLog]:
        return self._repo.get_by_url(url)

    def create_from_ei(self, parsed_log: ParsedLog, log_path: Path) -> Optional[DpsLog]:
        """Create or return existing DpsLog from a detailed EI parsed log.

        Returns the DpsLog or None on handled failures.
        """
        logger.info(f"Processing detailed log: {log_path}")

        encounter = parsed_log.get_encounter()
        if encounter is None:
            logger.error(f"Encounter for log {log_path} could not be found. Skipping log.")
            move_failed_log(log_path, reason="failed")
            return None

        final_health_percentage = parsed_log.get_final_health_percentage()
        if final_health_percentage == 100.0 and encounter.name == "Eye of Fate":
            move_failed_log(log_path, reason="failed")
            return None

        start_time = parsed_log.get_starttime()

        dpslog = self.find_by_start_time(start_time=start_time, encounter=encounter)

        if dpslog:
            logger.info(f"Log already found in database, returning existing log {dpslog}")
            return dpslog

        logger.info(f"Creating new log entry for {log_path}")
        players = [player["account"] for player in parsed_log.json_detailed["players"]]

        defaults = {
            "duration": parsed_log.get_duration(),
            "player_count": len(players),
            "encounter": encounter,
            "boss_name": parsed_log.json_detailed["fightName"],
            "cm": parsed_log.json_detailed["isCM"],
            "lcm": parsed_log.json_detailed["isLegendaryCM"],
            "emboldened": "b68087" in parsed_log.json_detailed.get("buffMap", {}),
            "success": parsed_log.json_detailed["success"],
            "final_health_percentage": final_health_percentage,
            "gw2_build": parsed_log.json_detailed.get("gW2Build"),
            "players": players,
            "core_player_count": len(Player.objects.filter(gw2_id__in=players, role="core")),
            "friend_player_count": len(Player.objects.filter(gw2_id__in=players, role="friend")),
            "local_path": log_path,
            "phasetime_str": parsed_log.get_phasetime_str(),
        }

        dpslog, created = self._repo.update_or_create(start_time=start_time, defaults=defaults)
        return dpslog

    def create_or_update_from_dps_report(self, metadata: dict, log_path: Optional[Path] = None) -> DpsLog:
        """Create or update a DpsLog from dps.report metadata.

        Returns DpsLog object.
        """
        if metadata.get("players"):
            players = [i["display_name"] for i in metadata["players"].values()]
        else:
            players = []

        start_time = datetime.datetime.fromtimestamp(metadata["encounterTime"], tz=datetime.timezone.utc)

        defaults = {
            "encounter": self._get_encounter_for_metadata(metadata),
            "success": metadata["encounter"]["success"],
            "duration": datetime.timedelta(seconds=metadata["encounter"]["duration"]),
            "url": metadata.get("permalink"),
            "player_count": metadata["encounter"].get("numberOfPlayers"),
            "boss_name": metadata["encounter"].get("boss"),
            "cm": metadata["encounter"].get("isCm"),
            "gw2_build": metadata["encounter"].get("gw2Build"),
            "players": players,
            "core_player_count": len(Player.objects.filter(gw2_id__in=players, role="core")),
            "friend_player_count": len(Player.objects.filter(gw2_id__in=players, role="friend")),
            "report_id": metadata.get("id"),
            "local_path": log_path,
            "json_dump": metadata,
        }

        dpslog, created = self._repo.update_or_create(start_time=start_time, defaults=defaults)
        return dpslog

    def _get_encounter_for_metadata(self, metadata: dict) -> Optional[Encounter]:
        try:
            return Encounter.objects.get(dpsreport_boss_id=metadata["encounter"]["bossId"])
        except Encounter.DoesNotExist:
            logger.critical("Encounter not part of database. Register? %s", metadata["encounter"])
            if settings.DEBUG:
                raise
            return None

    def get_rank_emote_log(self, dpslog: DpsLog) -> str:
        """Return rank emote string for a log (used in discord messages)."""
        encounter_success_all = None
        if dpslog.success:
            encounter_success_all = list(
                dpslog.encounter.dps_logs.filter(success=True, cm=dpslog.cm, emboldened=False)
                .filter(
                    Q(start_time__gte=dpslog.start_time - datetime.timedelta(days=9999))
                    & Q(start_time__lte=dpslog.start_time)
                )
                .order_by("duration")
            )
        rank_str = get_rank_emote(
            indiv=dpslog,
            group_list=encounter_success_all,
            core_minimum=settings.CORE_MINIMUM[dpslog.encounter.instance.instance_group.name],
            custom_emoji_name=False,
        )
        return rank_str

    def build_health_str(self, dpslog: DpsLog) -> str:
        """Build health string with leading zeros for discord message."""
        health_str = ".".join(
            [str(int(i)).zfill(2) for i in str(round(dpslog.final_health_percentage, 2)).split(".")]
        )  # makes 02.20%
        if health_str == "100.00":
            health_str = "100.0"
        return health_str
