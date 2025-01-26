# %%
from django.core.management.base import BaseCommand

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)
import scripts.leaderboards as leaderboards


class Command(BaseCommand):
    help = "Update leaderboards on discord"

    def handle(self, *args, **options):
        for itype in [
            "raid",
            "strike",
            "fractal",
        ]:
            leaderboards.create_leaderboard(itype=itype)
