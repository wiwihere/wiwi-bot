# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging
from dataclasses import dataclass

from django.db.models import QuerySet
from gw2_logs.models import (
    Encounter,
)

logger = logging.getLogger(__name__)


@dataclass
class EncounterInteraction:
    """Single encounter; raidboss, strike or fractalboss."""

    encounter: Encounter

    def get_all_succesful_clears(
        self,
        cm: bool,
        lcm: bool,
        min_core_count: int,
        emboldened: bool = False,
    ) -> QuerySet:
        return self.encounter.dps_logs.filter(
            success=True,
            emboldened=emboldened,
            cm=cm,
            lcm=lcm,
            core_player_count__gte=min_core_count,
        ).order_by("duration")
