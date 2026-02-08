# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging

from django.core.management.base import BaseCommand
from scripts.runners.run_log_processing import run_log_processing

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    FLOW:
    1. Find unprocessed logs for date
    2. Parse locally with EI
    3. Upload to dps.report
    4. Create/update InstanceClearGroup
    5. Build and send Discord message
    6. Update leaderboards and exit
    """

    help = "Parse logs and create message on discord"

    def add_arguments(self, parser):
        parser.add_argument("--y", type=int, nargs="?", default=None)
        parser.add_argument("--m", type=int, nargs="?", default=None)
        parser.add_argument("--d", type=int, nargs="?", default=None)
        parser.add_argument("--itype_groups", nargs="*")  # default doesnt work with nargs="*"

    def handle(self, *args, **options):
        # Initialize variables
        y = options["y"]
        m = options["m"]
        d = options["d"]

        itype_groups = options["itype_groups"]

        run_log_processing(y=y, m=m, d=d, itype_groups=itype_groups)


if __name__ == "__main__":
    options = {}
    options["y"] = 2026
    options["m"] = 2
    options["d"] = 5
    options["itype_groups"] = False

# %%
