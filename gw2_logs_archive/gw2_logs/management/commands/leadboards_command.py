# %%
from django.core.management.base import BaseCommand
from scripts import leaderboards


class Command(BaseCommand):
    help = "Update leaderboards on discord"

    def handle(self, *args, **options):
        for itype in [
            "raid",
            "strike",
            "fractal",
        ]:
            leaderboards.create_leaderboard(itype=itype)
