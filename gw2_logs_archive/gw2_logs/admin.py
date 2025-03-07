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


class InstanceInline(admin.TabularInline):
    model = models.Instance
    fields = ["name", "nr", "instance_group"]
    readonly_fields = ["name", "nr", "instance_group"]
    extra = 0

    ordering = ("nr", "instance_group")

    show_change_link = True


class InstanceGroupInline(admin.TabularInline):
    model = models.InstanceGroup
    fields = ["name"]
    readonly_fields = ["name"]
    extra = 0

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
    list_display = ("name", "nr", "instance_group", "emoji", "discord_message")
    inlines = [EncounterInline]


@admin.register(models.InstanceGroup)
class InstanceGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "discord_message")

    ordering = ("name",)


@admin.register(models.Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = (
        "id",
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
        "use_for_icg_duration",
    )

    list_filter = ["instance"]
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
    list_display = (
        "id",
        "name",
        "type",
        "png_name",
        "animated",
        "discord_id",
        "discord_id_cm",
        "discord_id_lcm",
        "url",
    )
    ordering = ("type", "png_name", "name")

    search_fields = ["name"]
    list_filter = ["type"]


@admin.register(models.InstanceClear)
class InstanceClearAdmin(admin.ModelAdmin):
    list_display = (
        "id",
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
    search_fields = ["id", "name"]

    inlines = [DpsLogInline]

    def log_count(self, obj):
        return obj.dps_logs.all().count()


@admin.register(models.InstanceClearGroup)
class InstanceClearGroupAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "type",
        "success",
        "duration",
        "start_time",
        "discord_message",
        "core_player_count",
        "friend_player_count",
        "log_count",
        "duration_encounters",
    )

    inlines = [InstanceClearInline]
    search_fields = ["id", "name"]
    list_filter = ["success", "type", "duration_encounters"]

    def log_count(self, obj):
        return sum([ic.dps_logs.all().count() for ic in obj.instance_clears.all()])


@admin.register(models.DpsLog)
class DpsLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "encounter",
        "cm",
        "lcm",
        "emboldened",
        "success",
        "use_in_leaderboard",
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
    list_display = ("id", "name", "gw2_id", "role")

    ordering = ("name",)


@admin.register(models.DiscordMessage)
class DiscordMessage(admin.ModelAdmin):
    list_display = ("id", "message_id", "name", "weekdate", "linked_count", "created_at", "updated_at", "update_count")
    inlines = [InstanceClearGroupInline, InstanceInline, InstanceGroupInline]

    readonly_fields = ("created_at", "updated_at")
    ordering = ("-updated_at",)

    search_fields = ["message_id", "name"]

    def linked_count(self, obj):
        return obj.instance_clear_group.all().count() + obj.instance.all().count() + obj.instance_group.all().count()
