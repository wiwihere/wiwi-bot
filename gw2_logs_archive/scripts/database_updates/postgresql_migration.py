# %%
import logging
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

import pandas as pd
from django.conf import settings

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)

from scripts.log_helpers import zfill_y_m_d

logger = logging.getLogger(__name__)
from gw2_logs.models import DpsLog, Emoji, Encounter, Instance, InstanceClear, InstanceClearGroup


# %%

# Migration from sqlite to postgres
# python -Xutf8 gw2_logs_archive\manage.py dumpdata > wholedb.json
# CHANGE settings database
# django check --database default
# django migrate --run-syncdb

# permission errors if not using manage.py
# python gw2_logs_archive\manage.py shell
# from django.contrib.contenttypes.models import ContentType
# ContentType.objects.all().delete()
# django loaddata bin\utilities\wholedb.json
