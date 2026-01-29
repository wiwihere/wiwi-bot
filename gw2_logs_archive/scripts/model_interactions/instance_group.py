# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging

from django.db.models import QuerySet
from gw2_logs.models import (
    InstanceClearGroup,
    InstanceGroup,
)

logger = logging.getLogger(__name__)


class InstanceGroupInteraction:
    """Single instancegroup; raid, strike or fractal."""

    def __init__(self, instance_group: InstanceGroup):
        self.instance_group = instance_group
        self.instance_type = self.instance_group.name

    def get_all_successful_group_clears(self) -> QuerySet[InstanceClearGroup]:
        """Filter on duration_encounters to only include runs where all the same wings
        were selected  for leaderboard. e.g. with wing 8 the clear times went up,
        so we reset the leaderboard here.
        """
        # This is a str of wings + bosses that is included when looking up rank.
        duration_encounters: str = (
            InstanceClearGroup.objects.filter(type=self.instance_type)
            .order_by("start_time")
            .last()
            .duration_encounters
        )
        # Find all older icgs and sort them by duration
        return (
            InstanceClearGroup.objects.filter(
                success=True,
                duration_encounters=duration_encounters,
                type=self.instance_type,
                core_player_count__gte=self.instance_group.min_core_count,
            )
            .exclude(name__icontains="cm__")
            .order_by("duration")
        )
