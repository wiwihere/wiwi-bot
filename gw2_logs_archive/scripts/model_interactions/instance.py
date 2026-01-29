# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging

from django.db.models import QuerySet
from gw2_logs.models import (
    Encounter,
    Instance,
)

logger = logging.getLogger(__name__)


class InstanceInteraction:
    """Single instance; raidwing or fractal scale or strikes grouped per expansion."""

    def __init__(self, instance: Instance):
        self.instance = instance

        self.instance_type: str = self.instance.instance_group.name
        self.min_core_count: int = self.instance.instance_group.min_core_count

    def get_all_succesful_clears(self, emboldened: bool = False) -> QuerySet:
        return self.instance.instance_clears.filter(
            success=True,
            emboldened=emboldened,
            core_player_count__gte=self.min_core_count,
        ).order_by("duration")

    def get_all_encounters_for_leaderboard(self):
        return Encounter.objects.filter(
            use_for_icg_duration=True,
            instance=self.instance,
        ).order_by("nr")
