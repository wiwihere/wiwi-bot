# %% gw2_logs_archive\scripts\encounter_progression\cerus_service.py
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import json
import logging
from pathlib import Path

from django.conf import settings
from gw2_logs.models import (
    Encounter,
)
from scripts.encounter_progression.base_progression_service import ProgressionService
from scripts.log_helpers import (
    today_y_m_d,
    zfill_y_m_d,
)

logger = logging.getLogger(__name__)

# Load config
CONFIG_PATH = Path(__file__).parent / "encounter_progression_config.json"
with open(CONFIG_PATH, "r") as f:
    PROGRESSION_CONFIG = json.load(f)


class DecimaProgressionService(ProgressionService):
    def __init__(
        self,
        clear_group_base_name: str,
        y: int,
        m: int,
        d: int,
    ):
        config = PROGRESSION_CONFIG[clear_group_base_name]
        
        self.clear_group_base_name = clear_group_base_name
        self.clear_name = f"{self.clear_group_base_name}__{zfill_y_m_d(y, m, d)}"  # e.g. decima_cm__20240406
        self.encounter = Encounter.objects.get(name=config["encounter_name"])
        self.embed_colour_group = config["embed_colour_group"]  # needed for embed parsing, needs to be in EMBED_COLOUR
        self.webhook_thread_id = getattr(
            settings.ENV_SETTINGS, config["webhook_thread_id_attr"]
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


# %%

if __name__ == "__main__":
    y, m, d = today_y_m_d()
    y, m, d = 2024, 3, 16
    cps = DecimaProgressionService(clear_group_base_name="decima_cm", y=y, m=m, d=d)

# %%
