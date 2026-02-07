from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dateutil.parser import parse
from scripts.log_processing.log_uploader import DpsReportUploader
from scripts.utilities.parsed_log import DetailedParsedLog

logger = logging.getLogger(__name__)


@dataclass
class MetadataParsed:
    data: dict

    def as_dict(self) -> dict:
        return self.data

    def to_dpslog_defaults(self, log_path: Optional[Path] = None) -> dict:
        """Return a pure dict of dpslog defaults derived from metadata (no ORM).

        This should only contain primitive types and lists so it is safe to
        pass around without Django configured.
        """
        players = self.get_players()

        defaults = {
            "success": self.data.get("encounter", {}).get("success"),
            "duration": datetime.timedelta(seconds=self.data.get("encounter", {}).get("duration", 0)),
            "url": self.data.get("permalink"),
            "player_count": int(self.data.get("encounter", {}).get("numberOfPlayers", 0)),
            "boss_id": self.data.get("encounter", {}).get("bossId"),
            "boss_name": self.data.get("encounter", {}).get("boss"),
            "cm": self.data.get("encounter", {}).get("isCm"),
            "lcm": self.data.get("encounter", {}).get("isLegendaryCm"),
            "gw2_build": self.data.get("encounter", {}).get("gw2Build"),
            "players": players,
            "report_id": self.data.get("id"),
            "local_path": log_path,
            "json_dump": self.data,
        }

        return defaults

    @classmethod
    def from_dps_report_url(cls, url: str) -> "MetadataParsed":
        """Create DetailedParsedLog from dps.report url by requesting detailed info from the API."""
        data = DpsReportUploader().request_metadata(url=url)
        return cls(data=data)

    @property
    def start_time(self) -> Optional[datetime.datetime]:
        et = self.data["encounterTime"]
        if et is None:
            return None
        try:
            return datetime.datetime.fromtimestamp(et, tz=datetime.timezone.utc)
        except Exception:
            return None

    @property
    def duration(self) -> float:
        return float(self.data["encounter"]["duration"])

    @property
    def boss_id(self) -> int:
        return self.data["encounter"]["bossId"]

    @property
    def boss_name(self) -> str:
        return self.data["encounter"]["boss"]

    def get_players(self) -> list[str]:
        """Create list of players each entry is the gw2 account name"""
        return [p.get("display_name") for p in self.data["players"].values()]

    def apply_boss_fixes(self, detailed: Optional[dict] = None) -> "MetadataParsed":
        """Apply boss fixes (Ai, OLC mappings, Eye of Judgement).

        Returns self to allow chaining.
        """
        # Ai: use detailed fightName split if available
        if self.data["encounter"]["boss"] == "Ai" and detailed:
            try:
                self.data["encounter"]["boss"] = detailed["fightName"].split(",")[0]
                if self.data["encounter"]["boss"] == "Dark Ai":
                    self.data["encounter"]["bossId"] = -23254
            except Exception:
                logger.debug("Could not apply Ai boss fix")

        # OLC boss id mapping
        if self.data["encounter"]["bossId"] in [25413, 25423, 25416]:
            self.data["encounter"]["bossId"] = 25414

        # Eye of Judgement -> Eye of Fate
        if self.data["encounter"]["boss"] == "Eye of Judgement":
            self.data["encounter"]["boss"] = "Eye of Fate"
            self.data["encounter"]["bossId"] = 19844

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
                self.data["encounter"]["duration"] = detailed.get("durationMS", 0) / 1000
                self.data["encounter"]["isCm"] = detailed.get("isCM")
                self.data["encounterTime"] = int(start_time.timestamp())
            except Exception:
                logger.debug("Could not apply metadata fix from detailed info")

        return self
