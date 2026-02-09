# %% gw2_logs_archive\scripts\encounter_progression\cerus_service.py
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import logging

from django.conf import settings
from gw2_logs.models import (
    Encounter,
)
from scripts.encounter_progression.base_progression_service import RANK_EMOTES_PROGRESSION, ProgressionService
from scripts.log_helpers import (
    today_y_m_d,
    zfill_y_m_d,
)

logger = logging.getLogger(__name__)


class CerusProgressionService(ProgressionService):
    def __init__(
        self,
        clear_group_base_name: str,
        y: int,
        m: int,
        d: int,
    ):
        self.clear_group_base_name = clear_group_base_name
        self.clear_name = f"{self.clear_group_base_name}__{zfill_y_m_d(y, m, d)}"  # e.g. cerus_cm__20240406
        self.encounter = Encounter.objects.get(name="Temple of Febe")
        self.embed_colour_group = "cerus_cm"  # needed for embed parsing, needs to be in EMBED_COLOUR
        self.webhook_thread_id = getattr(
            settings.ENV_SETTINGS, "webhook_bot_thread_cerus_cm"
        )  # needs to be in .env.prd
        self.webhook_url = settings.WEBHOOKS["progression"]

        super().__init__(
            clear_group_base_name=self.clear_group_base_name,
            clear_name=self.clear_name,
            encounter=self.encounter,
            embed_colour_group=self.embed_colour_group,
            webhook_thread_id=self.webhook_thread_id,
            webhook_url=self.webhook_url,
        )

    def get_table_header(self) -> str:
        return f"`##`{RANK_EMOTES_PROGRESSION[7]}**★** ` health |  80% |  50% |  10% `+_delay_⠀⠀\n\n"


# %%

if __name__ == "__main__":
    y, m, d = today_y_m_d()
    y, m, d = 2024, 3, 16
    cps = CerusProgressionService(clear_group_base_name="cerus_cm", y=y, m=m, d=d)

# %%
