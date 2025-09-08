# %%


import datetime

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)

import logging

from gw2_logs.models import DpsLog, InstanceClearGroup, Player
from scripts.log_helpers import today_y_m_d
from scripts.log_instance_interaction import InstanceClearGroupInteraction
from scripts.tools.update_discord_messages import update_discord_message_single

logger = logging.getLogger(__name__)


def reculculate_friends(y, m, d):
    """When a friend is added to the Players. We need to recalculate the friend counts in the logs"""
    for dpslog in DpsLog.objects.filter(
        start_time__gte=datetime.datetime(year=y, month=m, day=d, tzinfo=datetime.timezone.utc)
    ):
        logger.info(f"Updating {dpslog}")

        players = dpslog.players

        core_player_count_current = dpslog.core_player_count
        friend_player_count_current = dpslog.friend_player_count

        core_player_count_new = len(Player.objects.filter(gw2_id__in=players, role="core"))
        friend_player_count_new = len(Player.objects.filter(gw2_id__in=players, role="friend"))

        update = False
        if core_player_count_current != core_player_count_new:
            logger.info(
                f"Core player count changed from {core_player_count_current} to {core_player_count_new} for {dpslog}"
            )
            update = True
            dpslog.core_player_count = core_player_count_new
        if friend_player_count_current != friend_player_count_new:
            logger.info(
                f"Friend player count changed from {friend_player_count_current} to {friend_player_count_new} for {dpslog}"
            )
            update = True
            dpslog.friend_player_count = friend_player_count_new

        if update:
            dpslog.save()

    for itype_group in ["raid", "strike"]:
        update_discord_message_single(y=y, m=m, d=d)


# %%
if __name__ == "__main__":
    # y, m, d = 2025, 3, 6
    # y, m, d = 2025, 2, 24
    # y, m, d = 2025, 2, 27
    y, m, d = today_y_m_d()
    itype_group = "raid"

    reculculate_friends(y=y, m=m, d=d)
