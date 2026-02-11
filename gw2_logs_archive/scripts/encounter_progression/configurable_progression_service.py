# %% gw2_logs_archive\scripts\encounter_progression\configurable_progression_service.py
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import json
import logging
from typing import Optional

from django.conf import settings
from gw2_logs.models import (
    Encounter,
    InstanceClearGroup,
)
from pydantic import BaseModel
from scripts.encounter_progression.base_progression_service import ProgressionService
from scripts.log_helpers import (
    today_y_m_d,
    zfill_y_m_d,
)

logger = logging.getLogger(__name__)


class ProgressionConfig(BaseModel):
    description: Optional[str] = None
    encounter_name: str
    embed_colour: int
    webhook_thread_id_from_dotenv: str
    display_health_percentages: list[int]


def _load_progression_config() -> dict[str, ProgressionConfig]:
    config_path = settings.PROJECT_DIR.joinpath("data", "encounter_progression_config.json")
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found at {config_path}.\nPlease create it with the necessary progression configurations."
            """\n Example configuration:
                {
                "cerus_cm": { <-- this is the clear_group_base_name, used to start a progression run.
                    "description": "Early 2024 run", <-- optional
                    "encounter_name": "Temple of Febe", <-- encounter name as in the database
                    "embed_colour": "cerus_cm", <-- needs to be a colour code.
                    "webhook_thread_id_from_dotenv": "webhook_bot_thread_cerus_cm" <-- needs to be in .env.prd
                    "display_health_percentages": [80, 50, 10] <-- the remaining time is displayed at these percentages.
                    "enrage_timer": 1800 <-- optional, if not provided, enrage timer from database is used.
                    },
                }
            """
        )
    with open(config_path, "r") as f:
        raw_data = json.load(f)
        return {key: ProgressionConfig(**value) for key, value in raw_data.items()}


class ConfigurableProgressionService(ProgressionService):
    """Generic progression service that reads configuration from encounter_progression_config.json
    See the _load_progression_config function for expected config format.
    """

    def __init__(
        self,
        clear_group_base_name: str,
        y: int,
        m: int,
        d: int,
    ):
        config_dict = _load_progression_config()
        self.clear_group_base_name = clear_group_base_name
        self.clear_name = f"{self.clear_group_base_name}_progression__{zfill_y_m_d(y, m, d)}"

        if clear_group_base_name not in config_dict:
            self.raise_with_available_progressions(config_dict)

        config = config_dict[clear_group_base_name]

        self.encounter = Encounter.objects.get(name=config.encounter_name)
        self.embed_colour = config.embed_colour
        self.webhook_thread_id = getattr(settings.ENV_SETTINGS, config.webhook_thread_id_from_dotenv)
        self.webhook_url = settings.WEBHOOKS["progression"]

        super().__init__(
            clear_group_base_name=self.clear_group_base_name,
            clear_name=self.clear_name,
            encounter=self.encounter,
            embed_colour=self.embed_colour,
            webhook_thread_id=self.webhook_thread_id,
            webhook_url=self.webhook_url,
        )

    def raise_with_available_progressions(self, config_dict: dict):
        available_progressions = ", ".join(config_dict.keys())
        progressions_in_db = {
            name.split("_progression__")[0]
            for name in InstanceClearGroup.objects.filter(name__contains="_progression__").values_list(
                "name", flat=True
            )
        }
        raise ValueError(
            f"Unknown progression '{self.clear_group_base_name}'.\nAvailable progressions: {available_progressions}\nIn database: {', '.join(progressions_in_db)}"
        )


# %%

if __name__ == "__main__":
    y, m, d = today_y_m_d()

    # Example for Cerus
    # y, m, d = 2024, 3, 16
    # progression_service = ConfigurableProgressionService(clear_group_base_name="cerus_cm", y=y, m=m, d=d)

    # Example for Decima
    y, m, d = 2025, 12, 8
    progression_service = ConfigurableProgressionService(clear_group_base_name="decima_cm", y=y, m=m, d=d)

# %%
