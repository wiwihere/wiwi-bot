# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

from django.core.management.base import BaseCommand
from scripts.runners.run_leaderboard import run_leaderboard


class Command(BaseCommand):
    help = "Update leaderboards on discord"

    def handle(self, *args, **options):
        for instance_type in [
            "raid",
            "strike",
            "fractal",
        ]:
            run_leaderboard(instance_type=instance_type)


from scripts.runners.run_leaderboard import run_leaderboard

run_leaderboard(instance_type=instance_type)
