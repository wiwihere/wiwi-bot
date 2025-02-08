# %%
if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)

# from django.conf import settings
from gw2_logs.models import Encounter

Encounter.objects.filter(use_for_icg_duration=True, icg_name="raid")

# %%
for obj in Encounter.objects.all():
    if obj.leaderboard_instance_group is not None:
        print(f"{obj.id} {obj.name}")

        obj.use_for_icg_duration = True
        obj.save()
