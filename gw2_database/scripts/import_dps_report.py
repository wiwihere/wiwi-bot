# %%
"""
TODO list
- Change day end to reset time.
- Fractals shouldnt be an input. It should decide on its own what to do.
# after 30 mins of no logs, stop and update leaderboard.
# count fractal logs and stop if all are done.
- bundle raids

Multiple runs on same day/week?
- minimum core-count of 6 for leaderboards?

- create empty database
- credentials on database
"""

import datetime
import os
import time
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

import discord
import numpy as np
from dateutil.parser import parse
from discord import SyncWebhook
from django.db.models import Q

if __name__ == "__main__":
    # -- temp TESTING --
    from django_for_jupyter import init_django_from_commands

    init_django_from_commands("gw2_database")
    # -- temp TESTING --

import requests
from gw2_logs.models import DpsLog, Emoji, Encounter, Instance, InstanceClear, InstanceClearGroup, Player
from log_helpers import (
    EMBED_COLOR,
    RANK_EMOTES,
    WIPE_EMOTES,
    create_rank_str,
    create_unix_time,
    get_duration_str,
    get_emboldened_wing,
    get_fractal_day,
    today_y_m_d,
)

from bot_settings import settings

# %%


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
        files = {
            "file": open(
                self.log_path,
                "rb",
            )
        }

        self.r_raw = r = requests.post(base_url, files=files, data=data)

        if self.r_raw.status_code == 503:
            print(f"ERROR 503: Failed uploading {self.log_source_view}")
            return False
        if self.r_raw.status_code == 403:
            print(f"ERROR 403: Failed uploading {self.log_source_view}")
            print(self.r_raw.json()["error"])
            return False
        return r.json()

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
            print(f"Uploading log:  {self.log_source_view}")
            if self.log_path:
                r = self.upload_log()
            if self.log_url:
                r = self.request_metadata(url=self.log_url)
        else:
            print(f"Already in database: {self.log_source_view}")
            r = self.get_django_log().first().json_dump
        return r

    def fix_bosses(self, r):
        """Change raw results a bit to assign logs to the correct Encounter."""

        if r["encounter"]["boss"] == "Ai":
            # Dark and light Ai have the same boss id. This doesnt work in the database.
            # fightName in detailed logs do names as below, so we can look them up
            # 'Dark Ai, Keeper of the Peak'
            # 'Elemental Ai, Keeper of the Peak'
            print("Fixing Ai boss name")
            self.r2 = r2 = self.request_detailed_info(report_id=r["id"], url=r["permalink"])
            r["encounter"]["boss"] = r2["fightName"].split(",")[0]
            # Dark to different bossid so it gives separate log
            if r["encounter"]["boss"] == "Dark Ai":
                r["encounter"]["bossId"] = -23254

        if r["encounter"]["bossId"] == 25413:
            # OLC normal mode has different bossId because its 3 bosses apparently.
            # We change it to the cm bossId
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
        self.r = r = self.get_or_upload_log()

        if r is False:
            return False

        r = self.fix_bosses(r)

        try:
            encounter = Encounter.objects.get(dpsreport_boss_id=r["encounter"]["bossId"])
        except Encounter.DoesNotExist:
            encounter = None
            print(f"Encounter not part of database. Register? {r['encounter']}")
            print(f"bossId:  {r['encounter']['bossId']}")
            print(f"bossname:  {r['encounter']['boss']}")

        # Check wrong metadata, sometimes the normal json response has empty
        # or plain wrong data. This has to do with some memory issues on dps.report.
        # Can be fixed by requesting the detailed info.
        if datetime.timedelta(seconds=r["encounter"]["duration"]).seconds == 0:
            print(f"Log seems broken. Requesting more info {self.log_source_view}")

            self.r2 = r2 = self.request_detailed_info()
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
            start_time=datetime.datetime.fromtimestamp(r["encounterTime"], tz=datetime.timezone.utc),
        )
        print(f"Finished updating {self.log_source_view}")

        # Update final health percentage
        if log.final_health_percentage is None:
            if log.success is False:
                print("Requesting final boss health")
                self.r2 = r2 = self.request_detailed_info()
                log.final_health_percentage = 100 - r2["targets"][0]["healthPercentBurned"]
            else:
                log.final_health_percentage = 0
            log.save()

        # Check emboldened
        if log.emboldened is None:
            emboldened_wing = get_emboldened_wing(log.start_time)
            if (
                (emboldened_wing == log.encounter.instance.nr)
                and (log.encounter.instance.type == "raid")
                and not (log.cm)
            ):
                print("Checking for emboldened")
                self.r2 = r2 = self.request_detailed_info()
                if "presentInstanceBuffs" in r2:
                    log.emboldened = 68087 in list(chain(*r2["presentInstanceBuffs"]))
                else:
                    log.emboldened = False
            else:
                log.emboldened = False

            log.save()

        return log


