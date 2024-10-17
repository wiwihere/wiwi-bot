# %%
import datetime
import json
import shutil
import time
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dateutil.parser import parse

if __name__ == "__main__":
    from django_for_jupyter import init_django_from_commands

    init_django_from_commands("gw2_database")

from bot_settings import settings
from gw2_logs.models import DpsLog, Emoji, Encounter, Instance, InstanceClear, InstanceClearGroup, Player
from scripts.ei_parser import EliteInisghtsParser
from scripts.log_helpers import create_unix_time, get_duration_str, get_emboldened_wing, today_y_m_d, zfill_y_m_d


@dataclass
class LogUploader:
    """Upload log to dps.report and save results in django database.
    Sometimes dps.report doesnt report correctly, will get detailed info then.
    """

    log_path: str = None
    log_url: str = None
    only_url: bool = False

    def __post_init__(self):
        if self.log_path:
            self.log_path = Path(self.log_path).as_posix()

        self.log = None  # DpsLog instance
        self.r = None  # Normal api response
        self.r2 = None  # Detailed api response

    @classmethod
    def from_path(cls, log_path, only_url=False):
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
        """Upload log to dps.report, a.dps.report or b.dps.report"""
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

            time.sleep(1)
            self.r_raw = r = requests.post(base_url, files=files, data=data)

        if r.status_code == 503:
            print(f"{datetime.datetime.now()} ERROR 503: Failed uploading {self.log_source_view}")
            try:
                print(f"ERROR: {self.r_raw.error}")
            except:
                pass
            return False
        if r.status_code == 403:
            print(f"{datetime.datetime.now()} ERROR 403: Failed uploading {self.log_source_view}")
            try:
                print(r.json()["error"])

                # Move perma fail upload so it wont bother us again.
                if r.json()["error"] == "Encounter is too short for a useful report to be made":
                    self.move_failed_upload()
            except json.decoder.JSONDecodeError:
                pass
            try:
                print(f"{datetime.datetime.now()} ERROR Reason: {self.r_raw.reason}")
                if str(self.r_raw.reason) == "Forbidden":
                    self.move_forbidden_upload()
            except:
                if str(self.r_raw.reason) == "Forbidden":
                    self.move_forbidden_upload()
                pass
            return False

        if hasattr(r, "status_code"):
            if r.status_code == 200:
                return r.json()

        print(
            f"{datetime.datetime.now()} ERROR: Failed uploading log for unknown reason {r.status_code} {self.log_source_view}"
        )
        return False

    def move_failed_upload(self):
        """Some logs are just broken. Lets remove them from the equation"""  # noqa
        out_path = Path(settings.DPS_LOGS_DIR).parent.joinpath("failed_logs", Path(self.log_path).name)
        out_path.parent.mkdir(exist_ok=True)
        print(f"Moved failing log from {self.log_source_view} to")
        print(out_path)
        shutil.move(src=self.log_path, dst=out_path)

    def move_forbidden_upload(self):
        """The API throws exceptions regularly. Upload these by hand ;("""  # noqa
        out_path = Path(settings.DPS_LOGS_DIR).parent.joinpath(
            "forbidden_logs", zfill_y_m_d(*today_y_m_d()), Path(self.log_path).name
        )
        out_path.parent.mkdir(exist_ok=True, parents=True)
        print(f"Moved forbidden log from {self.log_source_view} to")
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
        More info of the output can be found here: https://baaron4.github.io/GW2-Elite-Insights-Parser/Json/index.html
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
            print(f"{datetime.datetime.now()}    Uploading log")
            if self.log_path:
                r = self.upload_log()
            if self.log_url:
                r = self.request_metadata(url=self.log_url)
        else:
            print(f"{datetime.datetime.now()}    Already in database")
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
        print(f"{datetime.datetime.now()} Start processing: {self.log_source_view}")
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
        # or plain wrong data. This has to do with some memory issues on b.dps.report.
        # Can be fixed by requesting the detailed info.
        # Still relevant when only requesting url because start time can be off
        if datetime.timedelta(seconds=r["encounter"]["duration"]).seconds == 0:
            print(f"Log seems broken. Requesting more info {self.log_source_view}")

            self.r2 = r2 = self.request_detailed_info(report_id=r["id"], url=r["permalink"])
            # r2["timeStart"] format is '2023-12-18 14:07:57 -05'
            start_time = parse(r2["timeStart"]).astimezone(datetime.timezone.utc)

            r["encounter"]["duration"] = self.r2["durationMS"] / 1000
            r["encounter"]["isCm"] = r2["isCM"]
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
                    print(f"{datetime.datetime.now()}    Requesting final boss health")
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
                    and (log.encounter.instance.instance_group.name == "raid")
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

        else:
            self.log, created = log, created = DpsLog.objects.update_or_create(
                defaults={
                    "url": r["permalink"],
                },
                # r["encounterTime"] format is 1702926477
                start_time=datetime.datetime.fromtimestamp(r["encounterTime"], tz=datetime.timezone.utc),
            )

        print(f"{datetime.datetime.now()} Finished processing: {self.log_source_view}")

        return log


