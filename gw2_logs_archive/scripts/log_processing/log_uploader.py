# %%

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import json
import logging
import shutil
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
    Player,
)
from scripts.log_helpers import (
    create_unix_time,
    get_emboldened_wing,
    today_y_m_d,
    zfill_y_m_d,
)

logger = logging.getLogger(__name__)


def get_log_path_view(log_path: Path, parents: int = 2) -> str:
    """Only show two parent folders of path."""
    parents = min(len(log_path.parts) - 2, parents)  # avoids index-error
    return log_path.as_posix().split(log_path.parents[parents].as_posix(), maxsplit=1)[-1]


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
        """Get metadata from dps.report if an url is available."""
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
    """

    log_path: Path = None
    log_url: str = None
    only_url: bool = False

    def __post_init__(self):
        if self.log_path:
            self.log_path = Path(self.log_path).as_posix()

        self.log: DpsLog | None = None  # DpsLog instance
        self.r: dict | None = None  # Normal api response
        self._detailed_info: dict | None = None  # Detailed api response

        self.uploader = DpsReportUploader()

    @classmethod
    def from_path(cls, log_path: Path, only_url=False):
        """Get the log from a local file

        only_url : (bool) default False
            only update the url, nothing else. We want this when log is already parsed locally.
        """
        return cls(log_path=log_path, only_url=only_url)

    @classmethod
    def from_url(cls, log_url, only_url=False):
        """If log already uploaded can also get it from an url"""
        return cls(log_url=str(log_url), only_url=only_url)

    @classmethod
    def from_log(cls, log: DpsLog):
        """log_file_view is a bit tricky. Initiate class from a DpsLog"""
        log_upload = cls(log_path=log.local_path)
        log_upload.log = log
        return log_upload

    @property
    def log_source(self) -> str:
        if self.log_path:
            return str(self.log_path)
        if self.log_url:
            return str(self.log_url)

    @property
    def log_source_view(self) -> str:
        """Only show two parent folders if log is from path."""
        if self.log_path:
            return get_log_path_view(self.log_path)
        return self.log_source

    def get_detailed_info(self, report_id: str = None, url: str = None) -> dict:
        if self._detailed_info is None:
            self._detailed_info = self.uploader.request_detailed_info(report_id=report_id, url=url)

        return self._detailed_info

    def get_detailed_info_from_log(self, log: DpsLog) -> dict:
        report_id = log.report_id
        url = log.url
        _detailed_info = self.get_detailed_info(report_id=report_id, url=url)
        return _detailed_info

    def move_forbidden_or_failed_upload(self, move_reason: Literal["failed", "forbidden"]) -> None:
        """The API throws exceptions regularly. Upload these by hand ;("""  # noqa
        if move_reason == "failed":
            # Some logs are just broken. Lets remove them from the equation
            out_path = settings.DPS_LOGS_DIR.parent.joinpath("failed_logs", Path(self.log_path).name)
        elif move_reason == "forbidden":
            # The API may throw exceptions. Upload these by hand ;(
            out_path = settings.DPS_LOGS_DIR.parent.joinpath(
                "forbidden_logs", zfill_y_m_d(*today_y_m_d()), Path(self.log_path).name
            )
        logger.warning(f"Moved {move_reason} log from {self.log_source_view} to\n{out_path}")

        shutil.move(src=self.log_path, dst=out_path)

    def get_django_log(self) -> DpsLog:
        """Return queryset with DpsLogs"""
        return DpsLog.objects.filter(local_path=self.log_source)

    def get_or_upload_log(self) -> Optional[dict]:
        """Get log from database, if not there, upload it."""

        if len(self.get_django_log()) == 0:
            logger.info("    Uploading log")
            if self.log_path:
                response, move_reason = self.upload_log()
                if move_reason:
                    self.move_forbidden_or_failed_upload(move_reason=move_reason)
                    return False

            if self.log_url:
                r = self.request_metadata(url=self.log_url)
        else:
            logger.info("    Already in database")
            r = self.get_django_log().first().json_dump
        return r

    def fix_bosses(self, r: dict) -> dict:
        """Change raw results a bit to assign logs to the correct Encounter."""

        if r["encounter"]["boss"] == "Ai":
            # Dark and light Ai have the same boss id. This doesnt work in the database.
            # fightName in detailed logs do names as below, so we can look them up
            # 'Dark Ai, Keeper of the Peak'
            # 'Elemental Ai, Keeper of the Peak'
            logger.info("    Fixing Ai boss name")
            _detailed_info = self.get_detailed_info(report_id=r["id"], url=r["permalink"])
            r["encounter"]["boss"] = _detailed_info["fightName"].split(",")[0]
            # Dark to different bossid so it gives separate log
            if r["encounter"]["boss"] == "Dark Ai":
                r["encounter"]["bossId"] = -23254

        if r["encounter"]["bossId"] in [25413, 25423, 25416]:
            # OLC has different bossId's. We map all logs to one.
            r["encounter"]["bossId"] = 25414

        if r["encounter"]["boss"] == "Eye of Judgement":
            r["encounter"]["boss"] = "Eye of Fate"
            r["encounter"]["bossId"] = 19844

        return r

    def run(self):
        """Get or upload the log and add to database

        Returns
        -------
        False on fail
        DpsLog.object on success
        """
        logger.info(f"Start processing: {self.log_source_view}")
        self.r = r = self.get_or_upload_log()

        if r is False:
            return False

        r = self.fix_bosses(r)

        try:
            encounter = Encounter.objects.get(dpsreport_boss_id=r["encounter"]["bossId"])
        except Encounter.DoesNotExist:
            encounter = None
            # jank way of making error known to user.
            logger.error(
                f"""
Encounter not part of database. Register? {r["encounter"]}
bossId:  {r["encounter"]["bossId"]}
bossname:  {r["encounter"]["boss"]}

"""
            )
            if settings.DEBUG:
                raise Encounter.DoesNotExist

        # Check wrong metadata, sometimes the normal json response has empty
        # or plain wrong data. This has to do with some memory issues on b.dps.report.
        # Can be fixed by requesting the detailed info.
        # Still relevant when only requesting url because start time can be off
        if datetime.timedelta(seconds=r["encounter"]["duration"]).seconds == 0:
            logger.info(f"Log seems broken. Requesting more info {self.log_source_view}")

            self._detailed_info = r2 = self.get_detailed_info(report_id=r["id"], url=r["permalink"])
            # r2["timeStart"] format is '2023-12-18 14:07:57 -05'
            start_time = parse(self._detailed_info["timeStart"]).astimezone(datetime.timezone.utc)

            r["encounter"]["duration"] = self._detailed_info["durationMS"] / 1000
            r["encounter"]["isCm"] = self._detailed_info["isCM"]
            r["encounterTime"] = create_unix_time(start_time)

        if not self.only_url:
            # Arcdps error 'File had invalid agents. Please update arcdps' would return some
            # empty jsons. This makes sure the log is still processed
            if self.r["players"] != []:
                players = [i["display_name"] for i in r["players"].values()]
            else:
                players = []

            self.log, created = log, created = DpsLog.objects.update_or_create(
                defaults={
                    "encounter": encounter,
                    "success": r["encounter"]["success"],
                    "duration": datetime.timedelta(seconds=r["encounter"]["duration"]),
                    "url": r["permalink"],
                    "player_count": r["encounter"]["numberOfPlayers"],
                    "boss_name": r["encounter"]["boss"],
                    "cm": r["encounter"]["isCm"],
                    "gw2_build": r["encounter"]["gw2Build"],
                    "players": players,
                    "core_player_count": len(Player.objects.filter(gw2_id__in=players, role="core")),
                    "friend_player_count": len(Player.objects.filter(gw2_id__in=players, role="friend")),
                    "report_id": r["id"],
                    "local_path": self.log_source,
                    "json_dump": r,
                },
                # r["encounterTime"] format is 1702926477
                start_time=datetime.datetime.fromtimestamp(r["encounterTime"], tz=datetime.timezone.utc),
            )

            # Update final health percentage
            if log.final_health_percentage is None:
                if log.success is False:
                    logger.info("    Requesting final boss health")
                    self._detailed_info = r2 = self.get_detailed_info_from_log(log=log)
                    log.final_health_percentage = round(100 - r2["targets"][0]["healthPercentBurned"], 2)

                    # Sometimes people get in combat at eyes which creates an uneccesary log.
                    if log.final_health_percentage == 100.0 and self.r["encounter"]["boss"] == "Eye of Fate":
                        self.move_forbidden_or_failed_upload(move_reason="failed")
                        log.delete()
                        return False

                else:
                    log.final_health_percentage = 0
                log.save()

            # Check emboldened
            if (log.emboldened is None) and (log.encounter is not None):
                emboldened_wing = get_emboldened_wing(log.start_time)
                if (
                    (emboldened_wing == log.encounter.instance.nr)
                    and (log.encounter.instance.instance_group.name == "raid")
                    and not (log.cm)
                ):
                    logger.info("    Checking for emboldened")
                    self._detailed_info = r2 = self.request_detailed_info()
                    if "presentInstanceBuffs" in r2:
                        log.emboldened = 68087 in list(chain(*r2["presentInstanceBuffs"]))
                    else:
                        log.emboldened = False
                else:
                    log.emboldened = False

                log.save()

        else:
            self.log, created = log, created = DpsLog.objects.update_or_create(
                defaults={
                    "url": r["permalink"],
                },
                # r["encounterTime"] format is 1702926477
                start_time=datetime.datetime.fromtimestamp(r["encounterTime"], tz=datetime.timezone.utc),
            )

        logger.info(f"Finished processing: {self.log_source_view}")

        return log