@dataclass
class InstanceClearInteraction:
    """Single instance clear; raidwing or fractal scale or strikes grouped per expansion."""

    iclear: InstanceClear

    @classmethod
    def from_logs(cls, logs, instance_group=None):
        """Log should be filtered on instance"""
        iname = f"{logs[0].encounter.instance.name_lower}__{logs[0].start_time.strftime('%Y%m%d')}"

        # Check if all logs are from the same wing.
        same_wing = all(log.encounter.instance == logs[0].encounter.instance for log in logs)
        if not same_wing:
            raise ValueError("Not all logs of same wing.")

        # Create or update instance
        iclear, created = InstanceClear.objects.update_or_create(
            defaults={
                "instance": logs[0].encounter.instance,
                "instance_clear_group": instance_group,
            },
            name=iname,
        )
        if created:
            print(f"Created {iclear}")

        # All logs that are not yet part of the instance clear will be added.
        for log in set(logs).difference(set(iclear.dps_logs.all())):
            log.instance_clear = iclear
            log.save()

        # Update start_time
        iclear.start_time = iclear.dps_logs.all().order_by("start_time").first().start_time

        # Calculate duration
        last_log = iclear.dps_logs.all().order_by("start_time").last()
        iclear.duration = last_log.start_time + last_log.duration - iclear.start_time

        # Check if all encounters have been finished.
        encounter_count = max([i.nr for i in iclear.instance.encounters.all()])

        iclear.success = False
        if len(iclear.dps_logs.filter(success=True)) == encounter_count:
            iclear.success = True

        iclear.emboldened = False
        if len(iclear.dps_logs.filter(success=True, emboldened=True)) > 0:
            iclear.emboldened = True

        iclear.save()
        return cls(iclear)

    @classmethod
    def from_name(cls, name):
        return cls(InstanceClear.objects.get(name=name))


