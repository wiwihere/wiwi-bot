# %%

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import logging
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
from scripts.model_interactions.dpslog_service import DpsLogService
from scripts.utilities.parsed_log import ParsedLog

logger = logging.getLogger(__name__)


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
    # TODO replace all callers to this function with a call to DpsLogService.create_from_ei and remove this adapter to consolidate logic in the service.
    # Delegate creation to the centralized service to avoid duplicated logic.
    service = DpsLogService()
    return service.create_from_ei(parsed_log=parsed_log, log_path=log_path)


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
        metadata: dict, encounter: Optional[Encounter] = None, log_path: Optional[Path] = None
    ) -> DpsLog:
        """Backward-compatible adapter that delegates to `DpsLogService`.

        Keeps the same callsite shape so callers can migrate incrementally.
        """
        # TODO replace all callers to this function with a call to DpsLogService.create_from_ei and remove this adapter to consolidate logic in the service.
        service = DpsLogService()
        return service.create_or_update_from_dps_report(metadata=metadata, log_path=log_path)

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
