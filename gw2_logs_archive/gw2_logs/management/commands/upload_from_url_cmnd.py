from itertools import chain
from pathlib import Path

from django.core.management.base import BaseCommand
from scripts import log_uploader


class Command(BaseCommand):
    help = "Upload from urls. These need to be pasted into bin/urls.txt"

    def handle(self, *args, **options):
        # Read urls from txt file
        log_urls = Path(r"bin/urls.txt").read_text()
        log_urls = log_urls.split(";")
        log_urls = list(chain(*[u.split("\n") for u in log_urls]))
        print(log_urls)

        # Parse the urls
        for log_url in log_urls:
            if log_url != "":
                self = log_upload = log_uploader.LogUploader.from_url(log_url=log_url)
                log_upload.run()
