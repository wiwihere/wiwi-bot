from django.contrib import admin

from . import models


class EncounterInline(admin.TabularInline):
    model = models.Encounter
    fields = ["id", "name", "emoji"]
    readonly_fields = ["id", "name", "emoji"]
    extra = 0
    show_change_link = True


class DpsLogInline(admin.TabularInline):
    model = models.DpsLog
    fields = ["id", "start_time", "duration", "encounter", "cm", "success", "core_player_count", "friend_player_count"]
    readonly_fields = [
        "id",
        "start_time",
        "duration",
        "encounter",
        "cm",
        "success",
        "core_player_count",
        "friend_player_count",
    ]
    extra = 0
    ordering = ("start_time",)

    show_change_link = True


class InstanceClearInline(admin.TabularInline):
    model = models.InstanceClear
    fields = [
        "name",
        "instance",
        "start_time",
        "duration",
        "success",
        "emboldened",
        "core_player_count",
        "friend_player_count",
    ]
    readonly_fields = [
        "name",
        "instance",
        "start_time",
        "duration",
        "success",
        "emboldened",
        "core_player_count",
        "friend_player_count",
    ]
    extra = 0
    ordering = ("start_time",)

    show_change_link = True


class InstanceClearGroupInline(admin.TabularInline):
    model = models.InstanceClearGroup
    fields = ["name", "type", "start_time", "duration", "success", "core_player_count", "friend_player_count"]
    readonly_fields = ["name", "type", "start_time", "duration", "success", "core_player_count", "friend_player_count"]
    extra = 0
    ordering = ("start_time",)

    show_change_link = True


class PlayerInline(admin.TabularInline):
    model = models.Player
    fields = ["name", "gw2_id"]
    readonly_fields = ["name", "gw2_id"]
    extra = 0
    ordering = ("name",)

    show_change_link = True


@admin.register(models.Instance)
class InstanceAdmin(admin.ModelAdmin):
    list_display = ("name", "instance_group", "emoji", "nr")
    inlines = [
        EncounterInline,
    ]


@admin.register(models.InstanceGroup)
class InstanceGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "discord_message")

    inlines = [
        EncounterInline,
    ]


@admin.register(models.Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "shortname",
        "instance",
        "nr",
        "emoji",
        "dpsreport_boss_id",
        "ei_encounter_id",
        "folder_names",
        "instance__group",
        "has_cm",
        "has_lcm",
        "lb",
        "lb_cm",
        "lb_lcm",
        "log_count",
        "leaderboard_instance_group",
    )

    # list_filter = "instance__type"
    inlines = [DpsLogInline]

    def instance__group(self, obj):
        if obj.instance is not None:
            return obj.instance.instance_group
        else:
            return None

    def log_count(self, obj):
        return obj.dps_logs.all().count()


@admin.register(models.Emoji)
class EmojiAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "png_name", "discord_id", "animated", "url")
    ordering = ("type", "png_name", "name")

    search_fields = ["name"]
    list_filter = ["type"]


@admin.register(models.InstanceClear)
class InstanceClearAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "instance",
        "start_time",
        "duration",
        "success",
        "emboldened",
        "instance_clear_group",
        "core_player_count",
        "friend_player_count",
        "log_count",
    )
    list_filter = ["instance"]

    inlines = [DpsLogInline]

    def log_count(self, obj):
        return obj.dps_logs.all().count()


@admin.register(models.InstanceClearGroup)
class InstanceClearGroupAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "type",
        "success",
        "duration",
        "start_time",
        "discord_message",
        "core_player_count",
        "friend_player_count",
        "log_count",
        "discord_message_id_old",
    )

    inlines = [InstanceClearInline]

    def log_count(self, obj):
        return sum([ic.dps_logs.all().count() for ic in obj.instance_clears.all()])


@admin.register(models.DpsLog)
class DpsLogAdmin(admin.ModelAdmin):
    list_display = (
        "encounter",
        "cm",
        "lcm",
        "emboldened",
        "success",
        "final_health_percentage",
        "duration",
        "url",
        "start_time",
        "core_player_count",
        "friend_player_count",
        "instance_clear_id",
        # "instance__type",
        # "group_clear_id",
    )
    list_filter = ["encounter", "success", "cm"]

    def instance_group(self, obj):
        if obj.encounter.instance is not None:
            return obj.encounter.instance.instance_group
        else:
            return None


@admin.register(models.Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("name", "gw2_id", "role")


@admin.register(models.DiscordMessage)
class DiscordMessage(admin.ModelAdmin):
    list_display = ("message_id",)
    inlines = [
        InstanceClearGroupInline,
    ]
