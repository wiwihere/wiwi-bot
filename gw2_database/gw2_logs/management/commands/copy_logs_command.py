# %%
import os
import shutil
from itertools import chain
from pathlib import Path

from bot_settings import settings
from django.core.management.base import BaseCommand
from scripts import copy_logs
from scripts.log_helpers import (
    ITYPE_GROUPS,
    WEBHOOKS,
    create_folder_names,
    find_log_by_date,
    today_y_m_d,
    zfill_y_m_d,
)


class Command(BaseCommand):
    help = "Update leaderboards on discord"

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
