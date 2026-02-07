from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Optional
from zipfile import Path

from dateutil.parser import parse
from django.conf import settings
from gw2_logs.models import Encounter, Player
from scripts.utilities.parsed_log import DetailedParsedLog

logger = logging.getLogger(__name__)


@dataclass
class MetadataParsed:
    raw: dict

    @property
    def start_time(self) -> Optional[datetime.datetime]:
        et = self.raw["encounterTime"]
        if et is None:
            return None
        try:
            return datetime.datetime.fromtimestamp(et, tz=datetime.timezone.utc)
        except Exception:
            return None

    @property
    def duration(self) -> float:
        return float(self.raw["encounter"]["duration"])

    @property
    def boss_id(self) -> int:
        return self.raw["encounter"]["bossId"]

    @property
    def boss_name(self) -> str:
        return self.raw["encounter"]["boss"]

    def get_players(self) -> list[str]:
        """Create list of players each entry is the gw2 account name"""
        return [p.get("display_name") for p in self.raw["players"].values()]

    def apply_boss_fixes(self, detailed: Optional[dict] = None) -> "MetadataParsed":
        """Apply boss fixes (Ai, OLC mappings, Eye of Judgement).

        Returns self to allow chaining.
        """
        # Ai: use detailed fightName split if available
        if self.raw["encounter"]["boss"] == "Ai" and detailed:
            try:
                self.raw["encounter"]["boss"] = detailed["fightName"].split(",")[0]
                if self.raw["encounter"]["boss"] == "Dark Ai":
                    self.raw["encounter"]["bossId"] = -23254
            except Exception:
                logger.debug("Could not apply Ai boss fix")

        # OLC boss id mapping
        if self.raw["encounter"]["bossId"] in [25413, 25423, 25416]:
            self.raw["encounter"]["bossId"] = 25414

        # Eye of Judgement -> Eye of Fate
        if self.raw["encounter"]["boss"] == "Eye of Judgement":
            self.raw["encounter"]["boss"] = "Eye of Fate"
            self.raw["encounter"]["bossId"] = 19844

        return self

    def apply_metadata_fix(self, detailed: Optional[DetailedParsedLog] = None) -> "MetadataParsed":
        """Apply legacy metadata fixes (duration/isCm/start time) using detailed info.

        Returns self to allow chaining.
        """
        try:
            duration_seconds = int(self["encounter"]["duration"])
        except Exception:
            duration_seconds = 0

        if duration_seconds == 0 and detailed:
            try:
                start_time = parse(detailed["timeStart"]).astimezone(datetime.timezone.utc)
                self.raw["encounter"]["duration"] = detailed.get("durationMS", 0) / 1000
                self.raw["encounter"]["isCm"] = detailed.get("isCM")
                self.raw["encounterTime"] = int(start_time.timestamp())
            except Exception:
                logger.debug("Could not apply metadata fix from detailed info")

        return self


class MetadataInteractor:
    """Class to interact with MetadataParsed, applying fixes and normalization."""

    data: MetadataParsed

    @staticmethod
    def apply_fixes(self, detailed: Optional[DetailedParsedLog] = None) -> MetadataParsed:
        """Apply all relevant fixes to the metadata."""
        return self.data.apply_boss_fixes(detailed=detailed).apply_metadata_fix(detailed=detailed)

    def get_encounter(self) -> Optional[Encounter]:
        try:
            return Encounter.objects.get(dpsreport_boss_id=self.data["encounter"]["bossId"])
        except Encounter.DoesNotExist:
            logger.critical(
                f"""
Encounter not part of database. Register? {self.data["encounter"]}
bossId:  {self.data["encounter"]["bossId"]}
bossname:  {self.data["encounter"]["boss"]}

"""
            )
            if settings.DEBUG:
                raise Encounter.DoesNotExist
            return None

    def to_defaults(
        self,
        log_path: Optional[Path] = None,
    ) -> dict:
        """Build defaults dict for DpsLog from dps.report self.data dict."""
        players = self.data.get_players()

        defaults = {
            "success": self.data.raw["encounter"]["success"],
            "duration": datetime.timedelta(seconds=self.data.raw["encounter"]["duration"]),
            "url": self.data.raw.get("permalink"),
            "player_count": self.data.raw["encounter"]["numberOfPlayers"],
            "encounter": self.get_encounter(),
            "boss_name": self.data.raw["encounter"]["boss"],
            "cm": self.data.raw["encounter"]["isCm"],
            "lcm": self.data.raw["encounter"]["isLegendaryCm"],
            "gw2_build": self.data.raw["encounter"]["gw2Build"],
            "players": players,
            "core_player_count": len(Player.objects.filter(gw2_id__in=players, role="core")),
            "friend_player_count": len(Player.objects.filter(gw2_id__in=players, role="friend")),
            "report_id": self.data.raw["id"],
            "local_path": log_path,
            "json_dump": self.data.raw,
        }

        return defaults
