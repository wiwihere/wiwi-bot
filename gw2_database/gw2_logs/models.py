from itertools import chain

from discord import ChannelFlags
from django.db import models
from traitlets import default

INSTANCE_TYPES = [("raid", "Raid"), ("fractal", "Fractal"), ("strike", "Strike"), ("golem", "Golem")]
EMOJI_TYPES = [("raid", "Raid"), ("fractal", "Fractal"), ("strike", "Strike"), ("medal", "Medal"), ("other", "Other")]
PLAYER_ROLES = [("core", "Core"), ("friend", "Friend")]

# %%


# Create your models here.


class Emoji(models.Model):
    """Discord emoji"""

    name = models.CharField(max_length=30)
    animated = models.BooleanField(null=True, blank=True, default=False)
    type = models.CharField(null=True, max_length=10, choices=EMOJI_TYPES, default=None)
    discord_id = models.IntegerField(null=True, blank=True)
    url = models.URLField(null=True, blank=True)
    discord_id_cm = models.IntegerField(null=True, blank=True)
    url_cm = models.URLField(null=True, blank=True)
    discord_id_lcm = models.IntegerField(null=True, blank=True)
    url_lcm = models.URLField(null=True, blank=True)
    png_name = models.CharField(max_length=50, null=True, blank=True)

    def save(self, *args, **kwargs):
        self.url = f"https://cdn.discordapp.com/emojis/{self.discord_id}.webp?size=32&quality=lossless"
        self.url_cm = f"https://cdn.discordapp.com/emojis/{self.discord_id_cm}.webp?size=32&quality=lossless"
        self.url_lcm = f"https://cdn.discordapp.com/emojis/{self.discord_id_lcm}.webp?size=32&quality=lossless"
        super(Emoji, self).save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def name_lower(self):
        return self.name.lower().replace(" ", "_")

    def discord_tag(self, difficulty="normal"):
        discord_id = self.get_discord_id(difficulty)
        if not self.animated:
            return f"<:{self.name_lower}:{discord_id}>"
        return f"<a:{self.name_lower}:{discord_id}>"

    def discord_tag_custom_name(self, difficulty="normal"):
        discord_id = self.get_discord_id(difficulty)
        if not self.animated:
            return f"<:{{}}:{discord_id}>"
        return f"<a:{{}}:{discord_id}>"

    def get_discord_id(self, difficulty):
        if difficulty == "normal":
            discord_id = self.discord_id
        elif difficulty == "cm":
            discord_id = self.discord_id_cm
        elif difficulty == "lcm":
            discord_id = self.discord_id_lcm
        return discord_id


class DiscordMessage(models.Model):
    message_id = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.message_id}"


