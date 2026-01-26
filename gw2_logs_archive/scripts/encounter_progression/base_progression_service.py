# %% gw2_logs_archive\scripts\encounter_progression\base_progression_service.py
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import logging
from typing import Tuple

from django.db.models import Q
from gw2_logs.models import (
    Encounter,
    InstanceClear,
    InstanceClearGroup,
)

logger = logging.getLogger(__name__)


class ProgressionService:
    def __init__(self, clear_group_base_name: str, clear_name: str, encounter: Encounter) -> None:
        self.clear_group_base_name = clear_group_base_name
        self.clear_name = clear_name
        self.encounter = encounter

        logger.info(f"Starting progression run for {self.encounter.name}: {self.clear_name}")

        self.iclear_group = self.get_iclear_group()
        self.iclear = self.get_iclear()

    def get_iclear_group(self) -> InstanceClearGroup:
        """Load or create the InstanceClearGroup for this progression day."""
        iclear_group, created = InstanceClearGroup.objects.get_or_create(name=self.clear_name, type="strike")
        if created:
            logger.info(f"Created InstanceClearGroup {iclear_group.name}")
        return iclear_group

    def get_iclear(self) -> InstanceClear:
        """Load or create the InstanceClear for this progression day."""
        iclear, created = InstanceClear.objects.get_or_create(
            defaults={
                "instance": self.encounter.instance,
                "instance_clear_group": self.iclear_group,
            },
            name=self.clear_name,
        )
        if created:
            logger.info(f"Created InstanceClear {iclear.name}")

        return iclear

    def _calculate_progression_day(self) -> int:
        # The progression_days_count is the total days up to this point for this progression
        progression_days_count = len(
            InstanceClearGroup.objects.filter(
                Q(name__startswith=f"{self.clear_group_base_name}__") & Q(start_time__lte=self.iclear_group.start_time)
            )
        )
        return progression_days_count

    def get_message_author(self) -> str:
        """Create author name for discord message.
        The author is displayed at the top of the message.
        """
        return f"Day #{self._calculate_progression_day():02d}"

    def update_instance_clear(self) -> Tuple[InstanceClear, InstanceClearGroup]:
        """Update the iclear_group and iclear"""
        dps_logs_all = self.iclear_group.dps_logs_all
        if dps_logs_all:
            start_time = min([i.start_time for i in dps_logs_all])
            # Set iclear_group start time
            if self.iclear_group.start_time != start_time:
                logger.info(
                    f"Updating start time for {self.iclear_group.name} from {self.iclear_group.start_time} to {start_time}"
                )
                self.iclear_group.start_time = start_time
                self.iclear_group.save()

            # Set iclear start time
            if self.iclear.start_time != start_time:
                logger.info(
                    f"Updating start time for {self.iclear.name} from {self.iclear.start_time} to {start_time}"
                )
                self.iclear.start_time = start_time
                self.iclear.save()

            # Set iclear duration
            last_log = dps_logs_all[-1]
            calculated_duration = last_log.start_time + last_log.duration - self.iclear.start_time
            if self.iclear.duration != calculated_duration:
                logger.info(
                    f"Updating duration for {self.iclear.name} from {self.iclear.duration} to {calculated_duration}"
                )
                self.iclear.duration = calculated_duration
                self.iclear.save()
