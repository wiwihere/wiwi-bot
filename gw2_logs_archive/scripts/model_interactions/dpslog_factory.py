from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Optional

from gw2_logs.models import Player
from scripts.utilities.metadata_parsed import MetadataParsed
from scripts.utilities.parsed_log import ParsedLog

logger = logging.getLogger(__name__)


def defaults_from_parsedlog(parsed_log: ParsedLog, log_path: Path) -> dict:
    """Build defaults dict for DpsLog from an Elite Insights parsed log."""
    players = [player["account"] for player in parsed_log.json_detailed["players"]]

    defaults = {
        "duration": parsed_log.get_duration(),
        "player_count": len(players),
        # encounter resolution belongs to the service; factory doesn't touch DB for Encounter
        "boss_name": parsed_log.json_detailed.get("fightName"),
        "cm": parsed_log.json_detailed.get("isCM"),
        "lcm": parsed_log.json_detailed.get("isLegendaryCM"),
        "emboldened": "b68087" in parsed_log.json_detailed.get("buffMap", {}),
        "success": parsed_log.json_detailed.get("success"),
        "final_health_percentage": parsed_log.get_final_health_percentage(),
        "gw2_build": parsed_log.json_detailed.get("gW2Build"),
        "players": players,
        "core_player_count": len(Player.objects.filter(gw2_id__in=players, role="core")),
        "friend_player_count": len(Player.objects.filter(gw2_id__in=players, role="friend")),
        "local_path": log_path,
        "phasetime_str": parsed_log.get_phasetime_str(),
    }

    return defaults


def defaults_from_metadata(
    metadata: dict, log_path: Optional[Path] = None, detailed_info: Optional[dict] = None
) -> dict:
    """Build defaults dict for DpsLog from dps.report metadata dict.

    Normalizes `metadata` with `MetadataParsed` then constructs the defaults
    dictionary expected by the service/repository.
    """
    mp = MetadataParsed.from_raw(metadata, detailed_info=detailed_info)

    players = mp.players_raw

    defaults = {
        # Service is responsible for resolving Encounter objects from boss ids
        "success": mp.raw.get("encounter", {}).get("success"),
        "duration": datetime.timedelta(seconds=mp.duration),
        "url": mp.raw.get("permalink"),
        "player_count": mp.raw.get("encounter", {}).get("numberOfPlayers"),
        "boss_name": mp.boss_name,
        "cm": mp.raw.get("encounter", {}).get("isCm"),
        "gw2_build": mp.raw.get("encounter", {}).get("gw2Build"),
        "players": players,
        "core_player_count": len(Player.objects.filter(gw2_id__in=players, role="core")),
        "friend_player_count": len(Player.objects.filter(gw2_id__in=players, role="friend")),
        "report_id": mp.raw.get("id"),
        "local_path": log_path,
        "json_dump": mp.as_dict(),
    }

    return defaults
