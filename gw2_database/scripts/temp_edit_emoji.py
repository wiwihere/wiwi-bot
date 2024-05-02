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
# from bot_settings import settings
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

# from scripts.log_helpers import (
#     EMBED_COLOR,
#     ITYPE_GROUPS,
#     WEBHOOKS,
#     WIPE_EMOTES,
#     create_discord_time,
#     create_or_update_discord_message,
#     get_duration_str,
#     get_rank_emote,
#     zfill_y_m_d,
# )

"""
\:junkmedal:
\:basicmedal:
\:finemedal:
\:masterworkmedal:
\:raremedal:
\:exoticmedal2:
\:ascmedal2:
\:legendarymedal2:
"""

"""
\:perfectbronzetrophyglow:
\:perfectsilvertrophyglow:
\:perfectgoldtrophyglow:
"""

the_old_ones = """
<:1_junk:1216411751688699994>
<:2_basic:1216411752992866395>
<:3_fine:1216411754959995081>
<:4_masterwork:1216411757413662810>
<:5_rare:1216411759146172578>
<:6_exotic:1216411760635019355>
<:7_ascended:1216411761868013731>
<:8_legendary:1216411763172708395>"""


medalnames = {
    "junkmedal": "1_junk",
    "basicmedal": "2_basic",
    "finemedal": "3_fine",
    "masterworkmedal": "4_masterwork",
    "raremedal": "5_rare",
    "exoticmedal2": "6_exotic",
    "ascmedal2": "7_ascended",
    "legendarymedal2": "8_legendary",
    "perfectgoldtrophyglow": "trophy_gold",
    "perfectsilvertrophyglow": "trophy_silver",
    "perfectbronzetrophyglow": "trophy_bronze",
}

# a = """<:junkmedal:1218317392627765450>
# <:basicmedal:1218317391260287006>
# <:finemedal:1218307650580647976>
# <:masterworkmedal:1218309092477767810>
# <:raremedal:1218309546636742727>
# <:exoticmedal2:1218317136628285460>
# <:ascmedal2:1218317135214805072>
# <:legendarymedal2:1218314286783533157>"""
a = """
<:perfectbronzetrophyglow:1220499344013267045>
<:perfectsilvertrophyglow:1220500728481710181>
<:perfectgoldtrophyglow:1220500180898680833> 
"""


for b in a.split(">"):
    if ":" in b:
        name = b.split(":")[1]
        ids = b.split(":")[2]
        print(ids)
    emoji, up = Emoji.objects.update_or_create(
        name=medalnames[name],
        defaults={"discord_id": ids, "type": "medal"},
    )
    emoji.save()

# %%
