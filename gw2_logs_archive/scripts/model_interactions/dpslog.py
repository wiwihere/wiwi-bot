# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging

from gw2_logs.models import DpsLog
from scripts.log_helpers import (
    BOSS_HEALTH_PERCENTAGES,
    BOSS_MAX_DURATION,
    get_duration_str,
)

logger = logging.getLogger(__name__)


class DpsLogMessageBuilder:
    def __init__(self, dpslog: DpsLog):
        self.dpslog = dpslog

    def build_health_str(self) -> str:
        """Build health string with leading zeros for discord message."""
        health_str = ".".join(
            [str(int(i)).zfill(2) for i in str(round(self.dpslog.final_health_percentage, 2)).split(".")]
        )  # makes 02.20%
        if health_str == "100.00":
            health_str = "100.0"
        return health_str

    @property
    def max_duration_seconds(self) -> int:
        return BOSS_MAX_DURATION[self.dpslog.encounter.name]

    @property
    def boss_health_percentages(self) -> list[int]:
        return BOSS_HEALTH_PERCENTAGES[self.dpslog.encounter.name]

    def health_percentage_to_remaining_time_str(self, hp: int) -> str:
        """Get the time in seconds when the boss reached a certain health percentage.
        This is shown in the progression message as the remaining time until enrage at certain health milestones.
        """
        time_s = self.dpslog.health_timers.get(str(hp))
        if time_s is None:
            return " -- "
        else:
            if time_s <= 0:
                return " -- "
            return get_duration_str(int(self.max_duration_seconds - time_s))

    def build_phasetime_str(self) -> str:
        """For progression logging when a milestone (from BOSS_HEALTH_PERCENTAGES) has been reached
        is calculated from detailed logs. The remaining time until enrage is shown at the specified health percentages.

        For example, for Cerus the times at 80%, 50% and 10% health are calculated.
        This results in a string like:
        '8:12 | 5:34 | 1:07'
        """

        if self.dpslog.encounter.name not in BOSS_HEALTH_PERCENTAGES.keys():
            return None

        # Build phasetime list like ["8:12", "5:34", "1:07"] based on the health timers in the dpslog and the
        # boss health percentages defined in log_helpers.BOSS_HEALTH_PERCENTAGES
        phasetime_lst = [self.health_percentage_to_remaining_time_str(hp) for hp in self.boss_health_percentages]

        return " | ".join(phasetime_lst)


if __name__ == "__main__":
    dpslog = DpsLog.objects.get(id=4933)
    self = DpsLogMessageBuilder(dpslog)

# %%
