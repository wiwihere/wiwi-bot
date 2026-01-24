# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import scripts.leaderboards as leaderboards
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Update leaderboards on discord"

    def handle(self, *args, **options):
        for itype in [
            "raid",
            "strike",
            "fractal",
        ]:
            leaderboards.create_leaderboard(itype=itype)
