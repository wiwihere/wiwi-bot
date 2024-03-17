# %%
import datetime
import json
import shutil
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

import requests
from dateutil.parser import parse

if __name__ == "__main__":
    from django_for_jupyter import init_django_from_commands

    init_django_from_commands("gw2_database")
from bot_settings import settings
from gw2_logs.models import DpsLog, Emoji, Encounter, Instance, InstanceClear, InstanceClearGroup, Player
from scripts.log_helpers import (
    create_unix_time,
    get_emboldened_wing,
)


@dataclass
class LogUploader:
    """Upload log to dps.report and save results in django database.
    Sometimes dps.report doesnt report correctly, will get detailed info then.
    """

    log_path: str = None
    log_url: str = None

    def __post_init__(self):
        if self.log_path:
            self.log_path = Path(self.log_path).as_posix()

        self.log = None  # DpsLog instance
        self.r = None  # Normal api response
        self.r2 = None  # Detailed api response

    @classmethod
    def from_path(cls, log_path):
        """Get the log from a local file"""
        return cls(log_path=log_path)

    @classmethod
    def from_url(cls, log_url):
        """If log already uploaded can also get it from an url"""
        return cls(log_url=str(log_url))

    @classmethod
    def from_log(cls, log: DpsLog):
        """log_file_view is a bit tricky. Initiate class from a DpsLog"""
        log_upload = cls(log_path=log.local_path)
        log_upload.log = log
        return log_upload

    @property
    def log_source(self):
        if self.log_path:
            return str(self.log_path)
        if self.log_url:
            return str(self.log_url)

    @property
    def log_source_view(self):
        """Only show two parent folders if log is from path."""
        if self.log_path:
            log_path = Path(self.log_path)
            parents = 2
            parents = min(len(log_path.parts) - 2, parents)  # avoids index-error
            return log_path.as_posix().split(log_path.parents[parents].as_posix(), maxsplit=1)[-1]
        return self.log_source

    def upload_log(self):
        """Upload log to dps.report"""
        base_url = "https://dps.report/uploadContent"

        data = {
            "json": 1,
            "generator": "ei",
            "userToken": settings.DPS_REPORT_USERTOKEN,
            "anonymous": False,
            "detailedwvw": False,
        }
        with open(self.log_path, "rb") as f:
            files = {"file": f}

            self.r_raw = r = requests.post(base_url, files=files, data=data)

        if r.status_code == 503:
            print(f"ERROR 503: Failed uploading {self.log_source_view}")
            return False
        if r.status_code == 403:
            print(f"ERROR 403: Failed uploading {self.log_source_view}")
            try:
                print(r.json()["error"])

                # Move perma fail upload so it wont bother us again.
                if r.json()["error"] == "Encounter is too short for a useful report to be made":
                    self.move_failed_upload()
            except json.decoder.JSONDecodeError:
                pass

            return False

        if hasattr(r, "status_code"):
            if r.status_code == 200:
                return r.json()
        print(f"ERROR: Failed uploading log for unknown reason {self.log_source_view}")
        return False

    def move_failed_upload(self):
        """Some logs are just broken. Lets remove them from the equation"""  # noqa
        out_path = Path(settings.DPS_LOGS_DIR).parent.joinpath("failed_logs", Path(self.log_path).name)
        out_path.parent.mkdir(exist_ok=True)
        print(f"Moved failing log from {self.log_source_view} to")
        print(out_path)
        shutil.move(src=self.log_path, dst=out_path)

    def request_metadata(self, report_id=None, url=None):
        """Get metadata from dps.report if an url is available."""
        json_url = "https://dps.report/getUploadMetadata"
        data = {"id": report_id, "permalink": url}
        self.r = r = requests.get(json_url, params=data)

        if r.status_code != 200:
            print(f"ERROR: Failed retrieving log {self.log_url}")
            return False
        return r.json()

    def request_detailed_info(self, report_id=None, url=None):
        """Upload can have corrupt metadata. We then have to request the fill log info.
        More info of the output can be found here: https://baaron4.github.io/GW2-Elite-Insights-Parser/Json
        """
        # Dont have to request info twice.
        if self.r2 is not None:
            return self.r2

        # Get url and report_id from DpsLog instance.
        if report_id is None:
            if self.log is None:
                self.log = self.get_django_log().first()
            report_id = self.log.report_id
            url = self.log.url

        json_url = "https://dps.report/getJson"
        data = {"id": report_id, "permalink": url}
        r2 = requests.get(json_url, params=data)
        return r2.json()

    def get_django_log(self):
        """Return queryset with DpsLogs"""
        return DpsLog.objects.filter(local_path=self.log_source)

    def get_or_upload_log(self):
        """Get log from database, if not there, upload it."""

        if len(self.get_django_log()) == 0:
            print("    Uploading log")
            if self.log_path:
                r = self.upload_log()
            if self.log_url:
                r = self.request_metadata(url=self.log_url)
        else:
            print("    Already in database")
            r = self.get_django_log().first().json_dump
        return r

    def fix_bosses(self, r):
        """Change raw results a bit to assign logs to the correct Encounter."""

        if r["encounter"]["boss"] == "Ai":
            # Dark and light Ai have the same boss id. This doesnt work in the database.
            # fightName in detailed logs do names as below, so we can look them up
            # 'Dark Ai, Keeper of the Peak'
            # 'Elemental Ai, Keeper of the Peak'
            print("    Fixing Ai boss name")
            self.r2 = r2 = self.request_detailed_info(report_id=r["id"], url=r["permalink"])
            r["encounter"]["boss"] = r2["fightName"].split(",")[0]
            # Dark to different bossid so it gives separate log
            if r["encounter"]["boss"] == "Dark Ai":
                r["encounter"]["bossId"] = -23254

        if r["encounter"]["bossId"] in [25413, 25423]:
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
        print(f"Start processing: {self.log_source_view}")
        self.r = r = self.get_or_upload_log()

        if r is False:
            return False

        r = self.fix_bosses(r)

        try:
            encounter = Encounter.objects.get(dpsreport_boss_id=r["encounter"]["bossId"])
        except Encounter.DoesNotExist:
            encounter = None
            # jank way of making error known to user.
            print(
                f"""
ERROR
Encounter not part of database. Register? {r['encounter']}
bossId:  {r['encounter']['bossId']}
print(f"bossname:  {r['encounter']['boss']}
ERROR
"""
            )
            if settings.DEBUG:
                raise Encounter.DoesNotExist

        # Check wrong metadata, sometimes the normal json response has empty
        # or plain wrong data. This has to do with some memory issues on dps.report.
        # Can be fixed by requesting the detailed info.
        if datetime.timedelta(seconds=r["encounter"]["duration"]).seconds == 0:
            print(f"Log seems broken. Requesting more info {self.log_source_view}")

            self.r2 = r2 = self.request_detailed_info()
            # r2["timeStart"] format is '2023-12-18 14:07:57 -05'
            start_time = parse(r2["timeStart"]).astimezone(datetime.timezone.utc)

            r["encounter"]["duration"] = self.r2["durationMS"] / 1000
            r["encounter"]["isCm"] = r2["isCM"]
            r["encounterTime"] = create_unix_time(start_time)

        players = [i["display_name"] for i in r["players"].values()]
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
                "core_player_count": len(Player.objects.filter(gw2_id__in=players)),
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
                print("    Requesting final boss health")
                self.r2 = r2 = self.request_detailed_info()
                log.final_health_percentage = 100 - r2["targets"][0]["healthPercentBurned"]

                # Sometimes people get in combat at eyes which creates an uneccesary log.
                if log.final_health_percentage == 100.0 and self.r["encounter"]["boss"] == "Eye of Fate":
                    self.move_failed_upload()
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
                and (log.encounter.instance.type == "raid")
                and not (log.cm)
            ):
                print("    Checking for emboldened")
                self.r2 = r2 = self.request_detailed_info()
                if "presentInstanceBuffs" in r2:
                    log.emboldened = 68087 in list(chain(*r2["presentInstanceBuffs"]))
                else:
                    log.emboldened = False
            else:
                log.emboldened = False

            log.save()
        print(f"Finished processing: {self.log_source_view}")

        return log