@dataclass
class DpsLogInteraction:
    """Create a dpslog from detailed logs in EI parser or the
    shorter json from dps.report.
    """

    dpslog: DpsLog = None

    @classmethod
    def from_local_ei_parser(cls, log_path, parsed_path):
        try:
            dpslog = DpsLog.objects.get(local_path=log_path)
        except DpsLog.DoesNotExist:
            dpslog = None

        if dpslog is None:
            if parsed_path is None:
                print(f"{log_path} was not parsed")
                return False

            json_detailed = EliteInisghtsParser.load_json_gz(js_path=parsed_path)
            dpslog = cls.from_detailed_logs(log_path, json_detailed)

        return cls(dpslog=dpslog)

    @classmethod
    def from_detailed_logs(cls, log_path, json_detailed):
        print(f"Processing detailed log: {log_path}")
        r2 = json_detailed

        players = [player["account"] for player in r2["players"]]
        final_health_percentage = 100 - r2["targets"][0]["healthPercentBurned"]

        encounter = Encounter.objects.get(ei_encounter_id=r2["eiEncounterID"])

        if final_health_percentage == 100.0 and encounter.name == "Eye of Fate":
            move_failed_upload(log_path)

        if encounter.name == "Temple of Febe":
            phasetime_str = cls._get_phasetime_str(json_detailed=json_detailed)
        else:
            phasetime_str = None

        dpslog, created = DpsLog.objects.update_or_create(
            defaults={
                # "url": r["permalink"],
                "duration": datetime.timedelta(seconds=r2["durationMS"] / 1000),
                # "end_time"=,
                "player_count": len(players),
                "encounter": encounter,
                "boss_name": r2["fightName"],
                "cm": r2["isCM"],
                "lcm": r2["isLegendaryCM"],
                "emboldened": "b68087" in r2["buffMap"],
                "success": r2["success"],
                "final_health_percentage": final_health_percentage,
                "gw2_build": r2["gW2Build"],
                "players": players,
                "core_player_count": len(Player.objects.filter(gw2_id__in=players, role="core")),
                "friend_player_count": len(Player.objects.filter(gw2_id__in=players, role="friend")),
                # "report_id": r["id"],
                "local_path": log_path,
                # "json_dump": r,
                "phasetime_str": phasetime_str,
            },
            start_time=datetime.datetime.strptime(r2["timeStartStd"], "%Y-%m-%d %H:%M:%S %z").astimezone(
                datetime.timezone.utc
            ),
        )
        return dpslog

    def from_normal_logs(self):
        pass

        # dpslog = DpsLog.objects.filter()

        # return cls(dpslog=dpslog)

    @staticmethod
    def _get_phasetime_str(json_detailed):
        """For Cerus LCM the time breakbar phases are reached is calculated from detailed logs."""
        # Get information on phase timings
        data = json_detailed["phases"]

        filtered_data = [d for d in data if "Cerus Breakbar" in d["name"]]
        df = pd.DataFrame(filtered_data)
        if not df.empty:
            df["time"] = df["end"].apply(lambda x: datetime.timedelta(minutes=10) - datetime.timedelta(milliseconds=x))

            phasetime_lst = [
                get_duration_str(i.astype("timedelta64[s]").astype(np.int32)) for i in df["time"].to_numpy()
            ]
        else:
            phasetime_lst = []

        while len(phasetime_lst) < 3:
            phasetime_lst.append(" -- ")

        phasetime_str = " | ".join(phasetime_lst)

        return phasetime_str


def move_failed_upload(log_path):
    """Some logs are just broken. Lets remove them from the equation"""  # noqa
    out_path = Path(settings.DPS_LOGS_DIR).parent.joinpath("failed_logs", Path(log_path).name)
    out_path.parent.mkdir(exist_ok=True)
    # print(f"Moved failing log from {self.log_source_view} to")
    print(out_path)
    shutil.move(src=log_path, dst=out_path)


# %%
# if __name__ == "__main__":
#     #     self = LogUploader.from_path(r"")
#     log_path = Path(
#     )
#     log = Path(
#     )
#     #     self.run()
#     a = DpsLogInteraction.from_local_ei_parser(log_path=log_path, parsed_path=log)


# %%
