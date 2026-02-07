# %%
"""DpsLog service module

Provides a single public `DpsLogService` that encapsulates creation and
lookup logic for `DpsLog` domain objects. Keep business rules (final-health,
emboldened checks, and move-on-failure) here so callers do not need to know
about the repository or filesystem layout.
"""

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import logging
from itertools import chain
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.db.models import Q
from gw2_logs.models import DpsLog, Player
from scripts.log_helpers import get_emboldened_wing, get_log_path_view, get_rank_emote
from scripts.model_interactions.dpslog_repository import DpsLogRepository
from scripts.model_interactions.encounter import EncounterInteraction
from scripts.utilities.failed_log_mover import move_failed_log
from scripts.utilities.metadata_parsed import MetadataParsed
from scripts.utilities.parsed_log import DetailedParsedLog

logger = logging.getLogger(__name__)


class DpsLogService:
    """TODO add docstring here"""

    def __init__(self, repository: DpsLogRepository = DpsLogRepository()):
        # Keep repository private; expose domain methods on the service.
        self.repo = repository

    # Repository facade methods (explicit return types improve clarity)
    def find_by_name(self, log_path: Path) -> Optional[DpsLog]:
        return self.repo.find_by_log_path(log_path)

    def get_by_url(self, url: str) -> Optional[DpsLog]:
        return self.repo.get_by_url(url)

    def delete(self, dpslog: DpsLog) -> None:
        """Delete log from database to avoid dangling references on failure"""
        logger.info(f"Deleting DpsLog {dpslog} from database")
        self.repo.delete(dpslog)

    def get_update_create_from_ei_parsed_log(
        self, detailed_parsed_log: DetailedParsedLog, log_path: Path
    ) -> Optional[DpsLog]:
        """Create or return existing DpsLog from a detailed EI parsed log.

        Returns the DpsLog or None on handled failures.
        """
        logger.info(f"{get_log_path_view(log_path)}: Processing detailed log")

        start_time = detailed_parsed_log.get_starttime()

        valid, move_reason = detailed_parsed_log.validate()  # raises ValueError on invalid log
        if not valid:
            if move_reason is not None:
                logger.warning(f"{get_log_path_view(log_path)}: Log is invalid. Moving log to {move_reason} folder.")
                move_failed_log(log_path, reason=move_reason)
            return None

        dpslog = self.repo.find_by_start_time(start_time=start_time, encounter=detailed_parsed_log.encounter)

        if dpslog:
            logger.info(f"Log already found in database, returning existing log {dpslog}")
        else:
            logger.info(f"{get_log_path_view(log_path)}: Creating new log entry for {log_path}")
            defaults = detailed_parsed_log.to_dpslog_defaults(log_path=log_path)

            # Resolve encounter and compute role-based player counts in service (ORM)
            defaults["encounter"] = detailed_parsed_log.encounter
            defaults["core_player_count"] = len(Player.objects.filter(gw2_id__in=defaults["players"], role="core"))
            defaults["friend_player_count"] = len(Player.objects.filter(gw2_id__in=defaults["players"], role="friend"))

            dpslog, created = self.repo.update_or_create(start_time=start_time, defaults=defaults)
        return dpslog

    def create_or_update_from_dps_report_metadata(
        self,
        metadata: MetadataParsed,
        log_path: Optional[Path] = None,
        url_only: bool = False,
    ) -> DpsLog:
        """Create or update a DpsLog from dps.report metadata.

        When `url_only` is True only minimal fields are written (the permalink),
        """

        if url_only:
            defaults = {"url": metadata.data.get("permalink")}
        else:
            defaults = metadata.to_dpslog_defaults(log_path=log_path)

            # Resolve encounter and compute role-based player counts in service (ORM)
            defaults["encounter"] = EncounterInteraction.find_by_dpsreport_metadata(metadata.data)
            defaults["core_player_count"] = len(Player.objects.filter(gw2_id__in=defaults["players"], role="core"))
            defaults["friend_player_count"] = len(Player.objects.filter(gw2_id__in=defaults["players"], role="friend"))

        dpslog, created = self.repo.update_or_create(start_time=metadata.start_time, defaults=defaults)
        return dpslog

    def fix_final_health_percentage(
        self,
        dpslog: DpsLog,
        detailed_parsed_log: Optional[DetailedParsedLog] = None,
    ) -> tuple[Optional[DpsLog], str | None]:
        """Update final health percentage on a DpsLog using optional detailed_info.

        Returns (dpslog, None) on success or (None, move_reason) when the log should be moved.
        """
        if dpslog.final_health_percentage is None:
            if dpslog.success is False:
                logger.info("    Requesting final boss health (service)")
                if detailed_parsed_log is None:
                    logger.debug("No detailed_info provided to fix_final_health_percentage")
                    return dpslog, None

                dpslog.final_health_percentage = detailed_parsed_log.get_final_health_percentage()
                if dpslog.final_health_percentage == 100.0 and dpslog.boss_name == "Eye of Fate":
                    return None, "failed"
            else:
                dpslog.final_health_percentage = 0
            dpslog.save()
        return dpslog, None

    def fix_emboldened(self, dpslog: DpsLog, detailed_parsed_log: Optional[dict] = None) -> DpsLog:
        """Set emboldened flag on a DpsLog using available detailed_info or wing schedule."""
        # FIXME can probably be removed? Or always just request detailed info when emboldened is None, since the wing schedule
        if (dpslog.emboldened is None) and (dpslog.encounter is not None):
            emboldened_wing = get_emboldened_wing(dpslog.start_time)
            if (
                (emboldened_wing == dpslog.encounter.instance.nr)
                and (dpslog.encounter.instance.instance_group.name == "raid")
                and not (dpslog.cm)
            ):
                logger.info("    Checking for emboldened (service)")
                if detailed_parsed_log is None:
                    logger.warning("No detailed_parsed_log provided to fix_emboldened")
                    dpslog.emboldened = False
                else:
                    if "presentInstanceBuffs" in detailed_parsed_log.data:
                        dpslog.emboldened = 68087 in list(chain(*detailed_parsed_log.data["presentInstanceBuffs"]))
                    else:
                        dpslog.emboldened = False
            else:
                dpslog.emboldened = False

            dpslog.save()
        return dpslog

    def update_permalink(self, dpslog: DpsLog, permalink: str) -> DpsLog:
        """Update only the `url` field on an existing `DpsLog` and persist it."""
        if dpslog.url != permalink:
            dpslog.url = permalink
            self.repo.save(dpslog)
        return dpslog

    def get_rank_emote_for_log(self, dpslog: DpsLog) -> str:
        """Return rank emote string for a log (used in discord messages).

        Looks up the rank of the log compared to previous logs.
        Returns the emotestr with information on the rank and how much slower
        it was compared to the fastest clear until that point in time.

        Returns emote string, e.g.:
        '<:r20_of45_slower1804_9s:1240399925502545930>'
        """

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
