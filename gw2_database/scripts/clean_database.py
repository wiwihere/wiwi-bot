# %%
"""Dangerous! Only use if you wish to have a clean start."""
import shutil
import sys

from log_helpers import today_y_m_d

if __name__ == "__main__":
    # -- temp TESTING --
    sys.path.append("../../nbs")
    from django_for_jupyter import init_django_from_commands

    init_django_from_commands("gw2_database")
    # -- temp TESTING --

from gw2_logs.models import DpsLog, Guild, Instance, InstanceClear, InstanceClearGroup, Player

from gw2_database.gw2_database import settings as django_settings

res = input("Are you sure you want to clean your database? A copy will be made first. [y/n]")
if res == "y":
    res2 = input("Really? Type: delete all my clears")
    if res2 == "delete all my clears":
        y, m, d = today_y_m_d()
        backup_db = django_settings.DATABASES["default"]["NAME"].parent.joinpath(
            f"backups/db_{y}{str(m).zfill(2)}{str(d).zfill(2)}.sqlite3"
        )
        i = 0
        while backup_db.exists():
            backup_db = backup_db.with_name(f"db_{y}{str(m).zfill(2)}{str(d).zfill(2)}_{i}.sqlite3")
            i += 1

        shutil.copyfile(src=django_settings.DATABASES["default"]["NAME"], dst=backup_db)
        print(f"Created db backup @ {backup_db}")

        print("Deleting all: DpsLog")
        DpsLog.objects.all().delete()
        print("Deleting all: InstanceClear")
        InstanceClear.objects.all().delete()
        print("Deleting all: InstanceClearGroup")
        InstanceClearGroup.objects.all().delete()
        print("Deleting all: Player")
        Player.objects.all().delete()
        print("Deleting all: Guild")
        Guild.objects.all().delete()

        print("Deleting all: discord_leaderboard_message_id form Instance")
        for instance in Instance.objects.all():
            instance.discord_leaderboard_message_id = None
            instance.save()
