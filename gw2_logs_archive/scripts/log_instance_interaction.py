# %%
# TODO remove?
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import datetime
import logging
from dataclasses import dataclass
from itertools import chain

import discord
import numpy as np
import pandas as pd
from django.conf import settings
from django.db.models import Q
from gw2_logs.models import (
    DiscordMessage,
    DpsLog,
    Encounter,
    Instance,
    InstanceClear,
    InstanceClearGroup,
)
from scripts.log_helpers import (
    EMBED_COLOR,
    ITYPE_GROUPS,
    PLAYER_EMOTES,
    WIPE_EMOTES,
    create_discord_time,
    create_or_update_discord_message,
    create_or_update_discord_message_current_week,
    get_duration_str,
    get_rank_emote,
    zfill_y_m_d,
)

logger = logging.getLogger(__name__)


# %%

if __name__ == "__main__":
    y, m, d = 2025, 9, 8
    itype_group = "raid"

    self = icgi = InstanceClearGroupInteraction.create_from_date(y=y, m=m, d=d, itype_group=itype_group)

    self = icgi = InstanceClearGroupInteraction.from_name("raids__20250206")
    if icgi is not None:
        # Set the same discord message id when strikes and raids are combined.
        if (ITYPE_GROUPS["raid"] == ITYPE_GROUPS["strike"]) and (icgi.iclear_group.type in ["raid", "strike"]):
            if self.iclear_group.discord_message is None:
                group_names = [
                    "__".join([f"{j}s", self.iclear_group.name.split("__")[1]]) for j in ITYPE_GROUPS["raid"]
                ]
                self.iclear_group.discord_message_id = (
                    InstanceClearGroup.objects.filter(name__in=group_names)
                    .exclude(discord_message=None)
                    .values_list("discord_message", flat=True)
                    .first()
                )
                self.iclear_group.save()

        # Find the clear groups. e.g. [raids__20240222, strikes__20240222]
        grp_lst = [icgi.iclear_group]
        if icgi.iclear_group.discord_message is not None:
            grp_lst += icgi.iclear_group.discord_message.instance_clear_group.all()
        grp_lst = sorted(set(grp_lst), key=lambda x: x.start_time)

        # combine embeds
        embeds = {}
        for icg in grp_lst:
            icgi = InstanceClearGroupInteraction.from_name(icg.name)
            logger.info(icg.name)
            titles, descriptions = icgi.create_message()
            icg_embeds = create_embeds(titles, descriptions)
            embeds.update(icg_embeds)
        embeds_mes = list(embeds.values())

        create_or_update_discord_message(
            group=icgi.iclear_group,
            hook=settings.WEBHOOKS[icgi.iclear_group.type],
            embeds_messages_list=embeds_mes,
        )
