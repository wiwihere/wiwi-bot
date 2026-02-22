# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging

from gw2_logs.models import DpsLog
from scripts.log_helpers import (
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
        if health_str == "00.00":
            health_str = "DEATH"
        return health_str

    def _health_percentage_to_remaining_time_str(self, hp: int) -> str:
        """Get the time in seconds when the boss reached a certain health percentage.
        This is shown in the progression message as the remaining time until enrage at certain health milestones.
        """
        max_duration_seconds = self.dpslog.encounter.enrage_time_seconds
        if max_duration_seconds is None:
            raise ValueError(
                f"Encounter {self.dpslog.encounter.name} does not have enrage_time_seconds defined in database."
            )

        time_s = self.dpslog.health_timers.get(str(hp))
        if time_s is None:
            return " -- "
        else:
            if time_s <= 0:
                return " -- "
            return get_duration_str(int(max_duration_seconds - time_s))

    def build_phasetime_str(self, display_health_percentages: list[int]) -> str:
        """For progression logging when a milestone (from display_health_percentages) has been reached
        is calculated from detailed logs. The remaining time until enrage is shown at the specified health percentages.

        For example, for Cerus the times at 80%, 50% and 10% health are calculated.
        This results in a string like:
        '8:12 | 5:34 | 1:07'
        """
        phasetime_lst = [self._health_percentage_to_remaining_time_str(hp) for hp in display_health_percentages]

        return " | ".join(phasetime_lst)


if __name__ == "__main__":
    dpslog = DpsLog.objects.get(id=4933)
    self = DpsLogMessageBuilder(dpslog)

# %%