class InstanceGroup(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    discord_message = models.ForeignKey(
        DiscordMessage,
        related_name="instance_group",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    def __str__(self):
        return self.name


class Instance(models.Model):
    """Group of encounters"""

    name = models.CharField(max_length=30)
    instance_group = models.ForeignKey(
        InstanceGroup,
        related_name="instance",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    emoji = models.ForeignKey(
        Emoji,
        related_name="instance",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    discord_message = models.ForeignKey(
        DiscordMessage,
        related_name="instance",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    nr = models.IntegerField(null=True, blank=True)  # Nr of instance (raid nr)

    def __str__(self):
        return self.name

    @property
    def name_lower(self):
        return self.name.lower().replace(" ", "_")

    class Meta:
        ordering = ["instance_group", "nr"]


class Encounter(models.Model):
    """Single boss encounter in gw2"""

    name = models.CharField(max_length=30)
    shortname = models.CharField(max_length=30, null=True, blank=True)
    dpsreport_boss_id = models.IntegerField(null=True, blank=True)
    ei_encounter_id = models.IntegerField(null=True, blank=True)  # eiEncounterID
    folder_names = models.CharField(max_length=100, null=True, blank=True)
    emoji = models.ForeignKey(
        Emoji,
        related_name="encounter",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    instance = models.ForeignKey(
        Instance,
        related_name="encounters",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    nr = models.IntegerField(null=True, blank=True)  # Nr of boss in instance
    has_cm = models.BooleanField(null=True, blank=True)
    has_lcm = models.BooleanField(null=True, blank=True)
    lb = models.BooleanField(verbose_name="leaderboard", null=True, blank=True)  # Include in leaderboard
    lb_cm = models.BooleanField(verbose_name="leaderboard cm", null=True, blank=True)  # Include cm in leaderboard
    lb_lcm = models.BooleanField(verbose_name="leaderboard lcm", null=True, blank=True)  # Include lcm in leaderboard

    # TODO do we need this?
    leaderboard_instance_group = models.ForeignKey(
        InstanceGroup,
        related_name="encounters",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )  # Use the instance_group to select encounters that need to be bundled

    def __str__(self):
        return self.name

    @property
    def name_lower(self):
        return self.name.lower().replace(" ", "_")

    class Meta:
        ordering = ["instance", "nr"]


class InstanceClearGroup(models.Model):
    """Group of dps logs"""

    name = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=10, choices=INSTANCE_TYPES, default="raid")
    start_time = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    success = models.BooleanField(null=True, blank=True, default=False)
    discord_message = models.ForeignKey(
        DiscordMessage,
        related_name="instance_clear_group",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    discord_message_id_old = models.IntegerField(null=True, blank=True)  # TODO remove
    core_player_count = models.IntegerField(null=True, blank=True)
    friend_player_count = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name

    @property
    def name_lower(self):
        return self.name.lower().replace(" ", "_")

    @property
    def name_title(self):
        return self.name_lower.replace("_", " ").title()

    @property
    def pretty_time(self):
        if self.start_time is not None:
            return self.start_time.strftime("%a %d %b %Y")
        else:
            return "No start time yet"

    @property
    def dps_logs_all(self):
        return list(chain(*[i.dps_logs.all() for i in self.instance_clears.all()]))


class InstanceClear(models.Model):
    """Holds clears per instance. So if a wing is cleared all logs
    can be linked to this instance.
    """

    name = models.CharField(max_length=100, unique=True)
    instance = models.ForeignKey(
        Instance,
        related_name="instance_clears",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    instance_clear_group = models.ForeignKey(
        InstanceClearGroup,
        related_name="instance_clears",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    start_time = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    success = models.BooleanField(null=True, blank=True, default=False)  # All encounters in instance cleared?
    emboldened = models.BooleanField(null=True, blank=True)
    core_player_count = models.IntegerField(null=True, blank=True)
    friend_player_count = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name

    @property
    def name_lower(self):
        return self.name.lower().replace(" ", "_")

    @property
    def name_title(self):
        return self.name_lower.replace("_", " ").title()

    @property
    def discord_str(self):
        return f"{self.instance.emoji.discord_tag()} **{self.name_title}** {self.instance.emoji.discord_tag()}"

    class Meta:
        ordering = ["-start_time"]


class DpsLog(models.Model):
    """Base class to store dps logs in"""

    url = models.URLField(max_length=100)
    duration = models.DurationField(null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True, unique=True)
    end_time = models.DateTimeField(null=True, blank=True, unique=True)
    player_count = models.IntegerField(null=True, blank=True)
    encounter = models.ForeignKey(
        Encounter,
        related_name="dps_logs",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    boss_name = models.CharField(max_length=100, null=True, blank=True)
    cm = models.BooleanField(null=True, blank=True)
    lcm = models.BooleanField(null=True, blank=True)
    emboldened = models.BooleanField(null=True, blank=True)  # detailed info
    success = models.BooleanField(null=True, blank=True)
    final_health_percentage = models.FloatField(null=True, blank=True)  # detailed info
    gw2_build = models.IntegerField(null=True, blank=True)
    players = models.JSONField(default=list)
    core_player_count = models.IntegerField(null=True, blank=True)
    friend_player_count = models.IntegerField(null=True, blank=True)
    instance_clear = models.ForeignKey(
        InstanceClear,
        related_name="dps_logs",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    report_id = models.CharField(max_length=100, null=True, blank=True)
    local_path = models.CharField(max_length=200, null=True, blank=True)
    json_dump = models.JSONField(null=True, blank=True)
    phasetime_str = models.CharField(max_length=100, null=True, blank=True)  # cerus cm

    def __str__(self):
        return f"{self.boss_name} {self.start_time}"

    @property
    def difficulty(self):
        """Difficulty used in get the correct emote"""
        difficulty = "normal"
        if self.cm:
            difficulty = "cm"
        if self.lcm:
            difficulty = "lcm"
        return difficulty

    @property
    def cm_str(self):
        cm_str = ""
        if self.cm:
            cm_str = " CM"
        if self.lcm:
            cm_str = " LCM"
        return cm_str

    @property
    def discord_tag(self):
        mins, secs = divmod(self.duration.seconds, 60)

        if self.url == "":
            return f"{self.encounter.emoji.discord_tag(self.difficulty)}{{rank_str}}{self.encounter.name}{self.cm_str} \
(**{mins}:{str(secs).zfill(2)}**)"
        else:
            return f"{self.encounter.emoji.discord_tag(self.difficulty)}{{rank_str}}[{self.encounter.name}{self.cm_str}]({self.url}) \
(**{mins}:{str(secs).zfill(2)}**)"

    @property
    def pretty_time(self):
        if self.start_time is not None:
            return self.start_time.strftime("%a %d %b %Y")
        else:
            return "No start time yet"


class Player(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    gw2_id = models.CharField(max_length=100, null=True, blank=True)
    role = models.CharField(null=True, max_length=10, choices=PLAYER_ROLES, default=None)

    def __str__(self):
        return self.name
