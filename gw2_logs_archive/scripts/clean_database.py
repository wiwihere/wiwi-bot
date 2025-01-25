# %%
"""Dangerous! Only use if you wish to have a clean start."""

import shutil
import sqlite3
import sys

if __name__ == "__main__":
    from django_for_jupyter import init_django_from_commands

    init_django_from_commands("gw2_logs_archive")

from gw2_logs.models import DpsLog, Instance, InstanceClear, InstanceClearGroup, Player
from scripts.log_helpers import today_y_m_d

from gw2_logs_archive.bot_settings import settings as django_settings

res = input("Are you sure you want to clean your database? A copy will be made first. [y/n]")
if res == "y":
    res2 = input("Really? Type: delete all my clears")
    if res2 == "delete all my clears":
        y, m, d = today_y_m_d()
        django_db = django_settings.DATABASES["default"]["NAME"]
        backup_db = django_settings.PROJECT_DIR.joinpath(
            "data", "db_backups", f"db_{y}{str(m).zfill(2)}{str(d).zfill(2)}.sqlite3"
        )
        i = 0
        while backup_db.exists():
            backup_db = backup_db.with_name(f"db_{y}{str(m).zfill(2)}{str(d).zfill(2)}_{i}.sqlite3")
            i += 1

        shutil.copyfile(src=django_db, dst=backup_db)
        print(f"Created db backup @ {backup_db}")

        print("Deleting all: DpsLog")
        DpsLog.objects.all().delete()
        print("Deleting all: InstanceClear")
        InstanceClear.objects.all().delete()
        print("Deleting all: InstanceClearGroup")
        InstanceClearGroup.objects.all().delete()
        print("Deleting all: Player")
        Player.objects.all().delete()

        print("Deleting all: discord_leaderboard_message_id from Instance")
        for instance in Instance.objects.all():
            instance.discord_leaderboard_message_id = None
            instance.save()

        # Vacuum the database to reduce file size
        conn = sqlite3.connect(django_db)
        conn.execute("VACUUM")
        conn.close()
