# %%

"""Run leadederboards, builds messages, creates embeds and publishes on discord."""

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

import logging
from typing import Literal

from scripts.leaderboards.leaderboard_publishers import (
    publish_fullclear_message,
    publish_instance_leaderboard_messages,
    publish_navigation_menu,
)

logger = logging.getLogger(__name__)


def run_leaderboard(instance_type: Literal["raid", "strike", "fractal"]) -> None:
    """
    Run complete leaderboard generation for an instance type.

    Creates and publishes:
    1. Individual instance leaderboards (one per wing/strike/fractal)
    2. Full clear leaderboard (all instances combined)

    Parameters
    ----------
    instance_type: Literal["raid", "strike", "fractal"]
        Type of instances to process
    """

    logger.info(f"{instance_type}: Running leaderboard generation")

    publish_instance_leaderboard_messages(instance_type=instance_type)
    publish_fullclear_message(instance_type=instance_type)

    logger.info(f"{instance_type}: Completed leaderboard generation")


def run_leaderboard_navigation():
    """
    Publish navigation menu for leaderboards.

    Creates a single message with links to all individual instance leaderboards.
    """
    publish_navigation_menu()


if __name__ == "__main__":
    # For direct script execution / testing
    import sys

    if len(sys.argv) > 1:
        instance_type = sys.argv[1]
        run_leaderboard(instance_type)
    else:
        # Default for testing
        logger.info("No instance type provided, running for 'raid'")
        run_leaderboard("raid")