@dataclass
class InstanceClearGroupInteraction:
    iclear_group: InstanceClearGroup
    fractal: bool

    def __post_init__(self):
        self.get_total_clear_duration()

    @classmethod
    def create_from_date(cls, y, m, d, fractal=False):
        """Create an instance clear group from a specific date."""
        # All logs in a day
        logs_day = DpsLog.objects.filter(
            start_time__year=y,
            start_time__month=m,
            start_time__day=d,
        )
        if not fractal:
            logs_day = logs_day.exclude(encounter__instance__type="fractal")
            name = f"raids__{y}{str(m).zfill(2)}{str(d).zfill(2)}"

        else:
            logs_day = logs_day.filter(encounter__instance__type="fractal")
            name = f"fractals__{y}{str(m).zfill(2)}{str(d).zfill(2)}"

        # if len(logs_day) == 0:
        #     raise Exception(f"No logs? fractals={fractal}")

        instances_day = np.unique([log.encounter.instance.name for log in logs_day])

        iclear_group, created = InstanceClearGroup.objects.update_or_create(
            name=name,
        )

        # Create individual instance clears
        for instance_name in instances_day:
            logs_instance = logs_day.filter(encounter__instance__name=instance_name)
            ici = InstanceClearInteraction.from_logs(logs=logs_instance, instance_group=iclear_group)

        # Set start time of clear
        if iclear_group.instance_clears.all():
            start_time = min([i.start_time for i in iclear_group.instance_clears.all()])
            if iclear_group.start_time != start_time:
                iclear_group.start_time = start_time
                iclear_group.save()

        return cls(iclear_group, fractal)

    @classmethod
    def from_name(cls, name, fractal):
        return cls(InstanceClearGroup.objects.get(name=name), fractal)

    def create_discord_time(self, t: datetime.datetime):
        """time.mktime uses local time while the times in django are in utc.
        So we need to convert and then make discord str of it
        """
        t = create_unix_time(t)
        return f"<t:{t}:t>"

    @property
    def clears_by_date(self):
        return self.iclear_group.instance_clears.all().order_by("start_time")

    def get_total_clear_duration(self):
        """Get the total duration for raids and fractals
        Duration is saved in the iclear_group.
        """
        if self.iclear_group.type == "raid":
            # For raids we need to check multiple clears since they may not be done in one session.
            week_start = self.iclear_group.start_time - datetime.timedelta(
                days=self.iclear_group.start_time.weekday()
            )  # days are correct, but not hours and mins.
            week_start = week_start.replace(hour=8, minute=30, second=0, microsecond=0)  # Raid reset time.

            week_clears = InstanceClearGroup.objects.filter(type="raid").filter(
                Q(start_time__gte=week_start) & Q(start_time__lte=self.iclear_group.start_time)
            )
            successes = list(
                chain(*[j.instance_clears.filter(instance__type="raid", success=True) for j in week_clears])
            )

            if len(successes) == len(Instance.objects.filter(type=self.iclear_group.type)):
                print("Finished a whole instance group!")
                self.iclear_group.success = True
                self.iclear_group.duration = sum([ic.duration for ic in successes], datetime.timedelta())
                self.iclear_group.save()

        elif self.iclear_group.type == "fractal":
            # If success instances equals total number of instances
            if sum([j[0] for j in self.iclear_group.instance_clears.all().values_list("success")]) == len(
                Instance.objects.filter(type=self.iclear_group.type)
            ):
                print("Finished all fracals!")
                self.iclear_group.success = True
                self.iclear_group.duration = sum(
                    [i[0] for i in (self.iclear_group.instance_clears.all().values_list("duration"))],
                    datetime.timedelta(),
                )
                self.iclear_group.save()

    def create_message(self):
        """Create a discord message from the available logs that are linked
        to the instance clear.
        """
        self.all_logs = list(chain(*[i.dps_logs.order_by("start_time") for i in self.clears_by_date]))

        instance_types = np.unique([i.instance.type for i in self.clears_by_date])

        descriptions = {}
        titles = {}

        # Put raid, strike, fractal in separate embeds.
        for instance_type in instance_types:
            core_emote = Emoji.objects.get(name="core").discord_tag
            pug_emote = Emoji.objects.get(name="pug").discord_tag
            try:
                core_count = int(np.median([log.core_player_count for log in self.all_logs]))
                pug_count = int(np.median([log.player_count for log in self.all_logs])) - core_count
            except TypeError:
                core_count = 0
                pug_count = 0

            # Nina's space, add space after 5 ducks for better readability.
            pug_split_str = f"{core_emote*core_count}{pug_emote*pug_count}".split(">")
            pug_split_str[5] = f" {pug_split_str[5]}"  # empty str here:`⠀`
            pug_str = ">".join(pug_split_str)

            # title description with start - end time and colored ducks for core/pugs
            description = f"""{self.create_discord_time(self.all_logs[0].start_time)} - \
{self.create_discord_time(self.all_logs[-1].start_time+self.all_logs[-1].duration)} \
\n{pug_str}\n
"""

            title = self.iclear_group.pretty_time
            # Add total instance group time if all bosses finished.

            if self.iclear_group.success:
                group = list(
                    InstanceClearGroup.objects.filter(success=True, type=icgi.iclear_group.type)
                    .filter(
                        Q(start_time__gte=self.iclear_group.start_time - datetime.timedelta(days=9999))
                        & Q(start_time__lte=self.iclear_group.start_time)
                    )
                    .order_by("duration")
                )
                rank_str = create_rank_str(indiv=self.iclear_group, group=group)

                duration_str = get_duration_str(self.iclear_group.duration.seconds, colon=False)
                # description = f"⠀⠀⠀⠀⠀:first_place: **{duration_str}** :first_place: \n".join(description.split("\n", 1))
                title += f"⠀⠀⠀⠀{rank_str} **{duration_str}** {rank_str} \n"

            titles[instance_type] = {}
            titles[instance_type]["main"] = title
            descriptions[instance_type] = {}
            descriptions[instance_type]["main"] = description

        # Loop over the instance clears
        first_boss = True  # Tracks if a log is the first boss of all logs.
        for iclear in self.clears_by_date:
            titles[iclear.instance.type][iclear.name] = ""  # field title
            descriptions[iclear.instance.type][iclear.name] = ""  # field description

            # Find rank of full instance on leaderboard
            if iclear.success:
                iclear_success_all = list(
                    iclear.instance.instance_clears.filter(success=True)
                    .filter(
                        Q(start_time__gte=iclear.start_time - datetime.timedelta(days=9999))
                        & Q(start_time__lte=iclear.start_time)
                    )
                    .order_by("duration")
                )
            rank_str = create_rank_str(indiv=iclear, group=iclear_success_all)

            # Cleartime wing
            duration_str = get_duration_str(iclear.duration.seconds)

            titles[iclear.instance.type][
                iclear.name
            ] = f"**__{iclear.instance.emoji.discord_tag}{rank_str}{iclear.name.split('__')[0].replace('_', ' ').title()} \
({duration_str})__**\n"
            field_value = ""

            instance_logs = iclear.dps_logs.order_by("start_time")
            all_success_logs = list(
                chain(*[i.dps_logs.filter(success=True).order_by("start_time") for i in self.clears_by_date])
            )

            # Loop all logs in an instance (raid wing).
            # If there are wipes also take those
            # Print each log on separate line. Also calculate diff between logs (downtime)
            for idx, log in enumerate(instance_logs):
                encounter_wipes = instance_logs.filter(success=False, encounter__nr=log.encounter.nr)
                encounter_success = instance_logs.filter(success=True, encounter__nr=log.encounter.nr)

                duration_str = get_duration_str(0)  # Default no duration between previous and start log.

                if first_boss:
                    # If there was a wipe on the first boss we calculate diff between start of
                    # wipe run and start of kill run
                    if len(encounter_wipes) > 0:
                        diff_time = log.start_time - self.all_logs[0].start_time
                        if not encounter_success:
                            diff_time = log.start_time + log.duration - self.all_logs[0].start_time

                        duration_str = get_duration_str(diff_time.seconds)
                else:
                    # Calculate duration between start of kill run with previous kill run
                    if log.success:
                        all_success_logs_idx = all_success_logs.index(log)
                        diff_time = log.start_time - (
                            all_success_logs[all_success_logs_idx - 1].start_time
                            + all_success_logs[all_success_logs_idx - 1].duration
                        )
                        duration_str = get_duration_str(diff_time.seconds)
                if log.success:
                    first_boss = False  # Only after a successful log the first_boss is cleared.

                # Find rank of boss on leaderboard filter for logs of last year.
                encounter_success_all = None
                if log.success:
                    encounter_success_all = list(
                        log.encounter.dps_logs.filter(success=True, cm=log.cm)
                        .filter(
                            Q(start_time__gte=log.start_time - datetime.timedelta(days=9999))
                            & Q(start_time__lte=log.start_time)
                        )
                        .order_by("duration")
                    )
                rank_str = create_rank_str(indiv=log, group=encounter_success_all)

                # Wipes also get an url, can be click the emote to go there. Doesnt work on phone.
                # Dont show wipes that are under 15 seconds.
                wipe_str = ""
                for wipe in encounter_wipes:
                    if wipe.duration.seconds > 15:
                        wipe_emote = WIPE_EMOTES[np.ceil(wipe.final_health_percentage / 12.5)]
                        wipe_str += f" [{wipe_emote}]({wipe.url})"

                # Add encounter to field
                if log.success:
                    field_value += f"{log.discord_tag.format(rank_str=rank_str)}_+{duration_str}_{wipe_str}\n"
                else:
                    # If there are only wipes for an encounter, still add it to the field.
                    # This is a bit tricky, thats why we need to check a couple things.
                    #   - Cannot add text when there is a success as it will print multiple lines for
                    #     the same encounter.
                    #   - Also should only add multiple wipes on same boss once.
                    if not encounter_success:
                        if list(encounter_wipes).index(log) + 1 == len(encounter_wipes):
                            cm_str = ""
                            if log.cm:
                                cm_str = " CM"
                            field_value += f"{log.emoji_tag}{rank_str}{log.encounter.name}{cm_str} (wipe)_+{duration_str}_{wipe_str}\n"

            # Add the field text to the embed. Raids and strikes have a
            # larger chance that the field_value is larger than 1024 charcters.
            # This is sadly currently the limit on embed.field.value.
            # Descriptions can be 4096 characters, so instead of a field we just edit the description.
            descriptions[iclear.instance.type][iclear.name] = field_value

        self.titles = titles
        self.descriptions = descriptions

        return titles, descriptions

    def create_embeds(self, titles, descriptions):
        """Create discord embed from description."""
        embeds = {}
        has_title = False
        for instance_type in titles:
            use_fields = True  # max 1024 per field
            field_characters = np.array([len(i) for i in descriptions[instance_type].values()])
            # Check field length. If more than 1024 it cannot go to a field and should instead
            # go to description
            if np.any(field_characters > 1024):
                print("Cannot use fields because one has more than 1024 chars")
                use_fields = False

                # field characters actually change here because the titles are included in
                # the description.
                field_characters += np.array([len(i) for i in titles[instance_type].values()])

            # If we go over 4096 characters, a new embed should be created.
            # Just find per field which embed they should be in:

            embed_ids = np.floor(np.cumsum(field_characters) / 4096).astype(int)

            # Loop over every unique embed for this instance.
            for embed_id in np.unique(embed_ids):
                title = ""
                description = ""
                # The first embed gets a title and title  description.
                if int(embed_id) == 0:
                    title = titles[instance_type]["main"]
                    description = descriptions[instance_type]["main"]
                    if ("raid" in titles) and ("strike" in titles):
                        if not has_title:
                            has_title = True
                        else:
                            title = ""
                            description = ""

                if not use_fields:
                    # Loop the encounters
                    for embed_id_instance, encounter_key in zip(embed_ids, descriptions[instance_type].keys()):
                        if encounter_key == "main":  # Main is already in title.
                            continue
                        if embed_id_instance != embed_id:  # Should go to different embed.
                            print(len(description))

                            continue

                        description += titles[instance_type][encounter_key]
                        description += descriptions[instance_type][encounter_key] + "\n"

                embeds[f"{instance_type}_{embed_id}"] = discord.Embed(
                    title=title,
                    description=description,
                    colour=EMBED_COLOR[instance_type],
                )

                if use_fields:
                    for embed_id_instance, encounter_key in zip(embed_ids, descriptions[instance_type].keys()):
                        if encounter_key == "main":  # Main is already in title.
                            continue
                        if embed_id_instance != embed_id:  # Should go to different embed.
                            continue
                        field_name = titles[instance_type][encounter_key]
                        field_value = descriptions[instance_type][encounter_key]
                        embeds[f"{instance_type}_{embed_id}"].add_field(
                            name=field_name, value=field_value, inline=False
                        )

        return embeds

    def create_or_update_discord_message(self, embeds):
        """Send message to discord created by .create_message to discord"""

        embeds_split = {}
        embeds_split["fractal"] = [embeds[i] for i in embeds if "fractal_" in i]
        embeds_split["raid"] = [embeds[i] for i in embeds if "fractal_" not in i]

        webhooks = {}
        webhooks["fractal"] = SyncWebhook.from_url(settings.WEBHOOK_BOT_CHANNEL_FRACTAL)
        webhooks["raid"] = SyncWebhook.from_url(settings.WEBHOOK_BOT_CHANNEL_RAID)

        # Update message if it exists
        for embeds_instance, webhook in zip(embeds_split.values(), webhooks.values()):
            if embeds_instance == []:
                continue

            if self.iclear_group.discord_message_id is not None:
                try:
                    webhook.edit_message(
                        message_id=self.iclear_group.discord_message_id,
                        embeds=embeds_instance,
                    )

                    print("Discord message updated")
                except Exception as e:  # NotFound error
                    print("Error updating message")
                    print(e)

            # Otherwise create a new message.
            else:
                mess = webhook.send(wait=True, embeds=embeds_instance)
                self.iclear_group.discord_message_id = mess.id
                self.iclear_group.save()
                print("New discord message created")


