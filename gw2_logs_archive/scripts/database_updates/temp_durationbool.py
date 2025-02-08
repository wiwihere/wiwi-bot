# %%
if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)

# from django.conf import settings
from gw2_logs.models import DpsLog, Encounter, InstanceClearGroup
from scripts.log_instance_interaction import InstanceClearGroupInteraction

# %%
for obj in Encounter.objects.all():
    if obj.leaderboard_instance_group is not None:
        print(f"{obj.id} {obj.name}")

        obj.use_for_icg_duration = True
        obj.save()


# %% add duration_encounters to icg
for obj in InstanceClearGroup.objects.filter(type="raid", start_time__lte="2024-11-15 00:00:00").order_by(
    "start_time"
):
    # if obj.duration_encounters is None:
    print(f"{obj.id} {obj.name}")

    # obj.duration_encounters = "1_1__1_2__1_3__2_1__2_2__2_3__3_1__3_2__3_3__3_4__4_1__4_2__4_3__4_4__5_1__5_2__5_3__5_4__5_5__5_6__6_1__6_2__6_3__7_1__7_2__7_3"
    # obj.save()

    InstanceClearGroupInteraction.from_name(obj.name)


# %% add duration_encounters to icg
for obj in InstanceClearGroup.objects.filter(type="strike").order_by("-start_time"):
    # if obj.duration_encounters is None:
    if "cerus" not in obj.name:
        print(f"{obj.id} {obj.name}")

        # obj.duration_encounters = "3_1__3_2__3_3__3_5__4_1__4_2"
        # obj.save()

        InstanceClearGroupInteraction.from_name(obj.name)
        # break


# %% set CerusCM fails to not leaderboard
for obj in DpsLog.objects.filter(boss_name="Cerus", cm=True):
    if obj.success:
        print(f"{obj.id} {obj.boss_name}")
        obj.use_in_leaderboard = True
        # obj.save()
