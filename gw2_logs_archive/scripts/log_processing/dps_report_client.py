# %%
"""dps.report client

This module contains helpers to upload local Elite Insights logfiles to
dps.report and to fetch metadata/detailed info.

"""

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import json
import logging
import time
from pathlib import Path
from typing import Literal, Optional, Tuple

import requests
from django.conf import settings
from scripts.log_helpers import (
    get_log_path_view,
)
from scripts.utilities.metadata_parsed import MetadataParsed
from scripts.utilities.parsed_log import DetailedParsedLog

logger = logging.getLogger(__name__)


class DpsReportEndpoints:
    """Endpoints for dps.report uploads and metadata requests."""

    def __init__(self, base_url: str = "https://dps.report/"):
        if not base_url.endswith("/"):
            base_url += "/"
        self.base = base_url
        self.upload = self.base + "uploadContent"
        self.metadata = self.base + "getUploadMetadata"
        self.detailed_metadata = self.base + "getJson"


class DpsReportClient:
    """Upload logs to dps.report and request metadata.
    Uploads can be done with a path to a local log file.
    Metadata can be requested with either a report_id or the dps.report url.
    """

    def __init__(self):
        self.endpoints = DpsReportEndpoints()

    def upload_log(self, log_path: Path) -> Tuple[Optional[MetadataParsed], Literal["failed", "forbidden", None]]:
        """Upload log to dps.report, a.dps.report or b.dps.report"""

        data = {
            "json": 1,
            "generator": "ei",
            "userToken": settings.DPS_REPORT_USERTOKEN,
            "anonymous": False,
            "detailedwvw": False,
        }
        with open(log_path, "rb") as f:
            files = {"file": f}

            time.sleep(1)  # To avoid hitting rate limits
            response = requests.post(self.endpoints.upload, files=files, data=data)

        if response.status_code == 200:  # All good
            metadata = response.json()
            return MetadataParsed(data=metadata), None

        else:
            logger.error(f"Code {response.status_code}: Failed uploading {get_log_path_view(log_path)}")
            logger.error(f"Reason: {response.reason}")

        move_reason = None
        if response.status_code == 503:
            if hasattr(response, "error"):
                logger.error(f"{response.error}")

        elif response.status_code == 403:
            try:
                logger.error(response.json().get("error"))

                # Move perma fail upload so it wont bother us again.
                if response.json()["error"] == "Encounter is too short for a useful report to be made":
                    move_reason = "failed"
                    # TODO maybe get this from the reason?

            except json.decoder.JSONDecodeError:
                pass

            if str(response.reason) == "Forbidden":
                move_reason = "forbidden"

        return None, move_reason

    def request_metadata(self, report_id: Optional[str] = None, url: Optional[str] = None) -> Optional[MetadataParsed]:
        """Get metadata from dps.report if an url is available. Either provide report_id or url."""
        data = {"id": report_id, "permalink": url}
        response = requests.get(self.endpoints.metadata, params=data)

        if response.status_code != 200:
            logger.error(f"Code {response.status_code}: Failed retrieving log {url}")
            return None
        metadata = response.json()
        return MetadataParsed(data=metadata)

    def request_detailed_info(
        self, report_id: Optional[str] = None, url: Optional[str] = None
    ) -> Optional[DetailedParsedLog]:
        """Upload can have corrupt metadata. We then have to request the detailed log info.
        More info of the output can be found here: https://baaron4.github.io/GW2-Elite-Insights-Parser/Json/index.html
        """
        data = {"id": report_id, "permalink": url}
        detailed_response = requests.get(self.endpoints.detailed_metadata, params=data)
        if detailed_response.status_code != 200:
            logger.error(f"Code {detailed_response.status_code}: Failed retrieving log {url}")
            return None
        return DetailedParsedLog(detailed_response.json())