## %%
#
# y, m, d = today_y_m_d()
y, m, d = 2024, 1, 22
# y, m, d = 2023, 12, 11

fractal = get_fractal_day(y, m, d)

# fractal = False
shared_folder = False  # True when getting logs from onedrive

log_paths_done = []
run_count = 0
# if True:
try:
    while True:
        print(f"Run {run_count}")

        # Find logs in directory
        log_dir = Path(settings.DPS_LOGS_DIR)
        if shared_folder:
            log_dir = Path(settings.ONEDRIVE_LOGS_DIR)
        log_paths = sorted(log_dir.rglob(f"{y}{str(m).zfill(2)}{str(d).zfill(2)}*.zevtc"), key=os.path.getmtime)

        # Process each log
        for log_path in sorted(set(log_paths).difference(set(log_paths_done)), key=os.path.getmtime):
            print(log_path)
            log_upload = LogUploader.from_path(log_path)

            success = log_upload.run()
            if success is not False:
                log_paths_done.append(log_path)

            self = icgi = InstanceClearGroupInteraction.create_from_date(y=y, m=m, d=d, fractal=fractal)
            titles, descriptions = icgi.create_message()
            embeds = icgi.create_embeds(titles, descriptions)

            icgi.create_or_update_discord_message(embeds=embeds)
            break

        # Stop when its not today, not expecting more logs anyway.
        if (y, m, d) != today_y_m_d():
            break
        break

        time.sleep(30)
        run_count += 1

