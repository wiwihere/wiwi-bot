from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Optional

from gw2_logs.models import Player
from scripts.utilities.metadata_parsed import MetadataParsed
from scripts.utilities.parsed_log import DetailedParsedLog

logger = logging.getLogger(__name__)


def defaults_from_parsedlog(parsed_log: DetailedParsedLog, log_path: Path) -> dict:
    """Build defaults dict for DpsLog from an Elite Insights parsed log."""
    players = [player["account"] for player in parsed_log.data["players"]]

    defaults = {
        "duration": parsed_log.get_duration(),
        "player_count": len(players),
        # encounter resolution belongs to the service; factory doesn't touch DB for Encounter
        "boss_name": parsed_log.data.get("fightName"),
        "cm": parsed_log.data.get("isCM"),
        "lcm": parsed_log.data.get("isLegendaryCM"),
        "emboldened": "b68087" in parsed_log.data.get("buffMap", {}),
        "success": parsed_log.data.get("success"),
        "final_health_percentage": parsed_log.get_final_health_percentage(),
        "gw2_build": parsed_log.data.get("gW2Build"),
        "players": players,
        "core_player_count": len(Player.objects.filter(gw2_id__in=players, role="core")),
        "friend_player_count": len(Player.objects.filter(gw2_id__in=players, role="friend")),
        "local_path": log_path,
        "phasetime_str": parsed_log.get_phasetime_str(),
    }

    return defaults
