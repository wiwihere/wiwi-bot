# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import datetime
import logging
from dataclasses import dataclass
from itertools import chain
from typing import TYPE_CHECKING, Tuple, Union

import discord
import numpy as np
import pandas as pd
from django.conf import settings
from django.db.models import Q, QuerySet
from gw2_logs.models import (
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
from scripts.model_interactions.dps_log import DpsLogInteraction
from scripts.model_interactions.instance_clear import InstanceClearInteraction

logger = logging.getLogger(__name__)


def create_discord_embeds(titles, descriptions) -> dict[str, discord.Embed]:
    """Create discord embed from titles and descriptions."""
    embeds: dict[str, discord.Embed] = {}
    has_title = False
    for instance_type in titles:
        use_fields = True  # max 1024 per field
        field_characters = np.array([len(i) for i in descriptions[instance_type].values()])
        # Check field length. If more than 1024 it cannot go to a field and should instead
        # go to description
        if np.any(field_characters > 1024):
            logger.info("Cannot use fields because one has more than 1024 chars")
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
                        logger.debug(f"{len(description)} something is up with embeds")

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
                    embeds[f"{instance_type}_{embed_id}"].add_field(name=field_name, value=field_value, inline=False)

    return embeds


if __name__ == "__main__":
    from scripts.model_interactions.instance_clear_group import InstanceClearGroupInteraction

    # Test refactor on the go. Dont touch the code below.
    y, m, d = 2025, 12, 18
    itype_group = "raid"

    icgi = InstanceClearGroupInteraction.create_from_date(y=y, m=m, d=d, itype_group=itype_group)
    titles, descriptions = create_discord_message(icgi)

    assert titles == {
        "raid": {
            "main": "Thu 18 Dec 2025⠀⠀⠀⠀<:r20_of45_slower1804_9s:1240399925502545930> **3:12:00** <:r20_of45_slower1804_9s:1240399925502545930> \n",
            "spirit_vale__20251218": "**__<:spirit_vale:1185639755464060959><:r46_of82_slower108_8s:1240799615763222579>Spirit Vale (17:49)__**\n",
            "salvation_pass__20251218": "**__<:salvation_pass:1185642016776913046><:r23_of84_slower55_9s:1240399925502545930>Salvation Pass (14:55)__**\n",
            "bastion_of_the_penitent__20251218": "**__<:bastion_of_the_penitent:1185642020484698132><:r73_of99_slower319_4s:1240799615763222579>Bastion of the Penitent (23:26)__**\n",
            "mount_balrior__20251218": "**__<:mount_balrior:1311064236486688839><:r14_of39_slower175_0s:1240399925502545930>Mount Balrior (22:17)__**\n",
        }
    }

    assert descriptions == {
        "raid": {
            "main": "<t:1766083791:t> - <t:1766089156:t> \n<a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414> <a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:pug:1206367130509905931>\n\n",
            "spirit_vale__20251218": "<:vale_guardian:1206250717401063605><:r55_of82_slower22_6s:1240799615763222579>[Vale Guardian](https://dps.report/Zb2m-20251218-185224_vg) (**2:31**)_+0:00_\n<:gorseval_the_multifarious:1206250719074721813><:r29_of83_slower10_7s:1240399925502545930>[Gorseval the Multifarious](https://dps.report/aIEy-20251218-190208_gors) (**2:10**)_+7:33_\n<:sabetha_the_saboteur:1206250720483872828><:r68_of83_slower49_0s:1240798628596027483>[Sabetha the Saboteur](https://dps.report/texU-20251218-190742_sab) (**3:42**)_+1:51_\n",
            "salvation_pass__20251218": "<:slothasor:1206250721880576081><:r8_of84_slower9_5s:1240399924198379621>[Slothasor](https://dps.report/yGvz-20251218-191257_sloth) (**2:10**)_+2:58_\n<:bandit_trio:1206250723550175283><:r26_of84_slower4_6s:1240399925502545930>[Bandit Trio](https://dps.report/3csn-20251218-192149_trio) (**6:31**)_+0:22_\n<:matthias_gabrel:1206250724879503410><:r72_of84_slower66_0s:1240798628596027483>[Matthias Gabrel](https://dps.report/D9Wl-20251218-192539_matt) (**3:10**)_+2:40_\n",
            "bastion_of_the_penitent__20251218": "<:cairn:1206251996680556544><:r6_of99_slower3_6s:1240399924198379621>[Cairn CM](https://dps.report/e3La-20251218-193053_cairn) (**1:18**)_+3:44_\n<:mursaat_overseer:1206252000229199932><:r3_of99_slower3_7s:1338196304924250273>[Mursaat Overseer CM](https://dps.report/cUNu-20251218-193357_mo) (**1:37**)_+1:35_\n<:samarog:1206256460120457277><:r4_of99_slower41_2s:1240399924198379621>[Samarog CM](https://dps.report/Lgpi-20251218-194020_sam) (**5:08**)_+1:19_\n<:deimos:1206256463031304253><:r5_of99_slower19_9s:1240399924198379621>[Deimos CM](https://dps.report/7jym-20251218-195252_dei) (**5:23**)_+7:03_ [<:wipe_at_14:1199739670641258526>](https://dps.report/2Q8K-20251218-194648_dei)\n",
            "mount_balrior__20251218": "<:greer:1310742326548762664><:r21_of42_slower45_4s:1240799615763222579>[Greer, the Blightbringer](https://dps.report/IPHG-20251218-200502_greer) (**7:59**)_+4:13_\n<:decima:1310742355644776458><:r17_of40_slower39_0s:1240399925502545930>[Decima, the Stormsinger](https://dps.report/tOQg-20251218-201241_deci) (**4:57**)_+2:41_\n<:ura:1310742374665683056><:r21_of40_slower42_1s:1240799615763222579>[Ura](https://dps.report/3xn6-20251218-201925_ura) (**4:50**)_+1:48_\n",
        }
    }

    embeds = create_discord_embeds(titles=titles, descriptions=descriptions)

    embeds[
        "raid_0"
    ].title == "Thu 18 Dec 2025⠀⠀⠀⠀<:r20_of45_slower1804_9s:1240399925502545930> **3:12:00** <:r20_of45_slower1804_9s:1240399925502545930> \n"

    expected_fields = [
        "EmbedProxy(inline=False, name='**__<:spirit_vale:1185639755464060959><:r46_of82_slower108_8s:1240799615763222579>Spirit Vale (17:49)__**\n', value='<:vale_guardian:1206250717401063605><:r55_of82_slower22_6s:1240799615763222579>[Vale Guardian](https://dps.report/Zb2m-20251218-185224_vg) (**2:31**)_+0:00_\n<:gorseval_the_multifarious:1206250719074721813><:r29_of83_slower10_7s:1240399925502545930>[Gorseval the Multifarious](https://dps.report/aIEy-20251218-190208_gors) (**2:10**)_+7:33_\n<:sabetha_the_saboteur:1206250720483872828><:r68_of83_slower49_0s:1240798628596027483>[Sabetha the Saboteur](https://dps.report/texU-20251218-190742_sab) (**3:42**)_+1:51_\n')",
        "EmbedProxy(inline=False, name='**__<:salvation_pass:1185642016776913046><:r23_of84_slower55_9s:1240399925502545930>Salvation Pass (14:55)__**\n', value='<:slothasor:1206250721880576081><:r8_of84_slower9_5s:1240399924198379621>[Slothasor](https://dps.report/yGvz-20251218-191257_sloth) (**2:10**)_+2:58_\n<:bandit_trio:1206250723550175283><:r26_of84_slower4_6s:1240399925502545930>[Bandit Trio](https://dps.report/3csn-20251218-192149_trio) (**6:31**)_+0:22_\n<:matthias_gabrel:1206250724879503410><:r72_of84_slower66_0s:1240798628596027483>[Matthias Gabrel](https://dps.report/D9Wl-20251218-192539_matt) (**3:10**)_+2:40_\n')",
        "EmbedProxy(inline=False, name='**__<:bastion_of_the_penitent:1185642020484698132><:r73_of99_slower319_4s:1240799615763222579>Bastion of the Penitent (23:26)__**\n', value='<:cairn:1206251996680556544><:r6_of99_slower3_6s:1240399924198379621>[Cairn CM](https://dps.report/e3La-20251218-193053_cairn) (**1:18**)_+3:44_\n<:mursaat_overseer:1206252000229199932><:r3_of99_slower3_7s:1338196304924250273>[Mursaat Overseer CM](https://dps.report/cUNu-20251218-193357_mo) (**1:37**)_+1:35_\n<:samarog:1206256460120457277><:r4_of99_slower41_2s:1240399924198379621>[Samarog CM](https://dps.report/Lgpi-20251218-194020_sam) (**5:08**)_+1:19_\n<:deimos:1206256463031304253><:r5_of99_slower19_9s:1240399924198379621>[Deimos CM](https://dps.report/7jym-20251218-195252_dei) (**5:23**)_+7:03_ [<:wipe_at_14:1199739670641258526>](https://dps.report/2Q8K-20251218-194648_dei)\n')",
        "EmbedProxy(inline=False, name='**__<:mount_balrior:1311064236486688839><:r14_of39_slower175_0s:1240399925502545930>Mount Balrior (22:17)__**\n', value='<:greer:1310742326548762664><:r21_of42_slower45_4s:1240799615763222579>[Greer, the Blightbringer](https://dps.report/IPHG-20251218-200502_greer) (**7:59**)_+4:13_\n<:decima:1310742355644776458><:r17_of40_slower39_0s:1240399925502545930>[Decima, the Stormsinger](https://dps.report/tOQg-20251218-201241_deci) (**4:57**)_+2:41_\n<:ura:1310742374665683056><:r21_of40_slower42_1s:1240799615763222579>[Ura](https://dps.report/3xn6-20251218-201925_ura) (**4:50**)_+1:48_\n')",
    ]

    for idx, field in enumerate(embeds["raid_0"].fields):
        str(field) == expected_fields[idx]
