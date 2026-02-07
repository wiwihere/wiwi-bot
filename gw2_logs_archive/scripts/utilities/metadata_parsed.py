from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Optional

from dateutil.parser import parse
from django.conf import settings
from gw2_logs.models import Encounter

logger = logging.getLogger(__name__)


@dataclass
class MetadataParsed:
    raw: dict

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
        return self.raw["encounter"]["bossId"]

    @property
    def boss_name(self) -> Optional[str]:
        return self.raw["encounter"]["boss"]

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

    def apply_metadata_fix(self, detailed: Optional[dict] = None) -> "MetadataParsed":
        """Apply legacy metadata fixes (duration/isCm/start time) using detailed info.

        Returns self to allow chaining.
        """
        try:
            duration_seconds = int(self.encounter_info.get("duration", 0))
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
    def apply_fixes(self, detailed: Optional[dict] = None) -> MetadataParsed:
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
