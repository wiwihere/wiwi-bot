# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import json
import logging
import time
from dataclasses import dataclass
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
from scripts.model_interactions.dpslog_service import DpsLogService
from scripts.utilities.failed_log_mover import move_failed_log
from scripts.utilities.parsed_log import ParsedLog

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

    def upload_log(self, log_path: Path) -> Tuple[Optional[dict], Literal["failed", "forbidden", None]]:
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
            return response.json(), None

        else:
            logger.error(f"Code {response.status_code}: Failed uploading {get_log_path_view(log_path)}")
            logger.error(f"Reason: {response.reason}")

        if response.status_code == 503:
            if hasattr(response, "error"):
                logger.error(f"{response.error}")
            return None, None

        elif response.status_code == 403:
            move_reason = None
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

        return None, None

    def request_metadata(self, report_id=None, url=None) -> Optional[dict]:
        """Get metadata from dps.report if an url is available. Either provide report_id or url."""
        data = {"id": report_id, "permalink": url}
        response = requests.get(self.endpoints.metadata, params=data)

        if response.status_code != 200:
            logger.error(f"Code {response.status_code}: Failed retrieving log {url}")
            return None
        return response.json()

    def request_detailed_info(self, report_id: Optional[str] = None, url: Optional[str] = None) -> Optional[dict]:
        """Upload can have corrupt metadata. We then have to request the detailed log info.
        More info of the output can be found here: https://baaron4.github.io/GW2-Elite-Insights-Parser/Json/index.html
        """
        data = {"id": report_id, "permalink": url}
        detailed_response = requests.get(self.endpoints.detailed_metadata, params=data)
        if detailed_response.status_code != 200:
            logger.error(f"Code {detailed_response.status_code}: Failed retrieving log {url}")
            return None
        return detailed_response.json()


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

    def __post_init__(self):
        if self.log_path:
            self.log_path = Path(self.log_path)
        self._detailed_info: dict | None = None  # Detailed api response

        self.uploader = DpsReportUploader()
        self.dpslog_service = DpsLogService()

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

    def get_detailed_info(self, report_id: str = None, url: str = None) -> dict:
        """Get detailed info from dps.report API. Dont request multiple times."""
        if self._detailed_info is None:
            self._detailed_info = self.uploader.request_detailed_info(report_id=report_id, url=url)

        return self._detailed_info

    def get_detailed_info_from_log(self, log: DpsLog) -> dict:
        """Get detailed info from dps.report API. Dont request multiple times."""
        report_id = log.report_id
        url = log.url
        _detailed_info = self.get_detailed_info(report_id=report_id, url=url)
        return _detailed_info

    def get_dps_log(self) -> Optional[DpsLog]:
        """Return DpsLog if its available in database."""

        if self.log_path:
            # TODO  this shouldnt happen here.
            dps_log = self.dpslog_service.find_by_name(self.log_path)
            if not dps_log:
                logger.warning(
                    "Log not found in database by name, trying by start time, this happens when someone else parsed it"
                )
                parsed_log = ParsedLog.from_ei_parsed_path(parsed_path=self.parsed_path)
                dpslog = self.dpslog_service.create_from_ei(parsed_log=parsed_log, log_path=self.log_path)
            return dpslog
        if self.log_url:
            return DpsLog.objects.filter(url=self.log_url).first()

    def get_or_upload_log(self) -> Tuple[Optional[dict], Literal["failed", "forbidden", None]]:
        """Get log from database, if not there, upload it.
        If there is a reason to move the log, return that too.
        """

        move_reason = None
        self.dps_log = self.get_dps_log()  # FIXME this is terrible
        if self.dps_log:
            if self.log_path:
                if not self.log_url:
                    logger.info(f"{self.log_source_view}: Uploading log")
                    response, move_reason = self.uploader.upload_log(log_path=self.log_path)

            # if self.log_url:
            #     logger.info("    Requesting info from url")
            #     response = self.uploader.request_metadata(url=self.log_url)
        else:
            logger.info("Already in database?")
            response = self.get_dps_log().first().json_dump
        return response, move_reason

    def fix_bosses(self, metadata: dict) -> dict:
        """Change raw results a bit to assign logs to the correct Encounter."""

        if metadata["encounter"]["boss"] == "Ai":
            # Dark and light Ai have the same boss id. This doesnt work in the database.
            # fightName in detailed logs do names as below, so we can look them up
            # 'Dark Ai, Keeper of the Peak'
            # 'Elemental Ai, Keeper of the Peak'
            logger.info("Fixing Ai boss name")
            _detailed_info = self.get_detailed_info(report_id=metadata["id"])
            metadata["encounter"]["boss"] = _detailed_info["fightName"].split(",")[0]
            # Dark to different bossid so it gives separate log
            if metadata["encounter"]["boss"] == "Dark Ai":
                metadata["encounter"]["bossId"] = -23254

        if metadata["encounter"]["bossId"] in [25413, 25423, 25416]:
            # OLC has different bossId's. We map all logs to one.
            metadata["encounter"]["bossId"] = 25414

        if metadata["encounter"]["boss"] == "Eye of Judgement":
            metadata["encounter"]["boss"] = "Eye of Fate"
            metadata["encounter"]["bossId"] = 19844

        return metadata

    @staticmethod
    def get_encounter(metadata: dict) -> Optional[Encounter]:
        try:
            encounter = Encounter.objects.get(dpsreport_boss_id=metadata["encounter"]["bossId"])
        except Encounter.DoesNotExist:
            encounter = None
            logger.critical(
                f"""
Encounter not part of database. Register? {metadata["encounter"]}
bossId:  {metadata["encounter"]["bossId"]}
bossname:  {metadata["encounter"]["boss"]}

"""
            )
            if settings.DEBUG:
                raise Encounter.DoesNotExist
        return encounter

    def fix_metadata(self, metadata: dict) -> dict:
        """
        Check wrong metadata, sometimes the normal json response has empty
        or plain wrong data. This has to do with some memory issues on dps.report.
        Can be fixed by requesting the detailed info.
        Still relevant when only requesting url because start time can be off
        """
        if datetime.timedelta(seconds=metadata["encounter"]["duration"]).seconds == 0:
            logger.info(f"Log seems broken. Requesting more info {self.log_source_view}")

            self._detailed_info = self.get_detailed_info(report_id=metadata["id"])
            # r2["timeStart"] format is '2023-12-18 14:07:57 -05'
            start_time = parse(self._detailed_info["timeStart"]).astimezone(datetime.timezone.utc)

            metadata["encounter"]["duration"] = self._detailed_info["durationMS"] / 1000
            metadata["encounter"]["isCm"] = self._detailed_info["isCM"]
            metadata["encounterTime"] = create_unix_time(start_time)
        return metadata

    def fix_final_health_percentage(self, log: DpsLog) -> Tuple[Optional[DpsLog], Literal["failed", None]]:
        """Update final health percentage"""
        # TODO this is a duplicate of dps_log.py
        if log.final_health_percentage is None:
            if log.success is False:
                logger.info("    Requesting final boss health")
                self._detailed_info = self.get_detailed_info_from_log(log=log)
                log.final_health_percentage = round(100 - self._detailed_info["targets"][0]["healthPercentBurned"], 2)

                # Sometimes people get in combat at eyes which creates an uneccesary log.
                if log.final_health_percentage == 100.0 and log.boss_name == "Eye of Fate":
                    move_reason = "failed"

                    return None, move_reason

            else:
                log.final_health_percentage = 0
            log.save()
        return log, None

    def fix_emboldened(self, log: DpsLog) -> DpsLog:
        """Legacy code. Older dps.report response didnt include the emboldened status.
        Check emboldened

        """
        if (log.emboldened is None) and (log.encounter is not None):
            emboldened_wing = get_emboldened_wing(log.start_time)
            if (
                (emboldened_wing == log.encounter.instance.nr)
                and (log.encounter.instance.instance_group.name == "raid")
                and not (log.cm)
            ):
                logger.info("    Checking for emboldened")
                self._detailed_info = self.get_detailed_info_from_log(log=log)

                if "presentInstanceBuffs" in self._detailed_info:
                    log.emboldened = 68087 in list(chain(*self._detailed_info["presentInstanceBuffs"]))
                else:
                    log.emboldened = False
            else:
                log.emboldened = False

            log.save()
        return log

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

        metadata = self.fix_bosses(metadata=metadata)

        encounter = self.get_encounter(metadata=metadata)

        # Fix metadata is response is incorrect
        metadata = self.fix_metadata(metadata=metadata)

        if self.only_url:
            # Just update the url, skip all further processing and fixes (since it is already done with the ei_parser)
            if self.dps_log:
                if self.dps_log.url != metadata["permalink"]:
                    self.dps_log.url = metadata["permalink"]
                    self.dps_log.save()
                log = self.dps_log
            else:
                log, created = DpsLog.objects.update_or_create(
                    defaults={
                        "url": metadata["permalink"],
                    },
                    # rresponse["encounterTime"] format is 1702926477
                    start_time=datetime.datetime.fromtimestamp(metadata["encounterTime"], tz=datetime.timezone.utc),
                )
                # TODO starttime doesnt work when someone else parses it.

        else:
            log = self.dpslog_service.create_or_update_from_dps_report(metadata=metadata, log_path=self.log_path)

            log, move_reason = self.fix_final_health_percentage(log=log)
            if move_reason:
                move_failed_log(self.log_path, move_reason)
                log.delete()

            self.fix_emboldened(log=log)

        logger.info(f"Finished processing: {self.log_source_view}")

        return log


if __name__ == "__main__":
    log_path = settings.DPS_LOGS_DIR.joinpath(r"Standard Kitty Golem (16199)\...zevtc")
    self = LogUploader(log_path=log_path)

    # self.uploader.upload_log(log_path)
