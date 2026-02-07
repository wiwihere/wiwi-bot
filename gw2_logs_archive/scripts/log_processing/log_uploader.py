# %%
"""Log uploader and dps.report client

This module contains helpers to upload local Elite Insights logfiles to
dps.report and to fetch metadata/detailed info. The `LogUploader` class is
responsible for coordinating uploads, metadata normalization, and delegating
creation/updating of `DpsLog` records to the `DpsLogService`.
"""

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import datetime
import json
import logging
import time
from dataclasses import dataclass
from functools import cached_property
from itertools import chain
from pathlib import Path
from typing import Literal, Optional, Tuple

import requests
from dateutil.parser import parse
from django.conf import settings
from gw2_logs.models import (
    DpsLog,
    Encounter,
)
from scripts.log_helpers import (
    create_unix_time,
    get_emboldened_wing,
    get_log_path_view,
)
from scripts.log_processing.ei_parser import EliteInsightsParser
from scripts.model_interactions.dpslog_service import DpsLogService
from scripts.utilities.failed_log_mover import move_failed_log
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


class DpsReportUploader:
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


@dataclass
class LogUploader:
    """Upload log to dps.report and save results in django database.
    Sometimes dps.report doesnt report correctly, will get detailed info then.
    Either provide a log_path or log_url.

    Parameters
    ----------
    log_path : (Path) default None
        Path to local log file
    log_url : (str) default None
        URL to dps.report log
    only_url : (bool) default False
        Only update the url, nothing else. We want this when log is already parsed locally.
    """

    log_path: Path = None
    log_url: str = None
    parsed_path: Path = None
    only_url: bool = False
    allow_reparse: bool = True

    def __post_init__(self):
        if self.log_path:
            self.log_path = Path(self.log_path)

        self.uploader = DpsReportUploader()
        self.dpslog_service = DpsLogService()

    @cached_property
    def detailed_metadata(self) -> Optional[DetailedParsedLog]:
        """Get detailed info from dps.report API. Dont request multiple times."""

        if self.parsed_path:
            detailed_parsed_log = DetailedParsedLog.from_ei_parsed_path(parsed_path=self.parsed_path)
        if self.log_url:
            detailed_parsed_log = self.uploader.request_detailed_info(url=self.log_url)
        return detailed_parsed_log

    @classmethod
    def from_log(cls, log: DpsLog):
        """log_file_view is a bit tricky. Initiate class from a DpsLog"""
        log_upload = cls(log_path=log.local_path)
        return log_upload

    @property
    def log_source_view(self) -> str:
        """Only show two parent folders if log is from path."""
        if self.log_path:
            return get_log_path_view(self.log_path)
        else:
            return str(self.log_url)

    def get_dps_log(self) -> Optional[DpsLog]:
        """Return DpsLog if its available in database."""
        if self.log_path:
            dpslog = self.dpslog_service.find_by_name(self.log_path)
            # Fallback: if not found, optionally try to (re)create from an EI parsed file
            if not dpslog and self.allow_reparse and self.parsed_path:
                logger.warning("Log not found in database by name, trying by start time via parsed file")
                parsed_log = DetailedParsedLog.from_ei_parsed_path(parsed_path=self.parsed_path)
                dpslog = self.dpslog_service.get_update_create_from_ei_parsed_log(
                    parsed_log=parsed_log, log_path=self.log_path
                )
            return dpslog
        if self.log_url:
            return self.dpslog_service.get_by_url(self.log_url)
        return None

    def get_or_upload_log(self) -> Tuple[Optional[MetadataParsed], Literal["failed", "forbidden", None]]:
        """Get log from database, if not there, upload it.
        If there is a reason to move the log, return that too.
        """

        self.dps_log = self.get_dps_log()

        has_log_path = self.log_path is not None
        has_dps_log = self.dps_log is not None
        has_log_url = self.log_url is not None

        should_upload = has_log_path and (
            not has_dps_log  # no DB record yet
            or not has_log_url  # DB record exists but not uploaded
        )

        metadata = None
        move_reason = None

        if should_upload:
            logger.info(f"{self.log_source_view}: Uploading log")
            metadata, move_reason = self.uploader.upload_log(log_path=self.log_path)

        elif has_log_url:
            metadata = self.uploader.request_metadata(url=self.log_url)

        elif has_dps_log:
            # existing DB record stores raw JSON; wrap in MetadataParsed for consistency
            raw = getattr(self.dps_log, "json_dump", None)
            metadata = MetadataParsed(raw) if raw else None

        return metadata, move_reason

    def run(self) -> Optional[DpsLog]:
        """Get or upload the log and add to database. Some conditions apply for logs to be valid.
        If they do not apply, move the log to forbidden or failed folder.

        Returns
        -------
        None on fail
        DpsLog.object on success
        """
        logger.info(f"{self.log_source_view}: Start processing")
        metadata, move_reason = self.get_or_upload_log()

        if move_reason:
            move_failed_log(self.log_path, move_reason)

        if metadata is None:
            logger.debug("    No valid metadata received")
            return None

        metadata.apply_boss_fixes()
        metadata.apply_metadata_fix()

        metadata_dict = metadata.as_dict()

        if self.only_url:
            # Just update the url, skip all further processing and fixes (since it is already done with the ei_parser)
            if self.dps_log:
                dpslog = self.dpslog_service.update_permalink(self.dps_log, metadata_dict["permalink"])
            else:
                logger.warning("Trying to update url, but log not found in database, this shouldnt happen")
                dpslog = self.dpslog_service.create_or_update_from_dps_report_metadata(
                    metadata=metadata_dict, log_path=self.log_path, url_only=True
                )

        else:
            dpslog = self.dpslog_service.create_or_update_from_dps_report_metadata(
                metadata=metadata_dict, log_path=self.log_path
            )

            dpslog, move_reason = self.dpslog_service.fix_final_health_percentage(
                dpslog=dpslog, detailed_info=self.detailed_metadata
            )
            if move_reason:
                move_failed_log(self.log_path, move_reason)
                self.dpslog_service.delete(dpslog)

            self.dpslog_service.fix_emboldened(dpslog=dpslog, detailed_info=self.detailed_metadata)

        logger.info(f"Finished processing: {self.log_source_view}")

        return dpslog


if __name__ == "__main__":
    log_path = settings.DPS_LOGS_DIR.joinpath(r"Standard Kitty Golem (16199)\...zevtc")
    self = LogUploader(log_path=log_path)

    # self.uploader.upload_log(log_path)
