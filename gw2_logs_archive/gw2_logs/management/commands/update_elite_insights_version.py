# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging

from django.core.management.base import BaseCommand
from scripts.log_processing.ei_parser import EliteInsightsParser

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Update elite insights parser"

    def handle(self, *args, **options):
        EliteInsightsParser(auto_update=True, auto_update_check=False)
