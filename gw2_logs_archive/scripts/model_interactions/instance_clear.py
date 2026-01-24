# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging
from dataclasses import dataclass

import numpy as np
from gw2_logs.models import (
    DpsLog,
    InstanceClear,
)

logger = logging.getLogger(__name__)


@dataclass
class InstanceClearInteraction:
    """Single instance clear; raidwing or fractal scale or strikes grouped per expansion."""

    iclear: InstanceClear

    @classmethod
    def from_logs(cls, logs: list[DpsLog], instance_group=None):
        """Log should be filtered on instance"""
        iname = f"{logs[0].encounter.instance.name_lower}__{logs[0].start_time.strftime('%Y%m%d')}"

        # Check if all logs are from the same wing.
        same_wing = all(log.encounter.instance == logs[0].encounter.instance for log in logs)
        if not same_wing:
            raise ValueError("Not all logs of same wing.")

        # Create or update instance
        iclear, created = InstanceClear.objects.update_or_create(
            defaults={
                "instance": logs[0].encounter.instance,
                "instance_clear_group": instance_group,
            },
            name=iname,
        )
        if created:
            logger.info(f"Created {iclear}")

        # All logs that are not yet part of the instance clear will be added.
        for log in set(logs).difference(set(iclear.dps_logs.all())):
            log.instance_clear = iclear
            log.save()

        # Update start_time
        iclear.start_time = iclear.dps_logs.all().order_by("start_time").first().start_time

        # Calculate duration
        last_log = iclear.dps_logs.all().order_by("start_time").last()
        iclear.duration = last_log.start_time + last_log.duration - iclear.start_time

        if len(iclear.dps_logs.all()) > 0:
            iclear.core_player_count = int(np.median([log.core_player_count for log in iclear.dps_logs.all()]))
            iclear.friend_player_count = int(np.median([log.friend_player_count for log in iclear.dps_logs.all()]))

        # Check if all encounters have been finished.
        encounter_count = max([i.nr for i in iclear.instance.encounters.all()])

        iclear.success = False
        if len(iclear.dps_logs.filter(success=True)) == encounter_count:
            iclear.success = True

        iclear.emboldened = False
        if len(iclear.dps_logs.filter(success=True, emboldened=True)) > 0:
            iclear.emboldened = True

        iclear.save()
        return cls(iclear)

    @classmethod
    def from_name(cls, name):
        return cls(InstanceClear.objects.get(name=name))