except KeyboardInterrupt:
    pass


# %% Just update or create discord message, dont upload logs.


y, m, d = today_y_m_d()
y, m, d = 2024, 1, 21

fractal = get_fractal_day(y, m, d)
# fractal = False


self = icgi = InstanceClearGroupInteraction.create_from_date(y=y, m=m, d=d, fractal=fractal)
# self = icgi = InstanceClearGroupInteraction.from_name("dummy")

embeds = icgi.create_message()
print(embeds)

icgi.create_or_update_discord_message(embeds=embeds)
# ici = InstanceClearInteraction.from_name("w7_the_key_of_ahdashim__20231211")

# %% Manual uploads without creating discord message

# y, m, d = 2023, 12, 18

# log_dir = Path(settings.DPS_LOGS_DIR)
# log_paths = list(log_dir.rglob(f"{y}{str(m).zfill(2)}{str(d).zfill(2)}*.zevtc"))

# for log_path in log_paths:
#     self = log_upload = LogUploader.from_path(log_path)
#     log_upload.run()

# log_urls = [
#     r"https://dps.report/dIVa-20231012-213625_void",
#     r"https://dps.report/bUkb-20231018-210130_void",
#     r"https://dps.report/QpUT-20231024-210315_void",
# ]
# for log_url in log_urls:
#     self = log_upload = LogUploader.from_url(log_url=log_url)
#     log_upload.run()


# %% TEMP update skull ids

skull_str = """<:skull_8_8:1199740877782909009>
<:skull_7_8:1199739773577875458>
<:skull_6_8:1199739753248084119>
<:skull_5_8:1199739676467150899>
<:skull_4_8:1199739673224945745>
<:skull_3_8:1199739671798890606>
<:skull_2_8:1199739670641258526>
<:skull_1_8:1199739666677641227>"""

names = [i for i in skull_str.split(":")[1:] if i.startswith("s")]
discord_ids = [int(i.split(">")[0]) for i in skull_str.split(":")[1:] if i.startswith("1")]
for name, discord_id in zip(names, discord_ids):
    Emoji.objects.update_or_create(name=name, discord_id=discord_id)

# %%
for icg in InstanceClearGroup.objects.filter(type="fractal"):
    icgi = InstanceClearGroupInteraction.from_name(icg.name, fractal=True)
    titles, descriptions = icgi.create_message()
    embeds = icgi.create_embeds(titles, descriptions)

    icgi.create_or_update_discord_message(embeds=embeds)
