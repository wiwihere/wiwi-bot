# %%
import datetime
from dataclasses import dataclass
from itertools import chain

import discord
import numpy as np
import pandas as pd
from discord import SyncWebhook
from django.db.models import Q

if __name__ == "__main__":
    from django_for_jupyter import init_django_from_commands

    init_django_from_commands("gw2_database")
from bot_settings import settings
from gw2_logs.models import (
    DiscordMessage,
    DpsLog,
    Emoji,
    Encounter,
    Instance,
    InstanceClear,
    InstanceClearGroup,
    Player,
)
from scripts.log_helpers import (
    EMBED_COLOR,
    ITYPE_GROUPS,
    WEBHOOKS,
    WIPE_EMOTES,
    create_discord_time,
    create_or_update_discord_message,
    get_duration_str,
    get_rank_emote,
    zfill_y_m_d,
)

"""
\:1_junk:
\:2_basic:
\:3_fine:
\:4_masterwork:
\:5_rare:
\:6_exotic:
\:7_ascended:
\:8_legendary:
"""

a = """<:1_junk:1216411751688699994>
<:2_basic:1216411752992866395>
<:3_fine:1216411754959995081>
<:4_masterwork:1216411757413662810>
<:5_rare:1216411759146172578>
<:6_exotic:1216411760635019355>
<:7_ascended:1216411761868013731>
<:8_legendary:1216411763172708395>"""


for b in a.split(">"):
    if ":" in b:
        name = b.split(":")[1]
        ids = b.split(":")[2]
        print(ids)
    emoji = Emoji.objects.update_or_create(
        name=name,
        defaults={"discord_id": ids, "type": "medal"},
    )
    emoji.save()
