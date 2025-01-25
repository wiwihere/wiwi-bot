# %%
if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)


from pathlib import Path

from django.core.management.base import BaseCommand
from scripts import log_uploader

# class Command(BaseCommand):
#     help = "Upload from urls. These need to be pasted into bin/urls.txt"

#     def handle(self, *args, **options):
if True:
    if True:
        log_urls = Path(r"../bin/urls.txt").read_text()
        log_urls = log_urls.split(";")
        log_urls = [u.split("\n") for u in log_urls]

        print(log_urls)


# for log_url in log_urls:
#     self = log_upload = log_uploader.LogUploader.from_url(log_url=log_url)
#     log_upload.run()
