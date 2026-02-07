# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import logging
from dataclasses import dataclass

import numpy as np
from django.conf import settings
from django.db.models import Q
from gw2_logs.models import (
    DpsLog,
    InstanceClear,
    InstanceClearGroup,
)
from scripts.log_helpers import get_rank_emote

logger = logging.getLogger(__name__)


@dataclass
class InstanceClearInteraction:
    """Single instance clear; raidwing or fractal scale or strikes grouped per expansion."""

    iclear: InstanceClear

    @classmethod
    def update_or_create_from_logs(
        cls,
        dpslog_list: list[DpsLog],
        instance_group: InstanceClearGroup = None,
    ) -> "InstanceClearInteraction":
        """Log should be filtered on instance"""
        iname = f"{dpslog_list[0].encounter.instance.name_lower}__{dpslog_list[0].start_time.strftime('%Y%m%d')}"

        # Check if all logs are from the same wing.
        same_wing = all(log.encounter.instance == dpslog_list[0].encounter.instance for log in dpslog_list)
        if not same_wing:
            raise ValueError("Not all logs of same wing.")

        # Create or update instance
        iclear, created = InstanceClear.objects.update_or_create(
            defaults={
                "instance": dpslog_list[0].encounter.instance,
                "instance_clear_group": instance_group,
            },
            name=iname,
        )
        if created:
            logger.info(f"Created {iclear}")

        # All logs that are not yet part of the instance clear will be added.
        for dpslog in set(dpslog_list).difference(set(iclear.dps_logs.all())):
            dpslog.instance_clear = iclear
            dpslog.save()

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
    def from_name(cls, name: str) -> "InstanceClearGroup":
        return cls(InstanceClear.objects.get(name=name))

    def get_rank_emote_ic(self) -> str:
        """Look up the rank of the instance clear compared to previous logs.
        Returns the emotestr with information on the rank and how much slower
        it was compared to the fastest clear until that point in time.
        example:
        '<:r20_of45_slower1804_9s:1240399925502545930>'
        """
        success_group = None
        if self.iclear.success:
            success_group = list(
                self.iclear.instance.instance_clears.filter(success=True, emboldened=False)
                .filter(
                    Q(start_time__gte=self.iclear.start_time - datetime.timedelta(days=9999))
                    & Q(start_time__lte=self.iclear.start_time),
                )
                .order_by("duration")
            )
        rank_str = get_rank_emote(
            indiv=self.iclear,
            group_list=success_group,
            core_minimum=settings.CORE_MINIMUM[self.iclear.instance.instance_group.name],
        )
        return rank_str
