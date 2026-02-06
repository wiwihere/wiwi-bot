# %%
from pathlib import Path
from typing import Optional, Tuple

from gw2_logs.models import DpsLog, Encounter


class DpsLogRepository:
    """Small adapter around Django ORM for `DpsLog` operations.

    Keeps ORM usage in one place to make higher-level services easier to test.
    """

    @staticmethod
    def find_by_name(log_path: Path) -> Optional[DpsLog]:
        try:
            return DpsLog.objects.get(local_path__endswith=log_path.name)
        except DpsLog.DoesNotExist:
            return None

    @staticmethod
    def find_by_start_time(start_time, encounter: Encounter) -> Optional[DpsLog]:
        dpslogs = DpsLog.objects.filter(
            start_time__range=(
                start_time - __import__("datetime").timedelta(seconds=5),
                start_time + __import__("datetime").timedelta(seconds=5),
            ),
            encounter__name=encounter.name,
        )
        if len(dpslogs) == 0:
            return None
        if len(dpslogs) > 1:
            raise Exception("Multiple dpslogs found for %s, check the admin." % encounter.name)
        return dpslogs.first()

    @staticmethod
    def update_or_create(start_time, defaults: dict) -> Tuple[DpsLog, bool]:
        dpslog, created = DpsLog.objects.update_or_create(defaults=defaults, start_time=start_time)
        return dpslog, created

    @staticmethod
    def get_by_url(url: str) -> Optional[DpsLog]:
        return DpsLog.objects.filter(url=url).first()

    @staticmethod
    def save(dpslog: DpsLog) -> None:
        """Persist an existing DpsLog instance."""
        dpslog.save()

    @staticmethod
    def delete(dpslog: DpsLog) -> None:
        """Delete an existing DpsLog instance."""
        dpslog.delete()
