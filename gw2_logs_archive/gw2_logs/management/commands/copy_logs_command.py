# %%

from django.core.management.base import BaseCommand

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)

from scripts.log_helpers import today_y_m_d
from scripts.tools import copy_logs


class Command(BaseCommand):
    help = "Copy logs from .env/DPS_LOGS_DIR to .env/ONEDRIVE_LOGS_DIR"

    def add_arguments(self, parser):
        parser.add_argument("--y", type=int, nargs="?", default=None)
        parser.add_argument("--m", type=int, nargs="?", default=None)
        parser.add_argument("--d", type=int, nargs="?", default=None)
        parser.add_argument("--itype_groups", nargs="*", default=["raid", "strike", "fractal"])

    def handle(self, *args, **options):
        y = options["y"]
        m = options["m"]
        d = options["d"]
        itype_groups = options["itype_groups"]
        if y is None:
            y, m, d = today_y_m_d()

        copy_logs.copy_logs(y, m, d, itype_groups)
