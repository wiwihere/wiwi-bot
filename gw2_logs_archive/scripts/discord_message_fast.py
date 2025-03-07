# %%


"""Populate discord channel with fast logs.
The raid-logs channel can become very slow to load because of all the emotes.

This function will populate a separate channel with only the most recent logs.
"""

import logging

from discord import SyncWebhook
from django.conf import settings

if __name__ == "__main__":
    from _setup_django import init_django

    init_django(__file__)

from gw2_logs.models import (
    DiscordMessage,
    DpsLog,
    Encounter,
    Instance,
    InstanceClear,
    InstanceClearGroup,
)
from scripts.log_helpers import ITYPE_GROUPS, create_or_update_discord_message
from scripts.log_instance_interaction import InstanceClearGroupInteraction, create_embeds

logger = logging.getLogger(__name__)


y, m, d = 2025, 2, 6
itype_group = "raid"

self = icgi = InstanceClearGroupInteraction.create_from_date(y=y, m=m, d=d, itype_group=itype_group)
# self = icgi = InstanceClearGroupInteraction.from_name("dummy")
# icgi.send_discord_message()

# Find the clear groups. e.g. [raids__20240222, strikes__20240222]
grp_lst = [self.iclear_group]
if self.iclear_group.discord_message is not None:
    grp_lst += self.iclear_group.discord_message.instance_clear_group.all()
grp_lst = sorted(set(grp_lst), key=lambda x: x.start_time)

# combine embeds
embeds = {}
for icg in grp_lst:
    icgi = InstanceClearGroupInteraction.from_name(icg.name)

    titles, descriptions = icgi.create_message()
    icg_embeds = create_embeds(titles, descriptions)
    embeds.update(icg_embeds)
embeds_mes = list(embeds.values())


# %%

# Initialize fast channel
i = 1
for itype_group in ITYPE_GROUPS:
    message_name = f"FAST_{itype_group}_message_{i}"

    if len(settings.WEBHOOKS_FAST[itype_group]) > 20:
        try:
            if (itype_group == "strike") and (ITYPE_GROUPS["strike"] == ITYPE_GROUPS["raid"]):
                message_name2 = f"FAST_raid_message_{i}"
                disc_mess = DiscordMessage.objects.get(name=message_name2)

                try:
                    DiscordMessage.objects.get(name=message_name)
                except DiscordMessage.DoesNotExist:
                    logger.info(f"Dupe message {message_name}")
                    disc_mess.message_id

                    disc_mess2 = DiscordMessage.objects.create(message_id=disc_mess.message_id, name=message_name)

        except DiscordMessage.DoesNotExist:
            logger.info(f"Creating new fast message {message_name}")
            webhook = SyncWebhook.from_url(settings.WEBHOOKS_FAST[itype_group])
            mess = webhook.send(wait=True, embeds=embeds_mes)

            disc_mess = DiscordMessage.objects.create(message_id=mess.id, name=message_name)
            disc_mess.increase_counter()
