from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Optional

from dateutil.parser import parse

logger = logging.getLogger(__name__)


@dataclass
class MetadataParsed:
    raw: dict
    detailed: Optional[dict]

    @classmethod
    def from_raw(cls, metadata: dict, detailed_info: Optional[dict] = None) -> "MetadataParsed":
        m = metadata.copy()

        # Fix boss name for Ai if possible
        if m.get("encounter", {}).get("boss") == "Ai" and detailed_info:
            try:
                m["encounter"]["boss"] = detailed_info["fightName"].split(",")[0]
                if m["encounter"]["boss"] == "Dark Ai":
                    m["encounter"]["bossId"] = -23254
            except Exception:
                logger.debug("Could not fix Ai boss name from detailed_info")

        # Map OLC boss ids to canonical id
        if m.get("encounter", {}).get("bossId") in [25413, 25423, 25416]:
            m["encounter"]["bossId"] = 25414

        # Eye of Judgement -> Eye of Fate
        if m.get("encounter", {}).get("boss") == "Eye of Judgement":
            m["encounter"]["boss"] = "Eye of Fate"
            m["encounter"]["bossId"] = 19844

        # Fix broken metadata if duration is zero using detailed_info
        try:
            duration_seconds = int(m.get("encounter", {}).get("duration", 0))
        except Exception:
            duration_seconds = 0

        if duration_seconds == 0 and detailed_info:
            try:
                start_time = parse(detailed_info["timeStart"]).astimezone(datetime.timezone.utc)
                m["encounter"]["duration"] = detailed_info.get("durationMS", 0) / 1000
                m["encounter"]["isCm"] = detailed_info.get("isCM")
                m["encounterTime"] = int(start_time.timestamp())
            except Exception:
                logger.debug("Could not normalize metadata from detailed_info")

        return cls(raw=m, detailed=detailed_info)

    @property
    def encounter_info(self) -> dict:
        return self.raw.get("encounter", {})

    @property
    def start_time(self) -> Optional[datetime.datetime]:
        et = self.raw.get("encounterTime")
        if et is None:
            return None
        try:
            return datetime.datetime.fromtimestamp(et, tz=datetime.timezone.utc)
        except Exception:
            return None

    @property
    def duration(self) -> float:
        try:
            return float(self.raw.get("encounter", {}).get("duration", 0))
        except Exception:
            return 0.0

    @property
    def boss_id(self) -> Optional[int]:
        return self.encounter_info.get("bossId")

    @property
    def boss_name(self) -> Optional[str]:
        return self.encounter_info.get("boss")

    @property
    def players_raw(self) -> list:
        players = []
        if self.raw.get("players"):
            try:
                players = [(p.get("account") or p.get("display_name")) for p in self.raw["players"].values()]
            except Exception:
                logger.debug("Failed to extract players from metadata")
                players = []
        return players

    def as_dict(self) -> dict:
        return self.raw

    def apply_boss_fixes(self) -> "MetadataParsed":
        """Apply legacy boss fixes (Ai, OLC mappings, Eye of Judgement).

        Returns self to allow chaining.
        """
        # Ai: use detailed fightName split if available
        if self.raw["encounter"]["boss"] == "Ai" and self.detailed:
            try:
                self.raw["encounter"]["boss"] = self.detailed["fightName"].split(",")[0]
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

    def apply_metadata_fix(self) -> "MetadataParsed":
        """Apply legacy metadata fixes (duration/isCm/start time) using detailed info.

        Returns self to allow chaining.
        """
        try:
            duration_seconds = int(self.encounter_info.get("duration", 0))
        except Exception:
            duration_seconds = 0

        if duration_seconds == 0 and self.detailed:
            try:
                start_time = parse(self.detailed["timeStart"]).astimezone(datetime.timezone.utc)
                self.raw["encounter"]["duration"] = self.detailed.get("durationMS", 0) / 1000
                self.raw["encounter"]["isCm"] = self.detailed.get("isCM")
                self.raw["encounterTime"] = int(start_time.timestamp())
            except Exception:
                logger.debug("Could not apply metadata fix from detailed info")

        return self
