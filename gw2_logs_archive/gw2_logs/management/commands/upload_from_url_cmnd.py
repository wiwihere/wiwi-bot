# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging
from itertools import chain

from django.conf import settings
from django.core.management.base import BaseCommand
from scripts.log_processing.log_uploader import LogUploader

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Upload from urls. These need to be pasted into bin/urls.txt"

    def handle(self, *args, **options):
        # Read urls from txt file
        log_urls = settings.PROJECT_DIR.joinpath("bin", "urls.txt").read_text()
        log_urls = log_urls.split(";")
        log_urls = list(chain(*[u.split("\n") for u in log_urls]))
        logger.info("Processing urls from urls.txt")
        logger.info(log_urls)

        # Parse the urls
        for log_url in log_urls:
            if log_url != "":
                log_upload = LogUploader(log_url=log_url, only_url=False)
                log_upload.run()
