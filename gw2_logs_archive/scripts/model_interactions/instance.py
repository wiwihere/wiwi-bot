# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import logging
from dataclasses import dataclass
from functools import cached_property

import numpy as np
from django.conf import settings
from django.db.models import Q, QuerySet
from gw2_logs.models import (
    DpsLog,
    Instance,
    InstanceClear,
    InstanceClearGroup,
)
from scripts.log_helpers import get_rank_emote

logger = logging.getLogger(__name__)


@dataclass
class InstanceInteraction:
    """Single instance; raidwing or fractal scale or strikes grouped per expansion."""

    def __init__(self, instance: Instance):
        self.instance = instance

        self.instance_type: str = self.instance.instance_group.name

    @cached_property
    def min_core_count(self) -> int:
        if settings.INCLUDE_NON_CORE_LOGS:
            return 0
        return settings.CORE_MINIMUM[self.instance.instance_group.name]

    def get_all_succesful_clears(self, emboldened: bool = False) -> QuerySet:
        return self.instance.instance_clears.filter(
            success=True,
            emboldened=emboldened,
            core_player_count__gte=self.min_core_count,
        ).order_by("duration")
