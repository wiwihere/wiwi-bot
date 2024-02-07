# %%
import logging  # noqa:F401
import os
from pathlib import Path

from dotenv import load_dotenv

r = load_dotenv(Path(__file__).parent.joinpath(".env"))

DISCORD_API_SECRET = os.getenv("DISCORD_API_TOKEN")
WEBHOOK_BOT_CHANNEL_RAID = os.getenv("WEBHOOK_BOT_CHANNEL_RAID")
WEBHOOK_BOT_CHANNEL_FRACTAL = os.getenv("WEBHOOK_BOT_CHANNEL_FRACTAL")
WEBHOOK_BOT_CHANNEL_LEADERBOARD = os.getenv("WEBHOOK_BOT_CHANNEL_LEADERBOARD")

LEADERBOARD_THREADS = {  # thread channel ids in discord.
    "raid": os.getenv("WEBHOOK_BOT_CHANNEL_LEADERBOARD_RAIDS"),
    "strike": os.getenv("WEBHOOK_BOT_CHANNEL_LEADERBOARD_STRIKES"),
    "fractal": os.getenv("WEBHOOK_BOT_CHANNEL_LEADERBOARD_FRACTALS"),
}

CORE_MINIMUM = {
    "raid": int(os.getenv("CORE_MINIMUM_RAID")),
    "strike": int(os.getenv("CORE_MINIMUM_RAID")),
    "fractal": int(os.getenv("CORE_MINIMUM_FRACTAL")),
}
INCLUDE_NON_CORE_LOGS = os.getenv("INCLUDE_NON_CORE_LOGS") == True  # Include non core logs on leaderboards

DPS_REPORT_USERTOKEN = os.getenv("DPS_REPORT_USERTOKEN")
DEBUG = os.getenv("DEBUG") == "True"

BASE_DIR = Path(__file__).parent

DPS_LOGS_DIR = rf"{Path.home()}\Documents\Guild Wars 2\addons\arcdps\arcdps.cbtlogs"
# Shared drive with other static members, they can post logs there to upload.
ONEDRIVE_LOGS_DIR = rf"{Path.home()}\OneDrive\gw2_shared_logs"

CMDS_DIR = BASE_DIR / "cmds"
COGS_DIR = BASE_DIR / "cogs"

VIDEOCMDS_DIR = BASE_DIR / "videocmds"


# GUILDS_ID = discord.Object(id=int(os.getenv("GUILD")))
# FEEDBACK_CH = int(os.getenv("FEEDBACK_CH", 0))
# GUILD_ID_INT = int(os.getenv("GUILD"))

LOGGING_CONFIG = {
    "version": 1,
    "disabled_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "%(levelname)-10s - %(asctime)s - %(module)-15s : %(message)s"},
        "standard": {"format": "%(levelname)-10s - %(name)-15s : %(message)s"},
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
        "console2": {
            "level": "WARNING",
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": "logs/infos.log",
            "mode": "w",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "bot": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "discord": {
            "handlers": ["console2", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# dictConfig(LOGGING_CONFIG)
