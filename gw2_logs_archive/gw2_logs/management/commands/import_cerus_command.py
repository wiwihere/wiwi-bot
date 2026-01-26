if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

from django.core.management.base import BaseCommand
from scripts.encounter_progression.cerus_service import run_cerus_cm
from scripts.log_helpers import today_y_m_d


class Command(BaseCommand):
    help = "Import Cerus LCM logs and track progression."

    def add_arguments(self, parser):
        parser.add_argument("--y", type=int, nargs="?", default=None)
        parser.add_argument("--m", type=int, nargs="?", default=None)
        parser.add_argument("--d", type=int, nargs="?", default=None)

    def handle(self, *args, **options):
        y = options["y"]
        m = options["m"]
        d = options["d"]
        if y is None:
            y, m, d = today_y_m_d()

        run_cerus_cm(y, m, d)
